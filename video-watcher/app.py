"""
Video Watcher — giao diện web cho watcher.py.
Chạy qua launcher (run.pyw → _tool_server.py) ở cổng 5011, hoặc: py app.py
"""
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import watcher

app = Flask(__name__)
OUT = watcher.OUTPUT_DIR
UPLOAD_DIR = os.path.join(watcher.BASE_DIR, 'uploads')
os.makedirs(OUT, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
_CFLAGS = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

JOBS = {}
_q = queue.Queue()


def _worker():
    # Một video mỗi lúc: Whisper + ffmpeg đã ăn hết GPU/CPU, chạy song song chỉ chậm hơn.
    while True:
        jid = _q.get()
        job = JOBS[jid]
        job['state'] = 'running'
        job['started'] = time.time()

        def log(msg, job=job):
            job['log'].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            job['msg'] = msg

        try:
            o = job['opts']
            res = watcher.analyze(job['source'], max_frames=o['max_frames'], model=o['model'],
                                  lang=o['lang'], do_transcript=o['transcript'], scene=o['scene'],
                                  hook_seconds=o['hook'], log=log)
            job['result'] = os.path.basename(res['out'])
            job['report'] = res['report']
            job['state'] = 'done'
        except Exception as e:
            log(f'LỖI: {e}')
            job['state'] = 'error'
            job['error'] = str(e)
        finally:
            if job.get('uploaded'):
                try:
                    os.remove(job['source'])
                    os.rmdir(os.path.dirname(job['source']))
                except OSError:
                    pass
            _q.task_done()


threading.Thread(target=_worker, daemon=True).start()


def _safe_dir(name):
    d = os.path.realpath(os.path.join(OUT, name))
    if not d.startswith(os.path.realpath(OUT) + os.sep) or not os.path.isdir(d):
        abort(404)
    return d


def _opts(data):
    def num(k, d, lo, hi, cast=int):
        try:
            return max(lo, min(hi, cast(data.get(k, d))))
        except (TypeError, ValueError):
            return d
    return {
        'max_frames': num('max_frames', 60, 8, 200),
        'model': data.get('model') if data.get('model') in ('tiny', 'base', 'small', 'large-v3') else 'small',
        'lang': (data.get('lang') or 'auto').strip()[:8],
        'transcript': str(data.get('transcript', 'true')).lower() not in ('false', '0', 'off'),
        'scene': num('scene', 0.30, 0.05, 0.9, float),
        'hook': num('hook', 15, 3, 60),
    }


def _enqueue(source, opts, uploaded=False):
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {'id': jid, 'source': source, 'opts': opts, 'state': 'queued', 'msg': 'Đang chờ...',
                 'log': [], 'uploaded': uploaded, 'created': time.time()}
    _q.put(jid)
    return jid


@app.route('/')
def index():
    return render_template('index.html')


@app.post('/api/analyze')
def api_analyze():
    data = request.get_json(force=True, silent=True) or {}
    src = (data.get('source') or '').strip().strip('"')
    if not src:
        return jsonify(error='Chưa nhập đường dẫn hoặc URL'), 400
    if not src.lower().startswith(('http://', 'https://')) and not os.path.isfile(src):
        return jsonify(error=f'Không thấy file: {src}'), 400
    return jsonify(id=_enqueue(src, _opts(data)))


@app.post('/api/upload')
def api_upload():
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify(error='Không có file'), 400
    name = os.path.basename(f.filename)
    dst = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:6]}_{name}")
    f.save(dst)
    # Giữ tên gốc cho tiêu đề báo cáo: đổi về tên thật trong thư mục con riêng.
    sub = os.path.join(UPLOAD_DIR, uuid.uuid4().hex[:8])
    os.makedirs(sub, exist_ok=True)
    final = os.path.join(sub, name)
    shutil.move(dst, final)
    return jsonify(id=_enqueue(final, _opts(request.form), uploaded=True))


@app.get('/api/jobs/<jid>')
def api_job(jid):
    j = JOBS.get(jid)
    if not j:
        return jsonify(error='Không có job'), 404
    pos = sum(1 for x in JOBS.values() if x['state'] == 'queued' and x['created'] < j['created'])
    return jsonify({k: j.get(k) for k in ('id', 'state', 'msg', 'error', 'result', 'report')} |
                   {'log': j['log'][-40:], 'queue_pos': pos})


@app.get('/api/history')
def api_history():
    items = []
    for name in sorted(os.listdir(OUT), reverse=True):
        p = os.path.join(OUT, name, 'analysis.json')
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding='utf-8') as fh:
                m = json.load(fh)
        except Exception:
            continue
        thumb = m['frames'][min(len(m['frames']) - 1, 1)]['file'] if m.get('frames') else None
        items.append({'name': name, 'title': m.get('title'), 'created': m.get('created'),
                      'duration': m['probe']['duration'], 'format': m['probe']['format_label'],
                      'shots': m['pacing']['shot_count'], 'thumb': thumb,
                      'has_breakdown': os.path.isfile(os.path.join(OUT, name, 'BREAKDOWN.md'))})
    return jsonify(items)


@app.get('/api/result/<name>')
def api_result(name):
    d = _safe_dir(name)
    with open(os.path.join(d, 'analysis.json'), encoding='utf-8') as fh:
        m = json.load(fh)
    bd = os.path.join(d, 'BREAKDOWN.md')
    m['breakdown'] = open(bd, encoding='utf-8').read() if os.path.isfile(bd) else None
    m['dir'] = d
    m['report_path'] = os.path.join(d, 'REPORT.md')
    return jsonify(m)


@app.get('/files/<name>/<path:rel>')
def files(name, rel):
    return send_from_directory(_safe_dir(name), rel)


@app.post('/api/open/<name>')
def api_open(name):
    os.startfile(_safe_dir(name))
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
    app.run(host='127.0.0.1', port=5011, debug=False)
