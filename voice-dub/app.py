"""
Lồng Tiếng — giao diện web cho dub.py.
Chạy qua launcher (run.pyw → _tool_server.py) ở cổng 5013, hoặc: py app.py
"""
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import dub

app = Flask(__name__)
OUT = dub.OUTPUT_DIR
UPLOAD_DIR = os.path.join(dub.BASE_DIR, 'uploads')
os.makedirs(OUT, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
_CFLAGS = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

_q = queue.Queue()
ACTIVE = {}      # id -> project đang chờ/đang chạy, bản mới nhất nằm trong bộ nhớ
_cancel = set()


def _worker():
    # Một việc mỗi lúc: Whisper + ffmpeg đã ăn hết GPU/CPU, chạy song song chỉ chậm hơn.
    while True:
        pid = _q.get()
        p = ACTIVE[pid]
        back = 'review' if p['stage'] == 'dub' else 'error'

        def should_stop(pid=pid):
            return pid in _cancel

        try:
            if should_stop():
                raise dub.Cancelled()
            p['state'] = 'running'
            p['error'] = None
            dub.save_project(p)
            (dub.dub if p['stage'] == 'dub' else dub.analyze)(p, should_stop)
        except dub.Cancelled:
            p['state'] = back
            p['msg'] = 'Đã dừng'
            p['log'].append(f"[{time.strftime('%H:%M:%S')}] Đã dừng")
            dub.save_project(p)
        except Exception as e:
            p['state'] = back
            p['error'] = str(e)
            p['msg'] = 'Lỗi'
            p['log'].append(f"[{time.strftime('%H:%M:%S')}] LỖI: {e}")
            dub.save_project(p)
        finally:
            _cancel.discard(pid)
            ACTIVE.pop(pid, None)
            _q.task_done()


threading.Thread(target=_worker, daemon=True).start()


def _recover_interrupted():
    """Server tắt giữa chừng: đừng để project treo mãi ở 'đang chạy'."""
    for name in os.listdir(OUT):
        try:
            p = dub.load_project(name)
        except (OSError, ValueError):
            continue
        if p.get('state') in ('queued', 'running'):
            p['state'] = 'review' if p.get('stage') == 'dub' else 'error'
            p['error'] = 'Bị ngắt giữa chừng do tool tắt. Chạy lại được, audio đã có không tính phí lần nữa.'
            dub.save_project(p)


_recover_interrupted()


def _get(pid):
    if pid in ACTIVE:
        return ACTIVE[pid]
    try:
        return dub.load_project(pid)
    except (OSError, ValueError):
        abort(404)


def _num(data, key, default, lo, hi, cast=float):
    try:
        return max(lo, min(hi, cast(data.get(key, default))))
    except (TypeError, ValueError):
        return default


def _opts(data):
    target = data.get('target') or 'vi'
    return {'model': data.get('model') if data.get('model') in ('tiny', 'base', 'small', 'large-v3') else 'large-v3',
            'lang': (data.get('lang') or 'auto').strip()[:8],
            'target': target if target == 'none' or target in dub.LANGUAGES else 'vi'}


def _enqueue(p):
    ACTIVE[p['id']] = p
    _q.put(p['id'])


@app.route('/')
def index():
    return render_template('index.html', languages=dub.LANGUAGES, models=dub.TTS_MODELS, default_model=dub.DEFAULT_TTS_MODEL)


@app.get('/api/account')
def api_account():
    if not dub.api_key():
        return jsonify(has_key=False)
    try:
        return jsonify(has_key=True, sub=dub.subscription(), voices=dub.voices(),
                       remembered=dub.load_settings().get('voice') or '')
    except dub.ApiError as e:
        return jsonify(has_key=True, error=str(e))


@app.get('/api/library')
def api_library():
    a = request.args
    try:
        return jsonify(dub.library_voices(a.get('language'), a.get('gender'), a.get('accent'), a.get('q'),
                                          a.get('page', 0, type=int)))
    except dub.ApiError as e:
        return jsonify(error=str(e)), 502


@app.post('/api/voices/add')
def api_voice_add():
    data = request.get_json(force=True, silent=True) or {}
    try:
        if data.get('owner'):
            vid = dub.add_library_voice(data['owner'], data.get('id') or '', data.get('name'))
        else:
            vid = dub.resolve_voice_id((data.get('id') or '').strip())
        return jsonify(id=vid, voices=dub.voices())
    except dub.ApiError as e:
        return jsonify(error=str(e)), 502


@app.post('/api/key')
def api_key():
    data = request.get_json(force=True, silent=True) or {}
    dub.save_settings(elevenlabs_api_key=(data.get('key') or '').strip())
    return jsonify(ok=True)


@app.post('/api/projects')
def api_create():
    data = request.get_json(force=True, silent=True) or {}
    src = (data.get('source') or '').strip().strip('"')
    if not src:
        return jsonify(error='Chưa nhập đường dẫn video'), 400
    if not os.path.isfile(src):
        return jsonify(error=f'Không thấy file: {src}'), 400
    p = dub.create_project(src, _opts(data))
    _enqueue(p)
    return jsonify(id=p['id'])


@app.post('/api/upload')
def api_upload():
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify(error='Không có file'), 400
    sub = os.path.join(UPLOAD_DIR, uuid.uuid4().hex[:8])
    os.makedirs(sub, exist_ok=True)
    final = os.path.join(sub, os.path.basename(f.filename))
    f.save(final)
    p = dub.create_project(final, _opts(request.form))
    _enqueue(p)
    return jsonify(id=p['id'])


@app.get('/api/projects')
def api_list():
    items = []
    for name in sorted(os.listdir(OUT), reverse=True):
        if not os.path.isfile(os.path.join(OUT, name, 'project.json')):
            continue
        try:
            p = _get(name)
        except Exception:
            continue
        items.append({k: p.get(k) for k in ('id', 'title', 'state', 'created', 'duration')} | {'count': len(p.get('blocks') or [])})
    return jsonify(items)


@app.get('/api/projects/<pid>')
def api_project(pid):
    p = _get(pid)
    return jsonify({k: v for k, v in p.items() if k != 'log'} | {'log': p['log'][-40:], 'dir': dub.project_dir(pid)})


@app.post('/api/projects/<pid>/blocks')
def api_blocks(pid):
    p = _get(pid)
    if pid in ACTIVE:
        return jsonify(error='Đang chạy, chưa sửa được'), 409
    edits = (request.get_json(force=True, silent=True) or {}).get('edits') or {}
    for b in p['blocks']:
        if str(b['id']) in edits:
            b['text'] = str(edits[str(b['id'])]).strip()
    dub.save_project(p)
    return jsonify(ok=True)


@app.post('/api/projects/<pid>/estimate')
def api_estimate(pid):
    p = _get(pid)
    data = request.get_json(force=True, silent=True) or {}
    voice, model = data.get('voice') or '', data.get('model') or dub.DEFAULT_TTS_MODEL
    chars = dub.pending_chars(p, voice, model)
    usd = chars / 1000 * dub.TTS_MODELS.get(model, ('', 0.08))[1]
    return jsonify(chars=chars, total=sum(len(b['text']) for b in p['blocks']), usd=round(usd, 3))


@app.post('/api/projects/<pid>/dub')
def api_dub(pid):
    p = _get(pid)
    if pid in ACTIVE:
        return jsonify(error='Đang chạy'), 409
    if not p.get('blocks'):
        return jsonify(error='Chưa có lời, chạy nhận dạng trước'), 400
    data = request.get_json(force=True, silent=True) or {}
    voice = (data.get('voice') or '').strip()
    if not voice:
        return jsonify(error='Chưa chọn giọng'), 400
    if not os.path.isfile(p['source']):
        return jsonify(error=f"Không còn file video gốc: {p['source']}"), 400
    model = data.get('model') if data.get('model') in dub.TTS_MODELS else dub.DEFAULT_TTS_MODEL
    p['dub_opts'] = {'voice': voice, 'model': model,
                     'duck': _num(data, 'duck', 0.15, 0, 1),
                     'max_tempo': _num(data, 'max_tempo', 1.25, 1, 2),
                     'fade_in': _num(data, 'fade_in', 0.25, 0.02, 2),
                     'fade_out': _num(data, 'fade_out', 0.4, 0.02, 3),
                     'shorten': bool(data.get('shorten', True))}
    p['stage'] = 'dub'
    p['state'] = 'queued'
    p['msg'] = 'Đang chờ...'
    p.pop('result', None)
    dub.save_project(p)
    dub.save_settings(voice=voice)
    _enqueue(p)
    return jsonify(ok=True)


@app.post('/api/projects/<pid>/retry')
def api_retry(pid):
    p = _get(pid)
    if pid in ACTIVE:
        return jsonify(error='Đang chạy'), 409
    p['stage'] = 'analyze'
    p['state'] = 'queued'
    _enqueue(p)
    return jsonify(ok=True)


@app.post('/api/projects/<pid>/cancel')
def api_cancel(pid):
    if pid in ACTIVE:
        _cancel.add(pid)
    return jsonify(ok=True)


@app.get('/files/<pid>/<path:rel>')
def files(pid, rel):
    return send_from_directory(dub.project_dir(pid), rel, conditional=True)


@app.post('/api/open/<pid>')
def api_open(pid):
    os.startfile(dub.project_dir(pid))
    return jsonify(ok=True)


@app.post('/api/pick-file')
def api_pick():
    ps = ("Add-Type -AssemblyName System.Windows.Forms; "
          "$f = New-Object System.Windows.Forms.OpenFileDialog; "
          "$f.Filter = 'Video|*.mp4;*.mov;*.mkv;*.webm;*.avi;*.m4v|Tat ca|*.*'; "
          "$f.Title = 'Chon video'; "
          "$null = $f.ShowDialog((New-Object System.Windows.Forms.Form -Property @{TopMost=$true})); "
          "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Write-Output $f.FileName")
    r = subprocess.run(['powershell', '-NoProfile', '-STA', '-Command', ps], capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=600, creationflags=_CFLAGS)
    return jsonify(path=r.stdout.strip())


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5013, debug=False)
