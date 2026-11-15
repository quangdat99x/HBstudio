"""
Main Processing Pipeline - Orchestrates face detection, active-speaker
detection, and video cropping/zoom to produce the final auto-zoomed
podcast video.

Focus: track the face of the person currently speaking and pan the
"virtual camera" smoothly between speakers. When the producer puts a
document on screen (picture-in-picture inset of a web page, image,
article) the camera moves to the document and zooms only as far as the
whole document still fits; when nobody's face is on screen for a while
(full-screen document or footage) it shows the whole frame.

Uses FFmpeg to decode video frames (via pipe) instead of OpenCV's
VideoCapture, which ensures compatibility with all codecs including
H.265/HEVC.
"""

import os
import queue as _queue
import subprocess
import time
import numpy as np
import threading as _threading
from typing import Optional, Callable, Dict, Any
from .face_detector import FaceDetector
from .document_detector import DocumentDetector
from .speaker_detector import SpeakerDetector
from .video_processor import VideoProcessor
from .ffmpeg_utils import ensure_ffmpeg, video_encode_args
from .thumbnail_generator import generate_split_thumbnail


def _probe_video(ffmpeg_bin: str, input_path: str) -> Dict[str, Any]:
    """
    Use ffprobe to get video metadata: width, height, fps, total_frames, duration.
    Falls back to sane defaults if ffprobe fails.
    """
    ffprobe_bin = os.path.join(os.path.dirname(ffmpeg_bin), 'ffprobe.exe')
    if not os.path.exists(ffprobe_bin):
        ffprobe_bin = 'ffprobe'

    # Use key=value output instead of positional CSV: ffprobe's csv writer
    # does not reliably preserve the -show_entries request order (observed
    # emitting width,height,r_frame_rate,duration,nb_frames despite nb_frames
    # being requested before duration), which silently corrupted every
    # probe here — nb_frames parsed a duration string like "1073.966667",
    # int() raised, and every video fell back to the hardcoded
    # 1920x1080@30fps/duration=0 defaults below regardless of the real
    # source. Key=value parsing is immune to field ordering.
    cmd = [
        ffprobe_bin, '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,r_frame_rate,nb_frames,duration',
        '-of', 'default=noprint_wrappers=1:nokey=0',
        input_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = {}
        for line in result.stdout.strip().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                info[k.strip()] = v.strip()

        width = int(info['width'])
        height = int(info['height'])
        # r_frame_rate is like "30/1" or "30000/1001"
        fps_parts = info.get('r_frame_rate', '30/1').split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
        nb_frames_raw = info.get('nb_frames', '')
        nb_frames = int(nb_frames_raw) if nb_frames_raw not in ('', 'N/A') else 0
        duration_raw = info.get('duration', '')
        duration = float(duration_raw) if duration_raw not in ('', 'N/A') else 0.0

        # Video-stream duration is frequently missing/N/A (common in mp4/mov
        # muxes). Fall back to container-level duration, which is what the
        # audio track's real length is measured against — using the video
        # stream's (sometimes absent or slightly off) duration here is what
        # causes the render fps below to drift from the true audio length.
        if duration <= 0:
            fmt_cmd = [
                ffprobe_bin, '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=0',
                input_path
            ]
            fmt_result = subprocess.run(fmt_cmd, capture_output=True, text=True, timeout=30)
            fmt_out = fmt_result.stdout.strip()
            if fmt_out.startswith('duration='):
                fmt_val = fmt_out.split('=', 1)[1].strip()
                if fmt_val not in ('', 'N/A'):
                    duration = float(fmt_val)

        if nb_frames == 0 and duration > 0 and fps > 0:
            nb_frames = int(duration * fps)
        return {'width': width, 'height': height, 'fps': fps,
                'total_frames': nb_frames, 'duration': duration}
    except Exception as e:
        print(f"[WARN] ffprobe failed: {e}")
        return {'width': 1920, 'height': 1080, 'fps': 30.0,
                'total_frames': 0, 'duration': 0.0}


def _open_ffmpeg_reader(ffmpeg_bin: str, input_path: str,
                        width: int, height: int) -> subprocess.Popen:
    """Open an FFmpeg subprocess that outputs raw BGR24 frames to stdout."""
    cmd = [
        ffmpeg_bin, '-y',
        '-i', input_path,
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-vcodec', 'rawvideo',
        'pipe:1',
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=10 * 1024 * 1024,  # 10MB buffer
    )
    return proc


def _read_frame(proc: subprocess.Popen, width: int, height: int) -> Optional[np.ndarray]:
    """Read a single raw BGR frame from the FFmpeg pipe."""
    frame_size = width * height * 3
    raw = b''
    while len(raw) < frame_size:
        chunk = proc.stdout.read(frame_size - len(raw))
        if not chunk:
            return None
        raw += chunk
    return np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()


class _PrefetchReader:
    """Reads frames off an FFmpeg pipe on a background thread.

    Reading and per-frame work are strictly alternating in a naive loop: while
    Python resizes or analyses a frame, FFmpeg is stalled on a full pipe, and
    while FFmpeg decodes, Python is blocked on read(). Since both the pipe read
    and OpenCV/MediaPipe release the GIL, moving the read onto its own thread
    lets the two overlap, so a frame costs max(decode, process) instead of
    their sum — measured ~1.5x on the render pass.

    Frames are handed out strictly in order and byte-for-byte identical to what
    the serial path produced, so output is unchanged.
    """

    def __init__(self, proc: subprocess.Popen, width: int, height: int, depth: int = 8):
        self._proc = proc
        self._width = width
        self._height = height
        self._frame_size = width * height * 3
        self._queue: "_queue.Queue" = _queue.Queue(maxsize=depth)
        self._stop = _threading.Event()
        self._thread = _threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            while not self._stop.is_set():
                raw = b''
                while len(raw) < self._frame_size:
                    chunk = self._proc.stdout.read(self._frame_size - len(raw))
                    if not chunk:
                        self._queue.put(None)
                        return
                    raw += chunk
                # Materialise here (not on the consumer) so the copy overlaps
                # with downstream work too.
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    (self._height, self._width, 3)).copy()
                while not self._stop.is_set():
                    try:
                        self._queue.put(frame, timeout=0.5)
                        break
                    except _queue.Full:
                        continue
        except Exception:
            pass
        finally:
            if self._stop.is_set():
                return
            try:
                self._queue.put_nowait(None)
            except Exception:
                pass

    def read(self) -> Optional[np.ndarray]:
        """Next frame in order, or None once the stream is exhausted."""
        return self._queue.get()

    def close(self):
        self._stop.set()
        # Drain so a blocked producer can exit.
        try:
            while True:
                self._queue.get_nowait()
        except Exception:
            pass
        self._thread.join(timeout=5)


