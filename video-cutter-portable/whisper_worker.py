"""
whisper_worker.py — Chạy Whisper trong subprocess riêng, cách ly hoàn toàn
khỏi pywebview để tránh crash.

Giao tiếp với app.py qua file JSON status.

Usage:
    python whisper_worker.py <video_path> <model_name> <language> <status_file> [ffmpeg_cmd]
"""

import json
import sys
import os
import traceback


def _register_nvidia_dll_dirs():
    """
    On Windows, ctranslate2 (used by faster-whisper) loads CUDA runtime
    libraries (cublas64_12.dll, cudnn64_9.dll, ...) via the system DLL
    search path. Having an up-to-date GPU *driver* is not enough — these
    runtime libraries normally come from the CUDA Toolkit / cuDNN install.

    If the user installed the `nvidia-cublas-cu12` / `nvidia-cudnn-cu12`
    pip wheels (which bundle these DLLs under site-packages/nvidia/*/bin),
    register those folders with os.add_dll_directory so Windows can find
    them — otherwise GPU init silently fails with
    "Library cublas64_12.dll is not found or cannot be loaded" and the
    tool falls back to CPU.
    """
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    try:
        import site
        roots = set()
        for p in site.getsitepackages() + [site.getusersitepackages()]:
            roots.add(p)
        try:
            import sysconfig
            roots.add(sysconfig.get_paths().get("purelib", ""))
        except Exception:
            pass

        path_dirs = []
        for root in roots:
            nvidia_dir = os.path.join(root, "nvidia")
            if not os.path.isdir(nvidia_dir):
                continue
            for pkg in os.listdir(nvidia_dir):
                bin_dir = os.path.join(nvidia_dir, pkg, "bin")
                if os.path.isdir(bin_dir):
                    try:
                        os.add_dll_directory(bin_dir)
                    except Exception:
                        pass
                    path_dirs.append(bin_dir)

        # ctranslate2 loads the CUDA runtime DLLs through the OS loader, which
        # (unlike ctypes) does not honor os.add_dll_directory — it searches PATH.
        # Prepend the wheel bin dirs to PATH so cublas/cudnn are found.
        if path_dirs:
            existing = os.environ.get("PATH", "")
            os.environ["PATH"] = os.pathsep.join(path_dirs + [existing])
    except Exception:
        pass


_register_nvidia_dll_dirs()


