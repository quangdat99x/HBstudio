"""
watcher.py — "Xem" một video để Claude hiểu và bắt chước được nó.

Video → cắt cảnh (scene detect) → khung hình đại diện mỗi shot → contact sheet
có nhãn timestamp → hook sheet (1 fps cho 15s đầu) → transcript Whisper →
nhịp dựng, âm lượng, bảng màu → REPORT.md (Claude đọc file này + các ảnh sheet).

CLI:
    python watcher.py <video_path | url> [--out DIR] [--max-frames 60]
                      [--model small] [--lang auto] [--no-transcript]
                      [--scene 0.30] [--hook 15]
In ra đường dẫn REPORT.md ở dòng cuối cùng.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
# Model Whisper đã tải sẵn cho Video Cutter — dùng chung, khỏi tải lại.
WHISPER_CACHE = os.path.join(os.path.dirname(BASE_DIR), 'video-cutter-portable', 'whisper_models')

_CFLAGS = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

SHEET_COLS, SHEET_ROWS = 4, 3
CELL_W = 480
FRAME_W = 1280
MIN_SHOT = 0.4  # giây; cắt ngắn hơn thế này coi là nhiễu (flash, fade)


def _register_nvidia_dll_dirs():
    """ctranslate2 tìm cublas/cudnn qua PATH; các wheel nvidia-* để DLL trong site-packages."""
    if os.name != 'nt':
        return
    try:
        import site
        roots = set(site.getsitepackages() + [site.getusersitepackages()])
        dirs = []
        for root in roots:
            nv = os.path.join(root, 'nvidia')
            if os.path.isdir(nv):
                for pkg in os.listdir(nv):
                    b = os.path.join(nv, pkg, 'bin')
                    if os.path.isdir(b):
                        try:
                            os.add_dll_directory(b)
                        except Exception:
                            pass
                        dirs.append(b)
        if dirs:
            os.environ['PATH'] = os.pathsep.join(dirs + [os.environ.get('PATH', '')])
    except Exception:
        pass


def _run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=timeout, creationflags=_CFLAGS)


def fmt_ts(sec, ms=False):
    sec = max(0.0, float(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if ms:
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}" if h else f"{int(m):02d}:{s:06.3f}"
    return f"{int(h):d}:{int(m):02d}:{int(s):02d}" if h else f"{int(m):02d}:{int(s):02d}"


def slugify(name):
    name = os.path.splitext(os.path.basename(name))[0]
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name).strip('._')
    return (name or 'video')[:60]


# ───────────────────────────── Pipeline steps ─────────────────────────────

DOWNLOADER_DIR = os.path.join(os.path.dirname(BASE_DIR), 'Youtube Dowloader')


def download_url(url, out_dir, log):
    """Tải video (≤720p là đủ để xem) qua engine của YouTube Downloader."""
    log('Đang tải video từ URL (qua engine YouTube Downloader)...')
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.isdir(DOWNLOADER_DIR):
        raise RuntimeError(f'Không thấy YouTube Downloader ở {DOWNLOADER_DIR}')
    py = os.path.join(DOWNLOADER_DIR, '.venv', 'Scripts', 'python.exe')
    if not os.path.exists(py):
        py = sys.executable.replace('pythonw.exe', 'python.exe')
    r = _run([py, '-X', 'utf8', os.path.join(BASE_DIR, 'yt_fetch.py'), DOWNLOADER_DIR, url, out_dir, '720p'],
             timeout=3600)
    lines = [ln for ln in (r.stdout or '').strip().splitlines() if ln.startswith('{')]
    if not lines:
        raise RuntimeError('Tải lỗi: ' + (r.stderr or r.stdout or '')[-800:])
    res = json.loads(lines[-1])
    if not res.get('success'):
        raise RuntimeError('Tải lỗi: ' + str(res.get('error'))[:800])
    path = res['filepath']
    if not os.path.isfile(path):
        cands = [os.path.join(out_dir, f) for f in os.listdir(out_dir)
                 if f.lower().endswith(('.mp4', '.mkv', '.webm'))]
        if not cands:
            raise RuntimeError('Không tìm thấy file video sau khi tải.')
        path = max(cands, key=os.path.getsize)
    return path, res.get('info') or {'title': res.get('title')}

def probe(path):
    r = _run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', path])
    if r.returncode != 0:
        raise RuntimeError('ffprobe không đọc được file: ' + r.stderr[-400:])
    j = json.loads(r.stdout)
    v = next((s for s in j['streams'] if s.get('codec_type') == 'video'), None)
    a = next((s for s in j['streams'] if s.get('codec_type') == 'audio'), None)
    if not v:
        raise RuntimeError('File không có luồng video.')
    dur = float(j['format'].get('duration') or v.get('duration') or 0)
    num, _, den = (v.get('avg_frame_rate') or '0/1').partition('/')
    fps = float(num) / float(den or 1) if float(den or 1) else 0
    w, h = int(v.get('width', 0)), int(v.get('height', 0))
    rot = 0
    for sd in v.get('side_data_list', []) or []:
        if 'rotation' in sd:
            rot = abs(int(sd['rotation']))
    if rot in (90, 270):
        w, h = h, w
    ratio = w / h if h else 0
    if ratio < 0.7:
        fmt = 'dọc 9:16 (Shorts/TikTok/Reels)'
    elif ratio < 1.2:
        fmt = 'vuông/4:5 (feed)'
    elif ratio < 2.0:
        fmt = 'ngang 16:9 (YouTube)'
    else:
        fmt = 'ngang siêu rộng (cinematic)'
    return {
        'duration': dur, 'width': w, 'height': h, 'fps': round(fps, 3), 'format_label': fmt,
        'vcodec': v.get('codec_name'), 'acodec': a.get('codec_name') if a else None,
        'has_audio': a is not None, 'size_mb': round(int(j['format'].get('size', 0)) / 1048576, 1),
        'bitrate_kbps': round(int(j['format'].get('bit_rate', 0) or 0) / 1000),
    }


def detect_scenes(path, duration, threshold, log):
    """Cắt cảnh bằng bộ lọc scene của ffmpeg trên bản thu nhỏ (nhanh)."""
    log('Đang dò điểm cắt cảnh...')
    vf = f"scale=320:-2,select='gt(scene\\,{threshold})',showinfo"
    r = _run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-an', '-sn', '-dn',
              '-vf', vf, '-f', 'null', '-'], timeout=max(600, duration * 3))
    cuts = []
    for m in re.finditer(r'pts_time:\s*([0-9.]+)', r.stderr):
        t = float(m.group(1))
        if t > MIN_SHOT and (not cuts or t - cuts[-1] >= MIN_SHOT) and t < duration - MIN_SHOT:
            cuts.append(t)
    soft = detect_soft(path, duration, cuts, log)
    kinds = {t: 'hard' for t in cuts} | {t: 'soft' for t in soft}
    bounds = [0.0] + sorted(kinds) + [duration]
    return [{'start': bounds[i], 'end': bounds[i + 1], 'cut': kinds.get(bounds[i], 'start')}
            for i in range(len(bounds) - 1)]


def detect_soft(path, duration, hard_cuts, log):
    """Chuyển cảnh mềm (dissolve, wipe, fade) mà bộ lọc scene bỏ sót: so histogram màu cách nhau 1s.
    Ngưỡng tương đối với nền xung quanh để máy quay rung/lia không bị tính là chuyển cảnh."""
    try:
        import numpy as np
    except ImportError:
        return []
    fps = 4 if duration <= 600 else 2 if duration <= 3600 else 1
    w, h = 64, 36
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-an', '-sn', '-dn', '-vf',
                        f'fps={fps},scale={w}:{h},format=rgb24', '-f', 'rawvideo', '-'],
                       capture_output=True, timeout=max(600, duration * 3), creationflags=_CFLAGS)
    n = len(r.stdout) // (w * h * 3)
    if n < fps * 3:
        return []
    a = np.frombuffer(r.stdout[:n * w * h * 3], np.uint8).reshape(n, -1, 3) // 64
    idx = a[..., 0].astype(np.int32) * 16 + a[..., 1] * 4 + a[..., 2]
    H = np.stack([np.bincount(row, minlength=64) for row in idx]) / idx.shape[1]
    d = 0.5 * np.abs(H[fps:] - H[:-fps]).sum(1)  # khác biệt giữa khung t và t-1s
    times = (np.arange(len(d)) + fps / 2) / fps   # giữa khoảng so sánh
    win = 5 * fps
    found = []
    i = 0
    while i < len(d):
        lo, hi = max(0, i - win), min(len(d), i + win + 1)
        base = float(np.median(d[lo:hi]))
        if d[i] > 0.3 and d[i] > 4 * base:
            j = i
            while j + 1 < len(d) and d[j + 1] > 0.3:  # cả vùng chuyển cảnh → lấy đỉnh
                j += 1
            k = i + int(np.argmax(d[i:j + 1]))
            t = float(times[k])
            if (all(abs(t - c) > 1.0 for c in hard_cuts) and (not found or t - found[-1] > 1.5)
                    and MIN_SHOT < t < duration - MIN_SHOT):
                found.append(round(t, 2))
            i = j + 1
        else:
            i += 1
    if found:
        log(f'Thêm {len(found)} chuyển cảnh mềm (dissolve/wipe).')
    return found


def pick_frames(shots, duration, max_frames, min_frames=24):
    """Chọn thời điểm lấy khung: giữa mỗi shot; giới hạn bằng chia thùng thời gian; bù đều nếu ít shot."""
    cands = [((s['start'] + s['end']) / 2, i, s['end'] - s['start']) for i, s in enumerate(shots)]
    if len(cands) > max_frames:
        # Mỗi thùng thời gian giữ shot dài nhất → phủ đều cả video.
        buckets = {}
        for t, i, d in cands:
            b = min(max_frames - 1, int(t / duration * max_frames))
            if b not in buckets or d > buckets[b][2]:
                buckets[b] = (t, i, d)
        cands = sorted(buckets.values())
    picks = [(t, i) for t, i, _ in cands]
    # Video ít cắt (1 take dài) vẫn cần đủ khung để thấy chuyển động/biến đổi.
    target = min(max_frames, max(min_frames, len(picks)))
    if len(picks) < target:
        step = duration / (target + 1)
        have = [t for t, _ in picks]
        for k in range(1, target + 1):
            t = k * step
            if all(abs(t - h) > step * 0.4 for h in have):
                si = next((i for i, s in enumerate(shots) if s['start'] <= t < s['end']), len(shots) - 1)
                picks.append((t, si))
        picks.sort()
    return picks[:max_frames] if len(picks) > max_frames else picks


def extract_frame(path, t, dst, width=FRAME_W):
    _run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', f'{t:.3f}', '-i', path,
          '-frames:v', '1', '-vf', f'scale={width}:-2', '-q:v', '3', dst], timeout=60)
    return os.path.exists(dst)


def _font(size):
    from PIL import ImageFont
    for f in ('arialbd.ttf', 'segoeuib.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_sheet(items, dst, cols=SHEET_COLS, cell_w=CELL_W, title=None):
    """items: [(image_path, label)] → lưới ảnh có nhãn, nền tối."""
    from PIL import Image, ImageDraw
    imgs = []
    for p, label in items:
        try:
            im = Image.open(p).convert('RGB')
        except Exception:
            continue
        im = im.resize((cell_w, max(1, round(im.height * cell_w / im.width))))
        imgs.append((im, label))
    if not imgs:
        return False
    cell_h = max(im.height for im, _ in imgs)
    rows = math.ceil(len(imgs) / cols)
    pad, head = 6, (40 if title else 0)
    W = cols * cell_w + (cols + 1) * pad
    H = head + rows * cell_h + (rows + 1) * pad
    sheet = Image.new('RGB', (W, H), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((pad + 4, 8), title, fill=(235, 235, 240), font=_font(22))
    f = _font(max(16, cell_w // 22))
    for k, (im, label) in enumerate(imgs):
        r, c = divmod(k, cols)
        x = pad + c * (cell_w + pad)
        y = head + pad + r * (cell_h + pad)
        sheet.paste(im, (x, y + (cell_h - im.height) // 2))
        tb = d.textbbox((0, 0), label, font=f)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        d.rectangle([x, y, x + tw + 14, y + th + 12], fill=(0, 0, 0))
        d.text((x + 7, y + 4), label, fill=(255, 220, 60), font=f)
    sheet.save(dst, quality=88)
    return True


def frame_stats(path):
    """Độ sáng, độ bão hoà, 5 màu chủ đạo của một khung."""
    from PIL import Image, ImageStat
    im = Image.open(path).convert('RGB')
    small = im.resize((160, max(1, round(im.height * 160 / im.width))))
    hsv = small.convert('HSV')
    st = ImageStat.Stat(hsv)
    q = small.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:15]
    counts = sorted(q.getcolors(), reverse=True)
    colors = []
    for cnt, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        colors.append({'hex': f'#{r:02x}{g:02x}{b:02x}', 'share': round(cnt / (small.width * small.height), 3)})
    return {'brightness': round(st.mean[2] / 255, 3), 'saturation': round(st.mean[1] / 255, 3),
            'palette': colors}


def audio_loudness(path, duration, log):
    """RMS (dB) mỗi giây → đường cong năng lượng + tỉ lệ im lặng."""
    log('Đang đo âm lượng...')
    af = ('aresample=8000,asetnsamples=n=8000,'
          'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level')
    r = _run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-vn', '-af', af, '-f', 'null', '-'],
             timeout=max(600, duration * 2))
    vals = []
    for m in re.finditer(r'RMS_level=(-?[0-9.]+|-inf)', r.stderr):
        v = m.group(1)
        vals.append(-90.0 if v == '-inf' else max(-90.0, float(v)))
    if not vals:
        return None
    silent = sum(1 for v in vals if v < -45) / len(vals)
    srt = sorted(vals)
    return {'per_second_db': [round(v, 1) for v in vals], 'silence_ratio': round(silent, 3),
            'median_db': round(srt[len(srt) // 2], 1), 'peak_db': round(srt[-1], 1)}


def transcribe(path, model_name, lang, log):
    log(f'Đang chép lời bằng Whisper ({model_name})...')
    _register_nvidia_dll_dirs()
    from faster_whisper import WhisperModel
    language = None if lang in (None, '', 'auto') else lang
    model = None
    for device, ctype in (('cuda', 'float16'), ('cpu', 'int8')):
        try:
            model = WhisperModel(model_name, device=device, compute_type=ctype,
                                 download_root=WHISPER_CACHE if os.path.isdir(WHISPER_CACHE) else None)
            # VAD lọc mất lời hát / lời trên nền nhạc to → gần như trống thì chạy lại không VAD.
            for vad in (True, False):
                segs, info = model.transcribe(path, language=language, vad_filter=vad,
                                              word_timestamps=False, beam_size=5,
                                              condition_on_previous_text=vad)
                out = []
                for s in segs:
                    out.append({'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip()})
                    if len(out) % 20 == 0:
                        log(f'Đang chép lời... {fmt_ts(s.end)}')
                words = sum(len(s['text'].split()) for s in out)
                if not vad or words >= info.duration / 20:
                    break
                log('Ít lời qua VAD (có thể là nhạc/hát) — chép lại không lọc...')
            return {'language': info.language, 'device': device, 'model': model_name,
                    'vad': vad, 'segments': out}
        except Exception as e:
            if device == 'cpu':
                raise
            log(f'GPU lỗi ({str(e)[:120]}), chuyển sang CPU...')
            model = None
    return None


# ───────────────────────────── Analysis + report ─────────────────────────────

def pacing(shots, duration):
    lens = sorted(s['end'] - s['start'] for s in shots)
    n = len(lens)
    win = 10 if duration <= 300 else 30 if duration <= 1800 else 60
    nwin = max(1, math.ceil(duration / win))
    density = [0] * nwin
    for s in shots[1:]:
        density[min(nwin - 1, int(s['start'] // win))] += 1
    return {
        'shot_count': n,
        'avg_shot_sec': round(duration / n, 2) if n else 0,
        'median_shot_sec': round(lens[n // 2], 2) if n else 0,
        'shortest_sec': round(lens[0], 2) if n else 0,
        'longest_sec': round(lens[-1], 2) if n else 0,
        'cuts_per_min': round((n - 1) / (duration / 60), 1) if duration else 0,
        'hard_cuts': sum(1 for s in shots if s.get('cut') == 'hard'),
        'soft_transitions': sum(1 for s in shots if s.get('cut') == 'soft'),
        'density_window_sec': win,
        'cuts_per_window': density,
    }


def spark(vals, lo=None, hi=None):
    bars = '▁▂▃▄▅▆▇█'
    if not vals:
        return ''
    lo = min(vals) if lo is None else lo
    hi = max(vals) if hi is None else hi
    rng = (hi - lo) or 1
    return ''.join(bars[min(7, max(0, int((v - lo) / rng * 7.999)))] for v in vals)


def text_in(segments, a, b):
    return ' '.join(s['text'] for s in segments if s['end'] > a and s['start'] < b).strip()


def write_report(out, meta):
    m = meta
    p, pr = m['probe'], m['pacing']
    segs = (m.get('transcript') or {}).get('segments', [])
    L = []
    L.append(f"# Báo cáo xem video: {m['title']}")
    L.append('')
    L.append(f"> Thư mục: `{out}`  ")
    L.append(f"> Nguồn: `{m['source']}`  ")
    L.append(f"> Phân tích lúc {m['created']} · mất {m['elapsed_sec']}s")
    L.append('')
    L.append('## Cách Claude xem video này')
    L.append('1. Đọc hết báo cáo này (số liệu + shot list + transcript).')
    L.append(f"2. Xem **hook sheet** `{m['hook_sheet']}` — {m['hook_seconds']}s đầu, 1 khung/giây.")
    L.append('3. Xem lần lượt các **contact sheet** dưới đây theo thứ tự — đó là toàn bộ video đã nén thành ảnh.')
    L.append('4. Cần soi chi tiết (chữ trên màn hình, ánh sáng, bố cục) → mở khung lẻ trong `frames/`.')
    L.append('')
    for s in m['sheets']:
        L.append(f"- `{s['file']}` — khung #{s['first']}–#{s['last']} ({s['from']} → {s['to']})")
    L.append('')
    if m.get('source_info'):
        si = m['source_info']
        L.append('## Thông tin nguồn')
        for k in ('title', 'channel', 'uploader', 'upload_date', 'view_count', 'like_count', 'webpage_url'):
            if si.get(k):
                L.append(f'- **{k}**: {si[k]}')
        if si.get('tags'):
            L.append(f"- **tags**: {', '.join(si['tags'][:25])}")
        if si.get('description'):
            L.append('')
            L.append('```')
            L.append(si['description'])
            L.append('```')
        L.append('')
    L.append('## Thông số kỹ thuật')
    L.append(f"- Thời lượng: **{fmt_ts(p['duration'])}** ({p['duration']:.1f}s)")
    L.append(f"- Khung hình: {p['width']}×{p['height']} · {p['fps']} fps · **{p['format_label']}**")
    L.append(f"- Codec: {p['vcodec']} / {p['acodec'] or 'không có tiếng'} · {p['size_mb']} MB · {p['bitrate_kbps']} kbps")
    L.append('')
    L.append('## Nhịp dựng')
    L.append(f"- Số shot: **{pr['shot_count']}** · trung bình **{pr['avg_shot_sec']}s/shot** · trung vị {pr['median_shot_sec']}s")
    L.append(f"- Shot ngắn nhất {pr['shortest_sec']}s · dài nhất {pr['longest_sec']}s · **{pr['cuts_per_min']} cắt/phút**")
    L.append(f"- Kiểu chuyển: {pr['hard_cuts']} cắt cứng · {pr['soft_transitions']} chuyển mềm (dissolve/wipe/fade)")
    L.append(f"- Mật độ cắt mỗi {pr['density_window_sec']}s: `{spark(pr['cuts_per_window'], lo=0)}` "
             f"(max {max(pr['cuts_per_window'] or [0])} cắt/cửa sổ)")
    L.append('')
    if m.get('audio'):
        a = m['audio']
        vals = a['per_second_db']
        step = max(1, math.ceil(len(vals) / 100))
        ds = [max(vals[i:i + step]) for i in range(0, len(vals), step)]
        L.append('## Âm thanh')
        L.append(f"- Âm lượng trung vị {a['median_db']} dB · đỉnh {a['peak_db']} dB · im lặng {a['silence_ratio'] * 100:.0f}% thời lượng")
        L.append(f"- Đường năng lượng (mỗi ký tự ≈ {step}s): `{spark(ds, lo=max(-60, min(ds)), hi=max(ds))}`")
    if m.get('transcript'):
        t = m['transcript']
        words = sum(len(s['text'].split()) for s in segs)
        speech = sum(s['end'] - s['start'] for s in segs)
        wpm = round(words / (speech / 60)) if speech else 0
        L.append(f"- Lời thoại: ngôn ngữ **{t['language']}** · {words} từ · nói {speech / p['duration'] * 100:.0f}% thời lượng · "
                 f"**{wpm} từ/phút** khi nói")
    L.append('')
    if m.get('look'):
        lk = m['look']
        L.append('## Màu sắc / ánh sáng')
        L.append(f"- Độ sáng TB {lk['brightness']:.2f} · độ bão hoà TB {lk['saturation']:.2f} (0–1)")
        L.append(f"- Màu chủ đạo toàn video: {', '.join(c['hex'] for c in lk['palette'])}")
        L.append('')
    L.append('## Danh sách shot')
    L.append('| Khung | Shot | Bắt đầu | Kết thúc | Dài | File | Lời quanh khung |')
    L.append('|---|---|---|---|---|---|---|')
    frs = m['frames']
    for k, fr in enumerate(frs):
        s = m['shots'][fr['shot']]
        # Lời quanh khung này: từ giữa khung trước đến giữa khung sau.
        a = (frs[k - 1]['t'] + fr['t']) / 2 if k else 0
        b = (fr['t'] + frs[k + 1]['t']) / 2 if k + 1 < len(frs) else p['duration']
        txt = text_in(segs, a, b)
        if len(txt) > 160:
            txt = txt[:157] + '…'
        mark = ' (mềm)' if s.get('cut') == 'soft' else ''
        L.append(f"| #{fr['idx']} @{fmt_ts(fr['t'])} | {fr['shot'] + 1}{mark} | {fmt_ts(s['start'], True)} | "
                 f"{fmt_ts(s['end'], True)} | {s['end'] - s['start']:.1f}s | `{fr['file']}` | {txt.replace('|', '/')} |")
    if len(m['frames']) < len(m['shots']):
        L.append('')
        L.append(f"_Video có {len(m['shots'])} shot; chỉ lấy {len(m['frames'])} khung đại diện. "
                 f"Danh sách đủ mọi shot nằm trong `analysis.json`._")
    L.append('')
    if segs:
        L.append('## Transcript có timestamp')
        L.append('```')
        for s in segs:
            L.append(f"[{fmt_ts(s['start'])}] {s['text']}")
        L.append('```')
    path = os.path.join(out, 'REPORT.md')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')
    return path


def merge_palette(weights, n=8, min_dist=48):
    """Gộp các màu gần nhau (vd #000000/#000001) rồi lấy n màu nặng ký nhất."""
    rgb = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    kept = []
    for h, w in sorted(weights.items(), key=lambda x: -x[1]):
        c = rgb(h)
        for k in kept:
            if sum((a - b) ** 2 for a, b in zip(c, k[1])) ** 0.5 < min_dist:
                k[2] += w
                break
        else:
            kept.append([h, c, w])
    return [k[0] for k in sorted(kept, key=lambda k: -k[2])[:n]]


def analyze(source, out=None, **kw):
    """Chạy toàn bộ pipeline; lỗi giữa chừng thì xoá thư mục kết quả dở dang do mình tạo."""
    auto = out is None
    holder = {}
    try:
        return _analyze(source, out, holder, **kw)
    except Exception:
        d = holder.get('out')
        if auto and d and d.startswith(OUTPUT_DIR) and not os.path.exists(os.path.join(d, 'analysis.json')):
            shutil.rmtree(d, ignore_errors=True)
        raise


def _analyze(source, out, holder, max_frames=60, model='small', lang='auto', do_transcript=True,
             scene=0.30, hook_seconds=15, log=print):
    t0 = time.time()
    is_url = bool(re.match(r'^https?://', source.strip()))
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    if out is None:
        out = os.path.join(OUTPUT_DIR, f"{stamp}_{slugify('url' if is_url else source)}")
    holder['out'] = out
    os.makedirs(out, exist_ok=True)
    for sub in ('frames', 'sheets', 'hook'):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    src_info = None
    if is_url:
        video, src_info = download_url(source.strip(), out, log)
        if src_info and src_info.get('title'):
            new_out = os.path.join(OUTPUT_DIR, f"{stamp}_{slugify(src_info['title'])}")
            if out.startswith(OUTPUT_DIR) and not os.path.exists(new_out):
                shutil.move(out, new_out)
                video = os.path.join(new_out, os.path.basename(video))
                out = new_out
                holder['out'] = out
    else:
        video = os.path.abspath(source.strip().strip('"'))
        if not os.path.isfile(video):
            raise FileNotFoundError(f'Không thấy file: {video}')

    log('Đang đọc thông số video...')
    p = probe(video)
    dur = p['duration']
    shots = detect_scenes(video, dur, scene, log)
    log(f'Tìm thấy {len(shots)} shot. Đang trích khung đại diện...')

    picks = pick_frames(shots, dur, max_frames)
    frames = []
    for k, (t, si) in enumerate(picks, 1):
        rel = f"frames/f{k:03d}_{fmt_ts(t).replace(':', '-')}.jpg"
        if extract_frame(video, t, os.path.join(out, rel)):
            frames.append({'idx': k, 't': round(t, 2), 'shot': si, 'file': rel})
        if k % 10 == 0:
            log(f'Đã trích {k}/{len(picks)} khung...')

    log('Đang ghép contact sheet...')
    per = SHEET_COLS * SHEET_ROWS
    vertical = p['height'] > p['width']
    # Video dọc: 6 cột × 2 hàng cho sheet ngang vừa mắt thay vì cột ảnh dài lêu nghêu.
    cols, cell_w = (6, 320) if vertical else (SHEET_COLS, CELL_W)
    sheets = []
    for n, i in enumerate(range(0, len(frames), per), 1):
        chunk = frames[i:i + per]
        rel = f'sheets/sheet_{n:02d}.jpg'
        title = f"{m_title(source, src_info)} — sheet {n}  ({fmt_ts(chunk[0]['t'])} → {fmt_ts(chunk[-1]['t'])})"
        make_sheet([(os.path.join(out, f['file']), f"#{f['idx']}  {fmt_ts(f['t'])}") for f in chunk],
                   os.path.join(out, rel), cols=cols, cell_w=cell_w, title=title)
        sheets.append({'file': rel, 'first': chunk[0]['idx'], 'last': chunk[-1]['idx'],
                       'from': fmt_ts(chunk[0]['t']), 'to': fmt_ts(chunk[-1]['t'])})

    log('Đang dựng hook sheet (giây đầu)...')
    hook_n = int(min(hook_seconds, max(1, dur - 0.1)))
    hook_items = []
    for s in range(hook_n + 1):
        t = min(s + 0.05, dur - 0.05)
        dst = os.path.join(out, 'hook', f'h{s:02d}.jpg')
        if extract_frame(video, t, dst, width=640):
            hook_items.append((dst, f'{s}s'))
    hook_rel = 'sheets/hook.jpg'
    make_sheet(hook_items, os.path.join(out, hook_rel), cols=8 if vertical else 4,
               cell_w=240 if vertical else 360,
               title=f'HOOK — {hook_n}s đầu, 1 khung/giây')

    log('Đang phân tích màu sắc...')
    agg_b, agg_s, colors = [], [], {}
    for f in frames:
        try:
            st = frame_stats(os.path.join(out, f['file']))
        except Exception:
            continue
        f.update(brightness=st['brightness'], saturation=st['saturation'],
                 palette=[c['hex'] for c in st['palette']])
        agg_b.append(st['brightness'])
        agg_s.append(st['saturation'])
        for c in st['palette']:
            colors[c['hex']] = colors.get(c['hex'], 0) + c['share']
    look = None
    if agg_b:
        look = {'brightness': sum(agg_b) / len(agg_b), 'saturation': sum(agg_s) / len(agg_s),
                'palette': [{'hex': h} for h in merge_palette(colors)]}

    audio = audio_loudness(video, dur, log) if p['has_audio'] else None
    transcript = None
    if do_transcript and p['has_audio']:
        try:
            transcript = transcribe(video, model, lang, log)
        except Exception as e:
            log(f'Bỏ qua transcript: {e}')
    if transcript:
        with open(os.path.join(out, 'transcript.txt'), 'w', encoding='utf-8') as fh:
            for s in transcript['segments']:
                fh.write(f"[{fmt_ts(s['start'])}] {s['text']}\n")

    meta = {
        'title': m_title(source, src_info),
        'source': source, 'video_file': video, 'created': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'elapsed_sec': round(time.time() - t0), 'probe': p, 'source_info': src_info,
        'pacing': pacing(shots, dur), 'shots': [{'start': round(s['start'], 3), 'end': round(s['end'], 3), 'cut': s['cut']} for s in shots],
        'frames': frames, 'sheets': sheets, 'hook_sheet': hook_rel, 'hook_seconds': hook_n,
        'look': look, 'audio': audio, 'transcript': transcript,
        'settings': {'max_frames': max_frames, 'model': model, 'lang': lang, 'scene': scene},
    }
    with open(os.path.join(out, 'analysis.json'), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    report = write_report(out, meta)
    log(f"Xong sau {meta['elapsed_sec']}s.")
    return {'out': out, 'report': report, 'meta': meta}


def m_title(source, src_info):
    if src_info and src_info.get('title'):
        return src_info['title']
    return os.path.splitext(os.path.basename(source.strip().strip('"')))[0] or source


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='Phân tích video để Claude "xem" được.')
    ap.add_argument('source', help='Đường dẫn video hoặc URL (YouTube, TikTok...)')
    ap.add_argument('--out', help='Thư mục kết quả (mặc định: output/<thời gian>_<tên>)')
    ap.add_argument('--max-frames', type=int, default=60)
    ap.add_argument('--model', default='small', help='tiny/base/small/large-v3')
    ap.add_argument('--lang', default='auto')
    ap.add_argument('--no-transcript', action='store_true')
    ap.add_argument('--scene', type=float, default=0.30, help='Ngưỡng cắt cảnh 0.1–0.6 (thấp = nhạy hơn)')
    ap.add_argument('--hook', type=int, default=15, help='Số giây đầu dựng hook sheet')
    a = ap.parse_args()
    res = analyze(a.source, out=a.out, max_frames=a.max_frames, model=a.model, lang=a.lang,
                  do_transcript=not a.no_transcript, scene=a.scene, hook_seconds=a.hook,
                  log=lambda s: print(s, flush=True))
    print(res['report'])


if __name__ == '__main__':
    main()