class PodcastZoomPipeline:
    """Main pipeline for podcast video auto-zoom processing."""

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.zoom_factor = config.get('zoom_factor', 2.0)
        self.smoothing_speed = config.get('smoothing_speed', 0.05)
        self.analysis_fps = config.get('analysis_fps', 10)
        self.max_faces = config.get('max_faces', 4)
        self.min_switch_duration = config.get('min_switch_duration', 0.5)
        self.mar_threshold = config.get('mar_threshold', 0.12)
        # Thumbnail generation is off by default (Hổ Báo Studio does not use it).
        self.generate_thumbnail = bool(config.get('generate_thumbnail', False))
        # 'ffmpeg' renders the crop/zoom inside FFmpeg (one process, no raw
        # frames through Python) — several times faster. 'opencv' is the
        # original path: frames are piped into Python and resized with
        # cv2.INTER_LANCZOS4. Both use a Lanczos scaler, so quality matches,
        # but they are different implementations and pixels differ slightly.
        self.render_engine = config.get('render_engine', 'ffmpeg')
        # Documents on screen win over faces (see _apply_documents).
        self.follow_documents = bool(config.get('follow_documents', True))

    def process(self,
                input_path: str,
                output_path: str,
                progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Process a podcast video: detect active speaker → zoom & center.

        Args:
            input_path: Path to input video file
            output_path: Path for output video file
            progress_callback: Callable receiving dict with 'phase', 'progress', 'message'

        Returns:
            Dict with processing stats
        """
        def report(phase, progress, message):
            if progress_callback:
                progress_callback({
                    'phase': phase,
                    'progress': progress,
                    'message': message
                })

        # ── Ensure FFmpeg is available ──
        ffmpeg_bin = ensure_ffmpeg()

        # ── Phase 1: Probe video properties via ffprobe ──
        report('init', 0, 'Probing video...')
        info = _probe_video(ffmpeg_bin, input_path)
        width = info['width']
        height = info['height']
        fps = info['fps']
        total_frames = info['total_frames']
        duration = info['duration']

        if width == 0 or height == 0 or fps == 0:
            raise ValueError(f"Invalid video properties: {width}x{height} @ {fps}fps")

        report('init', 0, f'Video: {width}x{height} @ {fps:.0f}fps, {duration:.1f}s ({total_frames} frames)')
        print(f"[INFO] Video: {width}x{height} @ {fps:.2f}fps, {total_frames} frames, {duration:.1f}s")

        start_time = time.time()

        # ── Phase 2: Analyze video via FFmpeg pipe ──
        face_detector = FaceDetector(max_faces=self.max_faces)
        doc_detector = DocumentDetector() if self.follow_documents else None
        doc_boxes: Dict[int, Any] = {}       # keyframe → DocBox or None
        face_counts: Dict[int, int] = {}     # keyframe → faces found

        min_switch_frames = max(1, int(self.min_switch_duration * fps))
        speaker_detector = SpeakerDetector(
            window_size=max(5, int(fps * 0.5)),
            mar_threshold=self.mar_threshold,
            min_switch_frames=min_switch_frames
        )

        # round, not int(): at 29.97 fps and analysis_fps 10, int() gave every 2nd frame (15 analyses/s, 50% more
        # face-model work than asked); round() gives every 3rd (~10/s) as configured
        analysis_interval = max(1, round(fps / self.analysis_fps))

        report('analyze', 0, 'Analyzing faces & active speaker...')

        # frame_idx → (center_x, center_y) of the crop target for that keyframe
        crop_targets: Dict[int, tuple] = {}
        last_known_center = (width / 2, height / 2)

        # Thumbnail data
        face_id_occurrences: Dict[int, list] = {}
        face_id_bboxes: Dict[int, list] = {}
        all_face_ids: set = set()

        _TOP_N = 5
        thumbnail_candidates: list = []

        # Open FFmpeg reader for analysis pass
        print(f"[INFO] Opening FFmpeg reader for analysis...")
        reader_proc = _open_ffmpeg_reader(ffmpeg_bin, input_path, width, height)
        reader = _PrefetchReader(reader_proc, width, height)

        frame_idx = 0
        analyzed_count = 0

        try:
            while True:
                frame = reader.read()
                if frame is None:
                    break

                timestamp = frame_idx / fps if fps > 0 else 0

                if frame_idx % analysis_interval == 0:
                    analysis = face_detector.detect_faces(frame, frame_idx, timestamp)
                    speaker_id = speaker_detector.update(analysis)
                    analyzed_count += 1

                    for face in analysis.faces:
                        face_id_occurrences.setdefault(face.face_id, []).append(face.center)
                        face_id_bboxes.setdefault(face.face_id, []).append(face.bbox)
                        all_face_ids.add(face.face_id)

                    if self.generate_thumbnail and len(analysis.faces) >= 1 and (total_frames == 0 or frame_idx > total_frames * 0.03):
                        avg_expr = sum(f.expression_score for f in analysis.faces) / len(analysis.faces)
                        multi_face_bonus = min(0.2, (len(analysis.faces) - 1) * 0.1)
                        frame_score = avg_expr + multi_face_bonus

                        faces_snapshot = [
                            {'center': f.center, 'bbox': f.bbox, 'face_id': f.face_id,
                             'expression_score': f.expression_score}
                            for f in analysis.faces
                        ]

                        if len(thumbnail_candidates) < _TOP_N:
                            thumbnail_candidates.append(
                                (frame_score, frame_idx, frame.copy(), faces_snapshot))
                            thumbnail_candidates.sort(key=lambda x: x[0], reverse=True)
                        elif frame_score > thumbnail_candidates[-1][0]:
                            thumbnail_candidates[-1] = (
                                frame_score, frame_idx, frame.copy(), faces_snapshot)
                            thumbnail_candidates.sort(key=lambda x: x[0], reverse=True)

                    # Crop target = active speaker's face center. When no clear
                    # speaker is found, hold the last position so the camera
                    # doesn't snap back to the frame center.
                    if speaker_id is not None:
                        for face in analysis.faces:
                            if face.face_id == speaker_id:
                                last_known_center = face.center
                                break
                    elif analysis.faces:
                        # No active speaker yet → frame the single face, or the
                        # centroid of all faces so everyone stays visible.
                        if len(analysis.faces) == 1:
                            last_known_center = analysis.faces[0].center
                        else:
                            cx = sum(f.center[0] for f in analysis.faces) / len(analysis.faces)
                            cy = sum(f.center[1] for f in analysis.faces) / len(analysis.faces)
                            last_known_center = (cx, cy)

                    crop_targets[frame_idx] = last_known_center
                    face_counts[frame_idx] = len(analysis.faces)
                    if doc_detector is not None:
                        doc_boxes[frame_idx] = doc_detector.detect(frame)

                if frame_idx % 100 == 0:
                    if total_frames > 0:
                        pct = int((frame_idx / total_frames) * 50)
                    else:
                        pct = min(49, analyzed_count // 2)
                    elapsed = time.time() - start_time
                    speed = frame_idx / elapsed if elapsed > 0 else 0
                    eta = (total_frames - frame_idx) / speed if (speed > 0 and total_frames > 0) else 0
                    report('analyze', pct,
                           f'Analyzing: frame {frame_idx}'
                           + (f'/{total_frames}' if total_frames > 0 else '')
                           + f' ({speed:.0f} fps, ETA {eta:.0f}s)')

                frame_idx += 1

        finally:
            reader.close()
            reader_proc.stdout.close()
            reader_proc.wait()

        # Update total_frames if we didn't know it
        if total_frames == 0:
            total_frames = frame_idx
        actual_frames = frame_idx

        face_detector.close()

        print(f"[INFO] Analysis done: {actual_frames} frames read, "
              f"{len(crop_targets)} keyframes")
        report('analyze', 50,
               f'Analysis complete. {len(crop_targets)} keyframes detected.')

        # Documents and face-less stretches override the face target (adds a zoom level per keyframe)
        crop_targets = self._apply_documents(crop_targets, face_counts, doc_boxes, fps, width, height)

        # ── Phase 3: Interpolate crop targets for all frames ──
        all_crop_centers = self._interpolate_targets(crop_targets, actual_frames, width, height)

        # ── Phase 4: Render output video via FFmpeg pipe ──
        report('render', 50, 'Rendering zoomed video with audio...')

        video_processor = VideoProcessor(
            zoom_factor=self.zoom_factor,
            smoothing_speed=self.smoothing_speed
        )

        # Render fps: derive from actual decoded frame count / real duration
        # rather than the probed nominal fps (r_frame_rate). Nominal fps is
        # often a rounded/VFR-agnostic value (e.g. reports 30 for a 29.97 or
        # variable-frame-rate source); writing the raw-frame stream at that
        # assumed-constant rate makes the encoded video's total presentation
        # time drift from the audio track's real length. The drift is
        # sub-frame on short clips but accumulates to a noticeable A/V offset
        # on long ones. Using actual_frames/duration keeps video length
        # exactly matched to the audio being muxed in below.
        render_fps = actual_frames / duration if duration > 0 else fps
        print(f"[INFO] Render fps: {render_fps:.6f} (nominal probe fps was {fps:.6f})")

        if self.render_engine == 'ffmpeg':
            self._render_via_ffmpeg(
                ffmpeg_bin, input_path, output_path,
                all_crop_centers, video_processor,
                width, height, actual_frames, render_fps, report)
        else:
            self._render_via_opencv(
                ffmpeg_bin, input_path, output_path,
                all_crop_centers, video_processor,
                width, height, actual_frames, render_fps, report)

        # ── Phase 5: Generate thumbnail (only when requested) ──
        thumbnail_path = None
        if not self.generate_thumbnail:
            pass
        elif thumbnail_candidates:
            best_score, best_idx, best_frame, best_faces = thumbnail_candidates[0]
            expr_scores = ', '.join(f'{f["expression_score"]:.2f}' for f in best_faces)
            print(f"[THUMB] Best frame #{best_idx} (score={best_score:.3f}, "
                  f"faces={len(best_faces)}, expr=[{expr_scores}])")

            thumbnail_path = os.path.splitext(output_path)[0] + '_thumbnail.jpg'

            thumb_centers = [f['center'] for f in best_faces]
            thumb_bboxes = [f['bbox'] for f in best_faces]

            if thumb_centers:
                try:
                    generate_split_thumbnail(
                        best_frame, thumb_centers, thumb_bboxes,
                        thumbnail_path,
                        output_width=width, output_height=height,
                    )
                    print(f"[OK] Thumbnail saved: {thumbnail_path}")
                except Exception as thumb_err:
                    print(f"[WARN] Thumbnail generation failed: {thumb_err}")
                    import traceback
                    traceback.print_exc()
                    thumbnail_path = None
            else:
                thumbnail_path = None
        else:
            print(f"[INFO] No thumbnail candidates found")

        # ── Done ──
        total_time = time.time() - start_time
        report('done', 100, f'Complete! Processed in {total_time:.1f}s')

        return {
            'duration': duration,
            'total_frames': actual_frames,
            'processing_time': total_time,
            'output_path': output_path,
            'thumbnail_path': thumbnail_path,
        }

    def _render_via_opencv(self, ffmpeg_bin, input_path, output_path,
                           all_crop_centers, video_processor,
                           width, height, actual_frames, render_fps, report):
        """Original render path: raw frames are piped into Python, cropped and
        resized with cv2.INTER_LANCZOS4, then piped back out to FFmpeg."""
        # FFmpeg writer: receives raw BGR frames on stdin, muxes with original audio.
        # No -movflags +faststart: that flag writes a temp file to %TEMP% (C drive).
        # Output goes directly to E drive with no intermediate temp files.
        ffmpeg_write_cmd = [
            ffmpeg_bin, '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{width}x{height}',
            '-r', f'{render_fps:.6f}',
            '-i', '-',
            '-i', input_path,
            *video_encode_args(ffmpeg_bin, crf=20),
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-map', '0:v:0',
            '-map', '1:a:0?',
            '-shortest',
            output_path
        ]

        print(f"[FFmpeg] Starting render writer...")
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_write_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        _stderr_chunks = []

        def _drain_stderr():
            try:
                while True:
                    chunk = ffmpeg_proc.stderr.read(4096)
                    if not chunk:
                        break
                    _stderr_chunks.append(chunk)
            except Exception:
                pass

        _stderr_thread = _threading.Thread(target=_drain_stderr, daemon=True)
        _stderr_thread.start()

        # Open second FFmpeg reader for render pass
        print(f"[FFmpeg] Opening FFmpeg reader for render pass...")
        render_reader = _open_ffmpeg_reader(ffmpeg_bin, input_path, width, height)
        render_prefetch = _PrefetchReader(render_reader, width, height)

        frame_idx = 0
        render_start = time.time()

        try:
            while True:
                frame = render_prefetch.read()
                if frame is None:
                    break

                target = all_crop_centers.get(frame_idx, (width / 2, height / 2, float(self.zoom_factor)))
                crop = video_processor.compute_crop(target, width, height)
                zoomed_frame = video_processor.apply_crop(frame, crop)

                try:
                    # Write the array's own buffer rather than a tobytes() copy
                    # — same bytes, one less 6 MB memcpy per frame. cv2.resize
                    # already returns a C-contiguous array, so this is a no-op
                    # guard rather than a copy.
                    ffmpeg_proc.stdin.write(np.ascontiguousarray(zoomed_frame).data)
                except BrokenPipeError:
                    _stderr_thread.join(timeout=5)
                    stderr_text = b''.join(_stderr_chunks).decode('utf-8', errors='replace')
                    raise RuntimeError(f"FFmpeg pipe broke: {stderr_text[-500:]}")

                if frame_idx % 100 == 0:
                    pct = 50 + int((frame_idx / actual_frames) * 48) if actual_frames > 0 else 50
                    elapsed = time.time() - render_start
                    speed = (frame_idx + 1) / elapsed if elapsed > 0 else 0
                    eta = (actual_frames - frame_idx) / speed if (speed > 0 and actual_frames > 0) else 0
                    report('render', pct,
                           f'Rendering: {frame_idx}/{actual_frames} frames '
                           f'({speed:.0f} fps, ETA {eta:.0f}s)')

                frame_idx += 1

        finally:
            render_prefetch.close()
            render_reader.stdout.close()
            render_reader.wait()

            ffmpeg_proc.stdin.close()
            ffmpeg_proc.wait(timeout=300)
            _stderr_thread.join(timeout=10)
            stderr_out = b''.join(_stderr_chunks).decode('utf-8', errors='replace')
            if ffmpeg_proc.returncode != 0:
                print(f"[WARN] FFmpeg exited with code {ffmpeg_proc.returncode}")
                print(f"   stderr: {stderr_out[-500:]}")
            else:
                print(f"[OK] FFmpeg render complete")

    def _render_via_ffmpeg(self, ffmpeg_bin, input_path, output_path,
                           all_crop_centers, video_processor,
                           width, height, actual_frames, render_fps, report):
        """Render the crop/zoom entirely inside FFmpeg.

        The camera motion (smoothing, dead-zone, adaptive speed) is identical
        to the OpenCV path — it is pure math over the crop targets, so every
        frame's crop rectangle is precomputed here with the same
        VideoProcessor, then replayed inside FFmpeg via a `sendcmd` script that
        drives the `crop` filter. No raw frame ever crosses into Python, which
        is where the OpenCV path spends most of its time.

        The scaler is FFmpeg's Lanczos rather than cv2.INTER_LANCZOS4 — same
        algorithm family and equivalent quality, but a different
        implementation, so pixels differ slightly from the OpenCV path.
        """
        crop_w = int(width / self.zoom_factor)
        crop_h = int(height / self.zoom_factor)

        # ── Precompute every frame's crop rectangle (cheap, no pixels) ──
        cmd_path = os.path.splitext(output_path)[0] + '_crop.cmds'
        prev = None
        written = 0
        with open(cmd_path, 'w', encoding='ascii') as fh:
            for idx in range(actual_frames):
                target = all_crop_centers.get(idx, (width / 2, height / 2, float(self.zoom_factor)))
                crop = video_processor.compute_crop(target, width, height)

                # Crop size follows the zoom (documents zoom less); even sizes
                # for yuv420. Mirror VideoProcessor.apply_crop's rounding.
                cw = min(width, int(crop.width) // 2 * 2)
                ch = min(height, int(crop.height) // 2 * 2)
                x = max(0, int(crop.center_x - crop.width / 2))
                y = max(0, int(crop.center_y - crop.height / 2))
                x = min(x, width - cw)
                y = min(y, height - ch)

                # Only emit when the rectangle actually changes — the dead-zone
                # keeps the camera still for long stretches, so this cuts the
                # script down a lot without changing any frame.
                if (x, y, cw, ch) == prev:
                    continue
                t = idx / render_fps if render_fps > 0 else 0.0
                if prev is None or (cw, ch) != prev[2:]:
                    fh.write(f"{t:.6f} crop w {cw}, crop h {ch}, crop x {x}, crop y {y};\n")
                else:
                    fh.write(f"{t:.6f} crop x {x}, crop y {y};\n")
                prev = (x, y, cw, ch)
                written += 1

        print(f"[FFmpeg] Crop script: {written} camera moves over "
              f"{actual_frames} frames -> {cmd_path}")

        # Filtergraph paths need ':' and '\' escaped; forward slashes are fine
        # on Windows and avoid a pile of backslash escaping.
        esc = cmd_path.replace('\\', '/').replace(':', '\\:')
        vf = (f"sendcmd=f='{esc}',"
              f"crop={crop_w}:{crop_h}:0:0,"
              f"scale={width}:{height}:flags=lanczos")

        cmd = [
            ffmpeg_bin, '-y',
            '-i', input_path,
            '-vf', vf,
            *video_encode_args(ffmpeg_bin, crf=20),
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-map', '0:v:0',
            '-map', '0:a:0?',
            '-shortest',
            '-progress', 'pipe:1',
            '-nostats',
            output_path,
        ]

        print(f"[FFmpeg] Rendering natively (crop+scale+encode in one pass)...")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                bufsize=1, universal_newlines=True)

        _stderr_chunks = []

        def _drain_stderr():
            try:
                for line in proc.stderr:
                    _stderr_chunks.append(line)
            except Exception:
                pass

        _stderr_thread = _threading.Thread(target=_drain_stderr, daemon=True)
        _stderr_thread.start()

        render_start = time.time()
        try:
            for line in proc.stdout:
                if not line.startswith('frame='):
                    continue
                try:
                    done = int(line.split('=', 1)[1].strip())
                except ValueError:
                    continue
                elapsed = time.time() - render_start
                speed = done / elapsed if elapsed > 0 else 0
                eta = (actual_frames - done) / speed if (speed > 0 and actual_frames > 0) else 0
                pct = 50 + int((done / actual_frames) * 48) if actual_frames > 0 else 50
                report('render', min(pct, 98),
                       f'Rendering: {done}/{actual_frames} frames '
                       f'({speed:.0f} fps, ETA {eta:.0f}s)')
        finally:
            proc.wait(timeout=600)
            _stderr_thread.join(timeout=10)
            stderr_out = ''.join(_stderr_chunks)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg render failed (exit {proc.returncode}): {stderr_out[-800:]}")
            print(f"[OK] FFmpeg render complete "
                  f"({actual_frames / max(time.time() - render_start, 1e-9):.0f} fps)")
            try:
                os.remove(cmd_path)
            except OSError:
                pass

    def _apply_documents(self, crop_targets, face_counts, doc_boxes, fps, width, height):
        """Turn face targets (x, y) into camera targets (x, y, zoom).

        * A document seen on screen for at least ~0.5 s (gaps up to ~1.2 s bridged, since a frame now and then
          misses its border) takes the camera: centre on it, zoom so the whole box fits with a ~15% margin, never
          more than the normal zoom. The box used is the largest one seen within +-1 s: inside a web page the
          detector sometimes only catches an inner panel.
        * No face at all for ~1 s and no document: full frame (zoom 1) - a full-screen document or footage.
        * Otherwise the face target with the normal zoom.
        """
        keys = sorted(crop_targets)
        z0 = float(self.zoom_factor)
        if not keys:
            return crop_targets
        step = (keys[1] - keys[0]) if len(keys) > 1 else 1
        per_sec = max(1.0, fps / step)                      # keyframes per second
        min_run = int(round(0.5 * per_sec))
        max_gap = int(round(1.2 * per_sec))
        win = int(round(1.0 * per_sec))
        noface_run = int(round(1.0 * per_sec))

        has = [doc_boxes.get(k) is not None for k in keys]
        hits = [i for i, h in enumerate(has) if h]
        for a, b in zip(hits, hits[1:]):                    # bridge short gaps between detections
            if 1 < b - a <= max_gap + 1:
                for j in range(a + 1, b):
                    has[j] = True
        i = 0
        while i < len(has):                                 # keep only runs long enough to be a real document
            if has[i]:
                j = i
                while j < len(has) and has[j]:
                    j += 1
                if j - i < min_run:
                    for q in range(i, j):
                        has[q] = False
                i = j
            else:
                i += 1

        noface = [face_counts.get(k, 1) == 0 for k in keys]
        out = {}
        n_doc = n_wide = 0
        for i, k in enumerate(keys):
            if has[i]:
                near = [doc_boxes[keys[j]] for j in range(max(0, i - win), min(len(keys), i + win + 1))
                        if doc_boxes.get(keys[j]) is not None]
                if near:
                    anchor = doc_boxes.get(k) or near[len(near) // 2]
                    same = [b for b in near if b.iou(anchor) > 0] or [anchor]
                    box = max(same, key=lambda b: b.w * b.h)
                    z = min(z0, width / (box.w * 1.15), height / (box.h * 1.15))
                    out[k] = (box.center[0], box.center[1], max(1.0, z))
                    n_doc += 1
                    continue
            lo, hi = max(0, i - noface_run // 2), min(len(keys), i + noface_run // 2 + 1)
            if hi - lo >= noface_run and all(noface[lo:hi]):
                out[k] = (width / 2, height / 2, 1.0)
                n_wide += 1
                continue
            out[k] = (crop_targets[k][0], crop_targets[k][1], z0)
        if n_doc or n_wide:
            print(f"[INFO] Keyframes: {n_doc} follow a document, {n_wide} full frame (no face), "
                  f"{len(keys) - n_doc - n_wide} follow faces")
        return out

    def _interpolate_targets(self, crop_targets, total_frames, width, height):
        """
        Interpolate crop centers between keyframes for smooth movement.

        Targets are (x, y) tuples — the active speaker's face center. We
        linearly interpolate between consecutive keyframes; the per-frame
        EMA in VideoProcessor then smooths the actual camera motion.
        """
        all_centers = {}
        keyframes = sorted(crop_targets.keys())

        if not keyframes:
            center = (width / 2, height / 2, float(self.zoom_factor))
            return {i: center for i in range(total_frames)}

        for i in range(total_frames):
            if i in crop_targets:
                all_centers[i] = crop_targets[i]
                continue

            prev_kf = max((k for k in keyframes if k <= i), default=keyframes[0])
            next_kf = min((k for k in keyframes if k >= i), default=keyframes[-1])

            if prev_kf == next_kf:
                all_centers[i] = crop_targets[prev_kf]
                continue

            t = (i - prev_kf) / (next_kf - prev_kf)
            p = crop_targets[prev_kf]
            n = crop_targets[next_kf]
            all_centers[i] = tuple(a + (b - a) * t for a, b in zip(p, n))

        return all_centers
