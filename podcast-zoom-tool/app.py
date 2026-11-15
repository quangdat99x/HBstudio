"""
Podcast Auto-Zoom Tool - Flask Web Application
Upload podcast videos → auto-detect active speaker → output zoomed videos
Supports batch processing: several clips are processed at once (as many as the machine's CPU budget allows,
E:/Tool/cpu_budget.json), at below-normal priority so the user's own apps stay responsive.
"""

import os
import uuid
import json
import time
import shutil
import threading
import logging
import traceback
import queue as queue_module
import tempfile

# Hide cmd/console windows for every subprocess call on Windows.
# Idempotent — safe even if run.pyw already imported it.
from core import _no_console  # noqa: F401

from flask import Flask, render_template, request, jsonify, send_file, Response
from core.pipeline import PodcastZoomPipeline

# Use same log file as run.pyw
BASE_DIR_EARLY = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR_EARLY, 'debug.log'),
                            encoding='utf-8', mode='w'),
    ]
)
logger = logging.getLogger('PodcastZoom.app')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB max upload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

TEMP_DIR = os.path.join(BASE_DIR, 'tmp')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Redirect ALL temp files to E drive — both Python-level and subprocesses (FFmpeg, Whisper).
# Without this, Werkzeug buffers large video uploads to %TEMP% on C drive,
# and FFmpeg/Whisper also write intermediate files there.
tempfile.tempdir = TEMP_DIR
os.environ['TEMP'] = TEMP_DIR
os.environ['TMP'] = TEMP_DIR


def _startup_cleanup():
    """Delete orphaned files left over from previous server sessions."""
    for folder in (UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR):
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
                logger.info(f"[startup_cleanup] Removed orphan: {fpath}")
            except Exception:
                pass


_startup_cleanup()

# In-memory job tracking
jobs = {}
job_order = []  # Ordered list of job IDs

# User-selected output directory for auto-save
output_save_dir = None

# Processing queue, several workers.
# One clip keeps ~2.5 real CPU cores busy (FFmpeg decode + the MediaPipe face model, which is CPU-only on Windows),
# so the machine runs (cores - cores kept for the user) / 2.5 clips at once, between 1 and 8.
CORES_PER_JOB = 2.5