def fmt_timestamp(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_status(status_file: str, data: dict):
    """Atomically write status to file."""
    tmp = status_file + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        # Atomic replace
        if os.path.exists(status_file):
            os.remove(status_file)
        os.rename(tmp, status_file)
    except Exception:
        # Fallback: direct write
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass


def get_duration(video_path: str, ffmpeg_cmd: str = "ffmpeg") -> float:
    import subprocess
    try:
        # Only the file name: the bundled path (...\ffmpeg\ffmpeg.exe) contains "ffmpeg" twice
        ffprobe = os.path.join(os.path.dirname(ffmpeg_cmd), os.path.basename(ffmpeg_cmd).replace("ffmpeg", "ffprobe"))
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", video_path],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def main():
    if len(sys.argv) < 5:
        print("Usage: whisper_worker.py <video_path> <model_name> <language> <status_file> [ffmpeg_cmd]")
        sys.exit(1)

    video_path = sys.argv[1]
    model_name = sys.argv[2]
    language = sys.argv[3]
    status_file = sys.argv[4]
    ffmpeg_cmd = sys.argv[5] if len(sys.argv) > 5 else "ffmpeg"

    # Check stop file (created by parent to signal stop)
    stop_file = status_file + ".stop"

    def should_stop():
        return os.path.exists(stop_file)

    def upd(data: dict):
        write_status(status_file, data)

    upd({"status": "running", "progress": 0, "message": f"Đang tải model {model_name}...",
         "error": None, "model": model_name, "segments_count": 0, "segments": []})

    try:
        # Set env vars BEFORE importing ctranslate2/torch to prevent thread conflicts
        os.environ["OMP_NUM_THREADS"] = "4"
        os.environ["CT2_VERBOSE"] = "-1"

        from faster_whisper import WhisperModel

        if should_stop():
            upd({"status": "idle", "progress": 0, "message": "Đã dừng.",
                 "error": None, "model": model_name, "segments_count": 0, "segments": []})
            return

        # --- GPU Detection ---
        device = "cpu"
        compute_type = "int8"

        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
        except Exception:
            pass

        if device == "cpu":
            try:
                import ctranslate2
                cuda_types = ctranslate2.get_supported_compute_types("cuda")
                if cuda_types:
                    device = "cuda"
                    compute_type = "float16"
            except Exception:
                pass

        device_label = device.upper()
        upd({"status": "running", "progress": 0,
             "message": f"Đang tải model {model_name} ({device_label})...",
             "error": None, "model": model_name, "segments_count": 0, "segments": []})
        print(f"[Whisper Worker] Loading model {model_name} on {device_label}", flush=True)

        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper_models")
        os.makedirs(cache_dir, exist_ok=True)

        try:
            model = WhisperModel(model_name, device=device, compute_type=compute_type,
                                 download_root=cache_dir)
        except Exception as cuda_err:
            if device == "cuda":
                print(f"[Whisper Worker] CUDA failed ({cuda_err}), falling back to CPU", flush=True)
                device = "cpu"
                compute_type = "int8"
                upd({"status": "running", "progress": 0,
                     "message": f"Đang tải model {model_name} (CPU fallback)...",
                     "error": None, "model": model_name, "segments_count": 0, "segments": []})
                model = WhisperModel(model_name, device="cpu", compute_type="int8",
                                     download_root=cache_dir)
            else:
                raise

        if should_stop():
            upd({"status": "idle", "progress": 0, "message": "Đã dừng.",
                 "error": None, "model": model_name, "segments_count": 0, "segments": []})
            return

        upd({"status": "running", "progress": 10,
             "message": "Đang transcribe audio...",
             "error": None, "model": model_name, "segments_count": 0, "segments": []})

        audio_duration = get_duration(video_path, ffmpeg_cmd)

        # --- Transcribe with language fallback ---
        segments_list = []
        detected_lang = "?"
        transcribe_ok = False

        if language and language != "auto":
            attempts = [language, None]
        else:
            attempts = [None]

        gpu_lib_fallback_done = False

        # Sequential by default. WHISPER_BATCH=16 decodes VAD chunks in batches on GPU: measured ~1.4x
        # faster on an RTX 4060 but drops ~4% of the words (fillers at sentence starts). Halved on out-of-memory.
        batch_size = int(os.environ.get("WHISPER_BATCH", "0")) if device == "cuda" else 0

        i = 0
        while i < len(attempts):
            lang_attempt = attempts[i]
            if should_stop():
                upd({"status": "idle", "progress": 0, "message": "Đã dừng.",
                     "error": None, "model": model_name, "segments_count": 0, "segments": []})
                return

            try:
                lang_label = lang_attempt or "auto-detect"
                print(f"[Whisper Worker] Trying language={lang_label}", flush=True)

                if batch_size > 0:
                    from faster_whisper import BatchedInferencePipeline
                    print(f"[Whisper Worker] Batched decoding, batch_size={batch_size}", flush=True)
                    segments_iter, info = BatchedInferencePipeline(model).transcribe(
                        video_path,
                        language=lang_attempt,
                        beam_size=5,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500),
                        word_timestamps=True,
                        without_timestamps=False,  # keep sentence-sized segments, not whole VAD chunks
                        batch_size=batch_size,
                    )
                else:
                    segments_iter, info = model.transcribe(
                        video_path,
                        language=lang_attempt,
                        beam_size=5,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500),
                        word_timestamps=True,
                    )

                detected_lang = info.language
                segments_list = []

                for seg in segments_iter:
                    # Check stop between segments
                    if should_stop():
                        print(f"[Whisper Worker] Stopped at segment {len(segments_list)}", flush=True)
                        # Save partial results
                        upd({
                            "status": "done",
                            "progress": 100,
                            "message": f"Đã dừng (lưu {len(segments_list)} đoạn) | Ngôn ngữ: {detected_lang}",
                            "error": None,
                            "model": model_name,
                            "segments_count": len(segments_list),
                            "segments": segments_list,
                        })
                        return

                    # Extract word-level timestamps
                    words_data = []
                    if seg.words:
                        for w in seg.words:
                            words_data.append({
                                "word": w.word.strip(),
                                "start": round(w.start, 2),
                                "end": round(w.end, 2),
                            })
                    segments_list.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": seg.text.strip(),
                        "words": words_data,
                    })
                    pct = 10
                    if audio_duration > 0:
                        pct = min(90, 10 + int(seg.end / audio_duration * 80))
                    upd({
                        "status": "running",
                        "progress": pct,
                        "message": (
                            f"Ngôn ngữ: {detected_lang} | "
                            f"Đã xử lý {len(segments_list)} đoạn | "
                            f"{fmt_timestamp(seg.end)} / {fmt_timestamp(audio_duration)}"
                        ),
                        "error": None,
                        "model": model_name,
                        "segments_count": len(segments_list),
                        "segments": [],  # don't dump mid-progress
                    })

                transcribe_ok = True
                break

            except Exception as attempt_err:
                print(f"[Whisper Worker] lang={lang_label} failed: {attempt_err}", flush=True)

                err_str = str(attempt_err).lower()
                if batch_size > 0 and "out of memory" in err_str:
                    batch_size //= 2
                    print(f"[Whisper Worker] GPU out of memory, retrying with batch_size={batch_size}", flush=True)
                    continue  # retry the same lang_attempt with a smaller batch (0 = sequential)

                # GPU runtime libraries (cublas/cudnn/...) missing or broken: rebuild on CPU and retry
                is_gpu_lib_err = device == "cuda" and any(
                    k in err_str for k in ("cublas", "cudnn", "library", "cuda")
                )
                if is_gpu_lib_err and not gpu_lib_fallback_done:
                    gpu_lib_fallback_done = True
                    print(f"[Whisper Worker] GPU library error, rebuilding model on CPU: {attempt_err}", flush=True)
                    device = "cpu"
                    compute_type = "int8"
                    upd({"status": "running", "progress": 0,
                         "message": f"Đang tải model {model_name} (CPU fallback)...",
                         "error": None, "model": model_name, "segments_count": 0, "segments": []})
                    model = WhisperModel(model_name, device="cpu", compute_type="int8",
                                         download_root=cache_dir)
                    upd({"status": "running", "progress": 10,
                         "message": "Đang transcribe audio (CPU)...",
                         "error": None, "model": model_name, "segments_count": 0, "segments": []})
                    continue  # retry the same lang_attempt on CPU

                if lang_attempt is None:
                    upd({"status": "error", "progress": 0,
                         "message": "", "error": f"Lỗi khi transcribe: {attempt_err}",
                         "model": model_name, "segments_count": 0, "segments": []})
                    sys.exit(1)
                else:
                    upd({"status": "running", "progress": 10,
                         "message": f"Ngôn ngữ '{lang_attempt}' không hoạt động, đang thử tự nhận diện...",
                         "error": None, "model": model_name, "segments_count": 0, "segments": []})
                    i += 1
                    continue

        if not transcribe_ok:
            upd({"status": "error", "progress": 0,
                 "message": "", "error": "Không thể transcribe video này.",
                 "model": model_name, "segments_count": 0, "segments": []})
            sys.exit(1)

        # Write final result
        upd({
            "status": "done",
            "progress": 100,
            "message": f"Hoàn tất! {len(segments_list)} đoạn | Ngôn ngữ: {detected_lang}",
            "error": None,
            "model": model_name,
            "segments_count": len(segments_list),
            "segments": segments_list,
        })
        print(f"[Whisper Worker] Done: {len(segments_list)} segments, lang={detected_lang}", flush=True)

    except ImportError as e:
        upd({"status": "error", "progress": 0,
             "message": "", "error": "Chưa cài faster-whisper! Chạy: pip install faster-whisper",
             "model": model_name, "segments_count": 0, "segments": []})
        print(f"[Whisper Worker] ImportError: {e}", flush=True)
        sys.exit(1)
    except Exception as e:
        tb = traceback.format_exc()
        upd({"status": "error", "progress": 0,
             "message": "", "error": str(e),
             "model": model_name, "segments_count": 0, "segments": []})
        print(f"[Whisper Worker] ERROR: {e}\n{tb}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