def _cpu_budget() -> dict:
    path = os.path.join(os.path.dirname(BASE_DIR), 'cpu_budget.json')
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _physical_cores() -> int:
    """Real CPU cores (i9-10900: 10). Hyper-threading doubles the logical CPUs Windows shows, but the second thread
    of a core adds only ~15-30% on heavy work, so budgets count cores, not threads."""
    try:
        import subprocess
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum"],
                             capture_output=True, text=True, timeout=20,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return max(1, int(out.strip()))
    except Exception:
        return max(1, (os.cpu_count() or 2) // 2)


def _zoom_workers() -> int:
    """`zoom_workers` in cpu_budget.json fixes the number; otherwise (cores - reserve_cores) / 2.5, 1..8.
    The old ceiling of 4 was sized for the i9-10900 (10 cores); on the i7-14700 (20 cores) it left the CPU at
    ~30% during the analysis pass, which is where a clip spends most of its time."""
    budget = _cpu_budget()
    if budget.get('zoom_workers'):
        try:
            return max(1, min(12, int(budget['zoom_workers'])))
        except (TypeError, ValueError):
            pass
    reserve = float(budget.get('reserve_cores', 2))
    return max(1, min(8, int((_physical_cores() - reserve) / CORES_PER_JOB)))


def _below_normal_priority() -> None:
    """Run this process (and every FFmpeg it starts: Windows children inherit below-normal) under the user's apps."""
    if os.name != 'nt':
        return
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # declare the types: without them the 64-bit pseudo-handle of GetCurrentProcess() is cut to 32 bits and the
        # call fails silently (the process stayed at Normal)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k32.SetPriorityClass.restype = wintypes.BOOL
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:
        pass


_below_normal_priority()
ZOOM_WORKERS = _zoom_workers()
_job_queue = queue_module.Queue()


def _queue_worker():
    """Process jobs from the queue (ZOOM_WORKERS of these run side by side)."""
    while True:
        job_id = _job_queue.get()
        if job_id is None:
            break
        try:
            _process_job(job_id)
        finally:
            _job_queue.task_done()


for _n in range(ZOOM_WORKERS):
    threading.Thread(target=_queue_worker, name=f"zoom-worker-{_n}", daemon=True).start()
logger.info(f"[startup] {ZOOM_WORKERS} zoom worker(s), {_physical_cores()} cores / {os.cpu_count()} threads, below-normal priority")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/set-output-dir', methods=['POST'])
def set_output_dir():
    """Set the output directory for auto-saving processed videos."""
    global output_save_dir
    data = request.json
    path = data.get('path', '').strip()
    if path and os.path.isdir(path):
        output_save_dir = path
        return jsonify({'success': True, 'path': output_save_dir})
    return jsonify({'success': False, 'error': 'Invalid directory'}), 400


@app.route('/api/upload', methods=['POST'])
def upload_video():
    """Handle video upload and add to processing queue."""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Validate extension
    allowed = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({'error': f'Unsupported format: {ext}'}), 400

    # Save uploaded file
    job_id = str(uuid.uuid4())[:8]
    input_filename = f"{job_id}_input{ext}"
    input_path = os.path.join(UPLOAD_DIR, input_filename)
    file.save(input_path)

    output_filename = f"{job_id}_zoomed.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    # Parse config from form
    config = {
        'zoom_factor': float(request.form.get('zoom_factor', 2.0)),
        'smoothing_speed': float(request.form.get('smoothing_speed', 0.05)),
        'analysis_fps': int(request.form.get('analysis_fps', 10)),
        'max_faces': int(request.form.get('max_faces', 4)),
        'min_switch_duration': float(request.form.get('min_switch_duration', 0.5)),
        'mar_threshold': float(request.form.get('mar_threshold', 0.12)),
        'generate_thumbnail': request.form.get('generate_thumbnail', '0') in ('1', 'true', 'on'),
    }

    # Initialize job
    jobs[job_id] = {
        'status': 'queued',
        'progress': 0,
        'message': 'Waiting in queue...',
        'phase': 'queued',
        'input_path': input_path,
        'output_path': output_path,
        'output_filename': output_filename,
        'original_filename': file.filename,
        'config': config,
        'created_at': time.time(),
        'error': None,
        'saved_path': None,
        'thumbnail_path': None,
    }
    job_order.append(job_id)

    # Add to processing queue (worker will pick it up sequentially)
    _job_queue.put(job_id)

    return jsonify({'job_id': job_id, 'status': 'queued'})


@app.route('/api/enqueue-path', methods=['POST'])
def enqueue_path():
    """Queue a video that is already on disk (no upload copy). JSON:
    {path, output_path (optional, final file), config: {...}}. The input file is never deleted;
    the result is moved to output_path when given, otherwise saved like an upload."""
    data = request.json or {}
    path = str(data.get('path') or '').strip()
    if not path or not os.path.isfile(path):
        return jsonify({'error': f'Không thấy file: {path}'}), 400
    ext = os.path.splitext(path)[1].lower()
    if ext not in {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}:
        return jsonify({'error': f'Unsupported format: {ext}'}), 400
    cfg_in = data.get('config') or {}
    config = {
        'zoom_factor': float(cfg_in.get('zoom_factor', 2.0)),
        'smoothing_speed': float(cfg_in.get('smoothing_speed', 0.05)),
        'analysis_fps': int(cfg_in.get('analysis_fps', 10)),
        'max_faces': int(cfg_in.get('max_faces', 4)),
        'min_switch_duration': float(cfg_in.get('min_switch_duration', 0.5)),
        'mar_threshold': float(cfg_in.get('mar_threshold', 0.12)),
        'generate_thumbnail': bool(cfg_in.get('generate_thumbnail', False)),
    }
    job_id = str(uuid.uuid4())[:8]
    output_filename = f"{job_id}_zoomed.mp4"
    final_output = str(data.get('output_path') or '').strip() or None
    jobs[job_id] = {
        'status': 'queued', 'progress': 0, 'message': 'Waiting in queue...', 'phase': 'queued',
        'input_path': path, 'output_path': os.path.join(OUTPUT_DIR, output_filename),
        'output_filename': output_filename, 'original_filename': os.path.basename(path),
        'config': config, 'created_at': time.time(), 'error': None, 'saved_path': None,
        'thumbnail_path': None, 'delete_input': False, 'final_output': final_output,
    }
    job_order.append(job_id)
    _job_queue.put(job_id)
    logger.info(f"[{job_id}] Queued by path: {path} -> {final_output or '(auto-save)'}")
    return jsonify({'job_id': job_id, 'status': 'queued'})


def _safe_path(original_path: str) -> str:
    """
    OpenCV on Windows cannot open files with Unicode/non-ASCII paths.
    Return a safe ASCII-only copy of the file in the uploads dir.
    If the path is already ASCII-safe, return it unchanged.
    """
    try:
        original_path.encode('ascii')
        return original_path  # Already ASCII-safe
    except UnicodeEncodeError:
        pass

    ext = os.path.splitext(original_path)[1].lower()
    safe_name = f"safe_{uuid.uuid4().hex[:8]}{ext}"
    safe_path = os.path.join(UPLOAD_DIR, safe_name)
    shutil.copy2(original_path, safe_path)
    logger.info(f"[safe_path] Copied Unicode path to ASCII path: {safe_name}")
    return safe_path


def _process_job(job_id):
    """Process a single job (called by queue worker thread)."""
    job = jobs.get(job_id)
    if not job:
        return

    job['status'] = 'processing'
    job['message'] = 'Starting processing...'

    safe_input = None

    def on_progress(data):
        job['phase'] = data.get('phase', '')
        job['progress'] = data.get('progress', 0)
        job['message'] = data.get('message', '')
        logger.debug(f"[{job_id}] {data.get('phase','')} {data.get('progress',0)}% - {data.get('message','')}")

    try:
        # Fix: OpenCV cannot handle Unicode paths on Windows
        safe_input = _safe_path(job['input_path'])
        if safe_input != job['input_path']:
            logger.info(f"[{job_id}] Using safe ASCII path for OpenCV: {safe_input}")

        logger.info(f"[{job_id}] Starting pipeline: {job['original_filename']}")
        pipeline = PodcastZoomPipeline(config=job['config'])
        result = pipeline.process(
            input_path=safe_input,
            output_path=job['output_path'],
            progress_callback=on_progress
        )
        job['result'] = result
        job['thumbnail_path'] = result.get('thumbnail_path')
        logger.info(f"[{job_id}] Complete! time={result['processing_time']:.1f}s")

        # Path jobs go straight to their final location; uploads use the auto-save folder.
        # Save BEFORE reporting 'complete': callers (Hổ Báo Studio) check the output file as soon as the status flips.
        if job.get('final_output'):
            _move_final(job_id)
        else:
            _auto_save(job_id)
        job['status'] = 'complete'
        job['progress'] = 100
        job['message'] = f"Done! Processed in {result['processing_time']:.1f}s"

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        job['message'] = f'Error: {str(e)}'
        logger.error(f"[{job_id}] Pipeline error: {e}")
        logger.error(traceback.format_exc())

    finally:
        # Delete the safe copy if we made one
        if safe_input and safe_input != job['input_path']:
            try:
                os.remove(safe_input)
            except Exception:
                pass
        # Delete the uploaded input — no longer needed after processing (never for path jobs)
        try:
            if job.get('delete_input', True) and os.path.exists(job['input_path']):
                os.remove(job['input_path'])
                logger.info(f"[{job_id}] Deleted input: {job['input_path']}")
        except Exception:
            pass


def _move_final(job_id):
    """Move the rendered file to the caller-specified final path (path jobs)."""
    job = jobs.get(job_id)
    if not job or not job.get('final_output'):
        return
    try:
        dst = job['final_output']
        os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
        if os.path.exists(job['output_path']):
            shutil.move(job['output_path'], dst)
            job['saved_path'] = dst
            logger.info(f"[{job_id}] Saved to {dst}")
    except Exception as e:
        job['saved_path'] = f"Save error: {e}"
        logger.error(f"[{job_id}] Final move failed: {e}")


def _auto_save(job_id):
    """Auto-copy the processed video and thumbnail to the user's chosen output directory."""
    global output_save_dir
    job = jobs.get(job_id)
    if not job or not output_save_dir:
        return

    try:
        if os.path.isdir(output_save_dir) and os.path.exists(job['output_path']):
            original_name = os.path.splitext(job['original_filename'])[0]
            save_name = f"{original_name}_zoomed.mp4"
            save_path = os.path.join(output_save_dir, save_name)

            # Handle duplicate filenames
            counter = 1
            while os.path.exists(save_path):
                save_name = f"{original_name}_zoomed_{counter}.mp4"
                save_path = os.path.join(output_save_dir, save_name)
                counter += 1

            shutil.copy2(job['output_path'], save_path)
            job['saved_path'] = save_path

            # Also copy thumbnail if it exists
            thumb_src = job.get('thumbnail_path')
            if thumb_src and os.path.exists(thumb_src):
                thumb_save_name = os.path.splitext(save_name)[0] + '_thumbnail.jpg'
                thumb_save_path = os.path.join(output_save_dir, thumb_save_name)
                shutil.copy2(thumb_src, thumb_save_path)
    except Exception as e:
        job['saved_path'] = f"Save error: {e}"


@app.route('/api/status/<job_id>')
def job_status(job_id):
    """Get job processing status."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    job = jobs[job_id]
    return jsonify({
        'job_id': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'message': job['message'],
        'phase': job['phase'],
        'error': job.get('error'),
        'saved_path': job.get('saved_path'),
        'original_filename': job.get('original_filename'),
    })


@app.route('/api/queue-status')
def queue_status():
    """Get status of all jobs in order."""
    result = []
    for jid in job_order:
        job = jobs.get(jid)
        if job:
            result.append({
                'job_id': jid,
                'status': job['status'],
                'progress': job['progress'],
                'message': job['message'],
                'phase': job['phase'],
                'error': job.get('error'),
                'saved_path': job.get('saved_path'),
                'original_filename': job.get('original_filename'),
            })
    return jsonify({
        'jobs': result,
        'output_dir': output_save_dir,
        'workers': ZOOM_WORKERS,          # clips processed at once: callers can keep this many queued
    })


@app.route('/api/stream/<job_id>')
def stream_status(job_id):
    """SSE endpoint for real-time progress updates."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    def generate():
        last_msg = ''
        while True:
            job = jobs.get(job_id)
            if not job:
                break

            msg = json.dumps({
                'job_id': job_id,
                'status': job['status'],
                'progress': job['progress'],
                'message': job['message'],
                'phase': job['phase'],
                'error': job.get('error'),
                'saved_path': job.get('saved_path'),
            })

            if msg != last_msg:
                yield f"data: {msg}\n\n"
                last_msg = msg

            if job['status'] in ('complete', 'error'):
                break

            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/download/<job_id>')
def download_result(job_id):
    """Download the processed video."""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = jobs[job_id]
    if job['status'] != 'complete':
        return jsonify({'error': 'Job not complete'}), 400

    if not os.path.exists(job['output_path']):
        return jsonify({'error': 'Output file not found'}), 404

    original_name = os.path.splitext(job['original_filename'])[0]
    download_name = f"{original_name}_zoomed.mp4"
    output_path = job['output_path']
    thumbnail_path = job.get('thumbnail_path')

    response = send_file(
        output_path,
        as_attachment=True,
        download_name=download_name,
        mimetype='video/mp4'
    )

    # Schedule deletion after response is sent
    @response.call_on_close
    def _cleanup():
        for p in (output_path, thumbnail_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                    logger.info(f"[{job_id}] Deleted after download: {p}")
                except Exception:
                    pass

    return response


@app.route('/api/clear-queue', methods=['POST'])
def clear_queue():
    """Clear completed/errored jobs from the queue."""
    global job_order
    to_remove = [jid for jid in job_order if jobs.get(jid, {}).get('status') in ('complete', 'error')]
    for jid in to_remove:
        job_order.remove(jid)
        # Clean up files
        job = jobs.pop(jid, None)
        if job:
            try:
                if os.path.exists(job.get('input_path', '')):
                    os.remove(job['input_path'])
                if os.path.exists(job.get('output_path', '')):
                    os.remove(job['output_path'])
            except Exception:
                pass
    return jsonify({'success': True, 'removed': len(to_remove)})


if __name__ == '__main__':
    print("\n  Podcast Auto-Zoom Tool")
    print("=" * 40)

    # Pre-download dependencies at startup
    print("Checking dependencies...")
    from core.ffmpeg_utils import ensure_ffmpeg
    from core.face_detector import ensure_model
    try:
        ffmpeg_path = ensure_ffmpeg()
        print(f"[OK] FFmpeg: {ffmpeg_path}")
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        exit(1)
    try:
        model_path = ensure_model()
        print(f"[OK] FaceLandmarker model: {model_path}")
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        exit(1)

    print("=" * 40)
    print("Open: http://localhost:5555")
    print("=" * 40 + "\n")
    app.run(host='0.0.0.0', port=5555, debug=False)
