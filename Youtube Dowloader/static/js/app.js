// ═══════════════════════════════════════════════════════════════════════
//  YouTube Downloader — Frontend Logic
//  Single-file JS for simplicity; all state & DOM logic here.
// ═══════════════════════════════════════════════════════════════════════

// ── Global State ─────────────────────────────────────────────────────
let socket = null;
let videoInfoList = [];
let taskMap = {};
let completedCount = 0;
let totalDownloads = 0;

// ── Server connection ────────────────────────────────────────────────────
//  This window and the Flask server are separate processes. Stopping the tool
//  in Tool Manager (or a server crash) leaves the window open but blind, and
//  every fetch() then fails with the browser's raw "Failed to fetch". Route all
//  API calls through api() so that case is reported in a way the user can act on.
const OFFLINE_MSG = 'Mất kết nối tới server của tool (server đã tắt). ' +
    'Quay lại Tool Manager, bấm "Dừng" rồi "Chạy" lại YouTube Downloader.';

function setServerOffline(offline) {
    let bar = document.getElementById('server-offline-bar');
    if (!offline) {
        if (bar) bar.remove();
        return;
    }
    if (bar) return;
    bar = document.createElement('div');
    bar.id = 'server-offline-bar';
    bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;padding:10px 16px;' +
        'background:#7f1d1d;color:#fee2e2;font-size:13px;font-weight:600;text-align:center;' +
        'box-shadow:0 2px 12px rgba(0,0,0,.4)';
    bar.innerHTML = '<i class="fas fa-plug"></i> ' + OFFLINE_MSG;
    document.body.appendChild(bar);
}

/** fetch() wrapper that turns a dead server into an actionable message. */
async function api(url, options) {
    let res;
    try {
        res = await fetch(url, options);
    } catch (e) {
        setServerOffline(true);
        throw new Error(OFFLINE_MSG);
    }
    setServerOffline(false);
    if (!res.ok) {
        throw new Error(`Server báo lỗi ${res.status} — xem log tại Tool/logs/downloader.log`);
    }
    return res;
}

// ── Init ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Load default download dir
    api('/api/default-dir')
        .then(r => r.json())
        .then(d => {
            document.getElementById('download-dir').value = d.default_dir;
        })
        .catch(() => { /* banner already shown by api() */ });

    // Connect SocketIO. The client script comes from a CDN, so it can be
    // missing when offline — that must not kill the rest of init.
    try {
        socket = io();
        socket.on('download_progress', handleProgress);
        socket.on('queue_item', handleQueueItem);
        socket.on('connect', () => setServerOffline(false));
        socket.on('disconnect', () => setServerOffline(true));
    } catch (e) {
        console.error('socket.io unavailable', e);
        showToast('Không tải được socket.io — thanh tiến trình sẽ không cập nhật.', 'warning');
    }

    // Load initial state
    loadHistory();
    loadQueue();
    refreshCookieStatus();
});

// ── Cookie Management ────────────────────────────────────────────────
async function refreshCookieStatus() {
    try {
        const res = await api('/api/cookies/status');
        const d = await res.json();
        const badge = document.getElementById('cookie-status-badge');
        const text = document.getElementById('cookie-status-text');
        if (!badge || !text) return;

        if (!d.exists || !d.valid) {
            badge.innerHTML = '<span style="color:#ef4444"><i class="fas fa-circle-xmark"></i> Chưa có cookie</span>';
            text.innerHTML = '<i class="fas fa-triangle-exclamation"></i> Chưa có cookie. Nếu gặp lỗi chống bot, hãy nhập cookies.txt.';
        } else {
            const old = d.age_days != null && d.age_days > 30;
            const color = old ? '#f59e0b' : '#22c55e';
            const icon = old ? 'fa-clock' : 'fa-circle-check';
            const ageStr = d.age_days != null ? `${d.age_days} ngày trước` : '';
            badge.innerHTML = `<span style="color:${color}"><i class="fas ${icon}"></i> ${d.count} cookie</span>`;
            text.innerHTML = `<i class="fas fa-info-circle"></i> Đã có cookie (${d.count} mục, cập nhật ${ageStr}).` +
                (old ? ' <b style="color:#f59e0b">Cookie hơi cũ — nếu lỗi hãy làm mới.</b>' : '');
        }
    } catch (e) {
        console.error('cookie status error', e);
    }
}

async function importCookies() {
    const btn = document.getElementById('btn-import-cookie');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang mở hộp thoại...';
    try {
        const res = await api('/api/cookies/import', { method: 'POST' });
        const d = await res.json();
        if (d.success) {
            showToast(`Đã nhập cookie thành công (${d.count} mục)!`, 'success');
            refreshCookieStatus();
        } else {
            showToast(d.error || 'Không nhập được cookie', 'error');
        }
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = orig;
    }
}

/** Open the in-app YouTube login window; the server saves cookies.txt for us. */
async function autoLoginCookies() {
    const btn = document.getElementById('btn-auto-cookie');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang chờ đăng nhập...';
    showToast('Cửa sổ đăng nhập YouTube đang mở. Đăng nhập xong, tool tự lưu cookie.', 'success');
    try {
        const res = await api('/api/cookies/auto', { method: 'POST' });
        const d = await res.json();
        if (d.success) {
            showToast(`Đã lưu cookie mới (${d.count} mục)!`, 'success');
            refreshCookieStatus();
        } else {
            showToast(d.error || 'Không lấy được cookie', 'error');
        }
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = orig;
    }
}

function toggleCookieHelp() {
    const el = document.getElementById('cookie-help');
    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

// ── Fetch Video Info ─────────────────────────────────────────────────
async function fetchVideoInfo() {
    const urlText = document.getElementById('url-input').value.trim();
    if (!urlText) {
        showToast('Vui lòng nhập ít nhất một link YouTube.', 'error');
        return;
    }

    const urls = urlText.split('\n').map(u => u.trim()).filter(Boolean);
    const btn = document.getElementById('btn-fetch');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Đang lấy thông tin...';

    try {
        const res = await api('/api/fetch-info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls }),
        });
        const data = await res.json();

        videoInfoList = data.results.filter(r => r.success);
        const errors = data.results.filter(r => !r.success);
        const dups = videoInfoList.filter(v => v.already_downloaded);

        renderVideoList();

        if (errors.length) showToast(`${errors.length} link lỗi hoặc không tìm thấy.`, 'error');
        if (dups.length) showToast(`${dups.length} video đã tải trước đó!`, 'warning');
        if (videoInfoList.length) {
            showToast(`Tìm thấy ${videoInfoList.length} video.`, 'success');
            document.getElementById('btn-download').disabled = false;
        }
    } catch (err) {
        showToast('Lỗi kết nối: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search"></i> Lấy thông tin video';
    }
}

function renderVideoList() {
    const card = document.getElementById('video-list-card');
    const list = document.getElementById('video-list');
    const statsBar = document.getElementById('stats-bar');

    if (!videoInfoList.length) {
        card.style.display = 'none';
        return;
    }

    card.style.display = '';
    statsBar.style.display = '';

    document.getElementById('stat-total').textContent = videoInfoList.length;
    const totalDur = videoInfoList.reduce((a, v) => a + (v.duration || 0), 0);
    document.getElementById('stat-duration').textContent = formatDuration(totalDur);
    document.getElementById('video-count').textContent = `${videoInfoList.length} video`;

    list.innerHTML = videoInfoList.map((v, i) => {
        const dup = v.already_downloaded
            ? `<div class="badge-dup"><i class="fas fa-exclamation-triangle"></i> Đã tải (${v.prev_download?.date || ''})</div>`
            : '';
        return `
        <div class="video-item" id="vi-${i}" ${v.already_downloaded ? 'style="border-color:rgba(245,158,11,0.25)"' : ''}>
            <img class="video-thumb" src="${v.thumbnail}" alt="" loading="lazy" onerror="this.style.display='none'">
            <div class="video-info">
                <div class="video-title" title="${esc(v.title)}">${esc(v.title)}</div>
                <div class="video-meta">
                    <span><i class="fas fa-user"></i> ${esc(v.channel)}</span>
                    <span><i class="fas fa-clock"></i> ${v.duration_formatted}</span>
                    ${v.view_count ? `<span><i class="fas fa-eye"></i> ${fmtNum(v.view_count)}</span>` : ''}
                </div>
                <div class="video-formats">${v.formats.slice(0, 5).map(f => f.resolution).join(' · ')}</div>
                ${dup}
            </div>
            <button class="video-remove" onclick="removeVideo(${i})" title="Xóa"><i class="fas fa-times"></i></button>
        </div>`;
    }).join('');
}

function removeVideo(i) {
    videoInfoList.splice(i, 1);
    renderVideoList();
    if (!videoInfoList.length) document.getElementById('btn-download').disabled = true;
}

// ── Folder Picker ────────────────────────────────────────────────────
async function browseFolder() {
    const btn = document.getElementById('btn-browse-dir');
    const input = document.getElementById('download-dir');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    try {
        const res = await api('/api/choose-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_dir: input.value.trim() }),
        });
        const d = await res.json();
        if (d.success) {
            input.value = d.path;
        }
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = orig;
    }
}

// ── Start Download ───────────────────────────────────────────────────
async function startDownload() {
    if (!videoInfoList.length) return;

    const downloadDir = document.getElementById('download-dir').value.trim();
    const maxRes = document.getElementById('resolution-select').value;
    if (!downloadDir) {
        showToast('Vui lòng chọn thư mục lưu trữ.', 'error');
        return;
    }

    const btn = document.getElementById('btn-download');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Đang khởi tạo...';

    const urls = videoInfoList.map(v => ({ url: v.url, title: v.title }));

    try {
        const res = await api('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls, download_dir: downloadDir, max_resolution: maxRes }),
        });
        const data = await res.json();

        totalDownloads = data.task_ids.length;
        completedCount = 0;
        taskMap = {};
        data.task_ids.forEach((tid, i) => {
            taskMap[tid] = {
                title: videoInfoList[i]?.title || 'Video',
                thumbnail: videoInfoList[i]?.thumbnail || '',
            };
        });

        renderDownloadProgress(data.task_ids);
        document.getElementById('progress-card').style.display = '';
        showToast(`Đang tải ${totalDownloads} video...`, 'success');
    } catch (err) {
        showToast('Lỗi: ' + err.message, 'error');
        btn.disabled = false;
    }

    btn.innerHTML = '<i class="fas fa-download"></i> Tải xuống tất cả';
}

function renderDownloadProgress(taskIds) {
    const list = document.getElementById('download-list');
    list.innerHTML = taskIds.map(tid => `
        <div class="dl-item" id="dl-${tid}">
            <div class="dl-header">
                <div class="dl-title">${esc(taskMap[tid]?.title || tid)}</div>
                <div class="dl-badge badge-queued" id="dl-status-${tid}">
                    <i class="fas fa-hourglass-start"></i> Đang chờ
                </div>
            </div>
            <div class="progress-track"><div class="progress-fill" id="dl-bar-${tid}" style="width:0%"></div></div>
            <div class="dl-meta"><span id="dl-pct-${tid}">0%</span><span id="dl-spd-${tid}"></span></div>
        </div>
    `).join('');
}

function handleProgress(data) {
    const { task_id, percent, speed, status, error, filename } = data;
    const bar = document.getElementById(`dl-bar-${task_id}`);
    const badge = document.getElementById(`dl-status-${task_id}`);
    const pct = document.getElementById(`dl-pct-${task_id}`);
    const spd = document.getElementById(`dl-spd-${task_id}`);
    const item = document.getElementById(`dl-${task_id}`);
    if (!bar) { handleQueueProgress(data); return; }

    bar.style.width = `${percent}%`;
    pct.textContent = `${percent}%`;
    spd.textContent = speed || '';

    if (status === 'queued') {
        badge.className = 'dl-badge badge-queued';
        badge.innerHTML = '<i class="fas fa-hourglass-start"></i> Đang chờ';
    } else if (status === 'downloading') {
        badge.className = 'dl-badge badge-active';
        badge.innerHTML = '<span class="spinner"></span> Đang tải';
    } else if (status === 'merging') {
        badge.className = 'dl-badge badge-merging';
        badge.innerHTML = '<i class="fas fa-compress-arrows-alt"></i> Đang ghép';
        bar.style.width = '100%';
    } else if (status === 'completed') {
        badge.className = 'dl-badge badge-done';
        badge.innerHTML = '<i class="fas fa-check-circle"></i> Hoàn thành';
        bar.classList.add('done');
        bar.style.width = '100%';
        pct.textContent = '100%';
        spd.textContent = filename || '';
        completedCount++;
        updateProgressSummary();
        if (completedCount === totalDownloads) {
            showToast(`Đã tải xong ${totalDownloads} video!`, 'success');
            document.getElementById('btn-download').disabled = false;
            loadHistory();
        }
    } else if (status === 'error') {
        badge.className = 'dl-badge badge-error';
        badge.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Lỗi';
        bar.classList.add('fail');
        if (error) {
            const errDiv = document.createElement('div');
            errDiv.className = 'dl-error';
            errDiv.textContent = error;
            item.appendChild(errDiv);
        }
        completedCount++;
        updateProgressSummary();
    }
}

function updateProgressSummary() {
    document.getElementById('progress-summary').textContent =
        `${completedCount}/${totalDownloads} hoàn thành`;
}

// ── History ──────────────────────────────────────────────────────────
async function loadHistory() {
    try {
        const res = await api('/api/history');
        const data = await res.json();
        renderHistory(data.history, data.total);
    } catch (e) { /* ignore */ }
}

function renderHistory(history, total) {
    const card = document.getElementById('history-card');
    const list = document.getElementById('history-list');

    if (!history || !history.length) {
        card.style.display = 'none';
        return;
    }

    card.style.display = '';
    document.getElementById('history-count').textContent = `(${total})`;

    list.innerHTML = history.slice(0, 40).map(h => `
        <div class="history-item">
            <div class="history-title" title="${esc(h.title)}">${esc(h.title)}</div>
            <div class="history-meta">
                <span><i class="fas fa-tv"></i> ${h.resolution || ''}</span>
                <span><i class="fas fa-calendar"></i> ${h.date || ''}</span>
            </div>
        </div>
    `).join('');
}

async function clearHistory() {
    if (!confirm('Xóa toàn bộ lịch sử tải xuống?')) return;
    try {
        await api('/api/history/clear', { method: 'POST' });
        loadHistory();
        showToast('Đã xóa lịch sử.', 'success');
    } catch (e) {
        showToast('Lỗi khi xóa lịch sử.', 'error');
    }
}

// ── Utilities ────────────────────────────────────────────────────────
function formatDuration(s) {
    if (!s) return '00:00';
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

function fmtNum(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n.toString();
}

function esc(t) {
    const d = document.createElement('div');
    d.textContent = t || '';
    return d.innerHTML;
}

function showToast(msg, type = 'success') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    const icons = { success: 'check-circle', error: 'exclamation-circle', warning: 'exclamation-triangle' };
    t.innerHTML = `<i class="fas fa-${icons[type] || 'info-circle'}"></i> ${msg}`;
    c.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        t.style.transform = 'translateX(30px)';
        t.style.transition = 'all 0.35s ease';
        setTimeout(() => t.remove(), 350);
    }, 4500);
}

// ── Repair tool ──────────────────────────────────────────────────────
async function repairTool() {
    if (!confirm('Xóa cache yt-dlp để sửa lỗi?')) return;
    try {
        const res = await api('/api/repair', { method: 'POST' });
        const data = await res.json();
        showToast(data.success ? 'Đã dọn cache!' : 'Không thể dọn cache.', data.success ? 'success' : 'error');
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    }
}

// ── Danh sách chờ ────────────────────────────────────────────────────
//  Link nhập sẵn, mỗi link một nút "Tải". Trạng thái lưu ở server
//  (download_queue.json) nên mở lại tool vẫn còn.
let queueItems = [];
let queueFilter = 'all';
const queueTaskToItem = {};   // task_id -> item id (để vẽ tiến trình vào đúng dòng)

async function loadQueue() {
    try {
        const res = await api('/api/queue');
        const d = await res.json();
        queueItems = d.items || [];
        queueItems.forEach(it => { if (it.task_id && it.status === 'downloading') queueTaskToItem[it.task_id] = it.id; });
        renderQueue();
    } catch (e) { /* banner already shown by api() */ }
}

function toggleQueueImport(show) {
    const box = document.getElementById('queue-import');
    const open = show !== undefined ? show : box.style.display === 'none';
    box.style.display = open ? '' : 'none';
    if (open) document.getElementById('queue-input').focus();
}

async function importQueue() {
    const ta = document.getElementById('queue-input');
    const text = ta.value.trim();
    if (!text) { showToast('Dán ít nhất một link trước.', 'error'); return; }
    const btn = document.getElementById('btn-queue-import');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Đang thêm...';
    try {
        const res = await api('/api/queue/import', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        const d = await res.json();
        if (!d.success) { showToast(d.error || 'Không nhập được.', 'error'); return; }
        queueItems = d.items || [];
        renderQueue();
        ta.value = '';
        toggleQueueImport(false);
        let msg = `Đã thêm ${d.added} link.`;
        if (d.already_done) msg += ` ${d.already_done} link đã tải trước đó → đánh dấu Xong.`;
        if (d.skipped) msg += ` ${d.skipped} link đã có trong danh sách, bỏ qua.`;
        showToast(msg, d.added ? 'success' : 'warning');
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = orig;
    }
}

function setQueueFilter(f) {
    queueFilter = f;
    document.querySelectorAll('#queue-filter .chip').forEach(c => c.classList.toggle('active', c.dataset.f === f));
    renderQueue();
}

function queueStatusBadge(it) {
    switch (it.status) {
        case 'done':        return '<span class="dl-badge badge-done"><i class="fas fa-check-circle"></i> Xong' + (it.done_at ? ` · ${esc(it.done_at)}` : '') + '</span>';
        case 'downloading': return '<span class="dl-badge badge-active"><span class="spinner"></span> Đang tải</span>';
        case 'error':       return '<span class="dl-badge badge-error"><i class="fas fa-exclamation-triangle"></i> Lỗi</span>';
        default:            return '<span class="dl-badge badge-queued"><i class="far fa-circle"></i> Chưa tải</span>';
    }
}

function renderQueue() {
    const list = document.getElementById('queue-list');
    const count = document.getElementById('queue-count');
    const done = queueItems.filter(i => i.status === 'done').length;
    count.textContent = queueItems.length ? `(${done}/${queueItems.length} xong)` : '';

    const shown = queueItems.filter(it =>
        queueFilter === 'all' ? true :
        queueFilter === 'done' ? it.status === 'done' : it.status !== 'done');

    if (!shown.length) {
        list.innerHTML = `<div class="q-empty"><i class="fas fa-inbox"></i>${
            queueItems.length ? 'Không có mục nào ở mục lọc này.' : 'Chưa có link nào. Bấm <b>Nhập link</b> để dán danh sách.'}</div>`;
        return;
    }

    list.innerHTML = shown.map(it => {
        const idx = queueItems.indexOf(it) + 1;
        const title = it.title ? esc(it.title) : esc(it.url);
        const busy = it.status === 'downloading';
        const mainBtn = it.status === 'done'
            ? `<button class="btn btn-ghost" onclick="markQueue('${it.id}','pending')" title="Đưa về Chưa tải"><i class="fas fa-rotate-left"></i> Chưa tải</button>`
            : `<button class="btn btn-primary" onclick="downloadQueueItem('${it.id}')" ${busy ? 'disabled' : ''}>
                   ${busy ? '<span class="spinner"></span> Đang tải' : `<i class="fas fa-download"></i> ${it.status === 'error' ? 'Tải lại' : 'Tải'}`}
               </button>`;
        const markDone = it.status === 'done' || busy ? '' :
            `<button class="btn-icon" onclick="markQueue('${it.id}','done')" title="Đánh dấu Xong (đã tải bằng cách khác)"><i class="fas fa-check"></i></button>`;
        const fileName = it.filepath ? it.filepath.split(/[\\/]/).pop() : '';
        return `
        <div class="q-item is-${it.status}" id="q-${it.id}">
            <div class="q-idx">${idx}</div>
            <div class="q-main">
                <div class="q-title"><a href="${esc(it.url)}" target="_blank" rel="noopener" title="${esc(it.url)}">${title}</a></div>
                ${it.title ? `<div class="q-url">${esc(it.url)}</div>` : ''}
                <div class="q-sub">${queueStatusBadge(it)}${fileName ? `<span title="${esc(it.filepath)}"><i class="fas fa-file-video"></i> ${esc(fileName)}</span>` : ''}</div>
                ${it.error && it.status === 'error' ? `<div class="q-err">${esc(it.error)}</div>` : ''}
                <div class="q-progress" id="qp-${it.id}" style="display:${busy ? '' : 'none'}">
                    <div class="progress-track"><div class="progress-fill" id="qp-bar-${it.id}" style="width:0%"></div></div>
                    <div class="dl-meta"><span id="qp-pct-${it.id}">0%</span><span id="qp-spd-${it.id}"></span></div>
                </div>
            </div>
            <div class="q-actions">
                ${mainBtn}
                ${markDone}
                <button class="btn-icon danger" onclick="removeQueueItem('${it.id}')" title="Bỏ khỏi danh sách" ${busy ? 'disabled' : ''}><i class="fas fa-times"></i></button>
            </div>
        </div>`;
    }).join('');
}

async function downloadQueueItem(id) {
    const downloadDir = document.getElementById('download-dir').value.trim();
    const maxRes = document.getElementById('resolution-select').value;
    if (!downloadDir) { showToast('Vui lòng chọn thư mục lưu trữ.', 'error'); return; }
    try {
        const res = await api(`/api/queue/${id}/download`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ download_dir: downloadDir, max_resolution: maxRes }),
        });
        const d = await res.json();
        if (!d.success) { showToast(d.error || 'Không tải được.', 'error'); return; }
        queueTaskToItem[d.task_id] = id;
        handleQueueItem(d.item);
        showToast('Bắt đầu tải. Xong sẽ tự đánh dấu.', 'success');
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    }
}

async function markQueue(id, status) {
    try {
        const res = await api(`/api/queue/${id}/mark`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status }),
        });
        const d = await res.json();
        if (d.success) handleQueueItem(d.item);
        else showToast(d.error || 'Không đánh dấu được.', 'error');
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    }
}

async function removeQueueItem(id) {
    try {
        await api(`/api/queue/${id}`, { method: 'DELETE' });
        queueItems = queueItems.filter(it => it.id !== id);
        renderQueue();
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    }
}

async function clearQueueDone() {
    const n = queueItems.filter(i => i.status === 'done').length;
    if (!n) { showToast('Không có mục nào đã xong.', 'warning'); return; }
    if (!confirm(`Bỏ ${n} mục đã tải xong khỏi danh sách chờ? (Lịch sử tải vẫn giữ.)`)) return;
    try {
        await api('/api/queue/clear-done', { method: 'POST' });
        loadQueue();
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    }
}

/** Server báo một mục đổi trạng thái (bắt đầu tải, xong, lỗi). */
function handleQueueItem(item) {
    if (!item) return;
    const i = queueItems.findIndex(it => it.id === item.id);
    const wasDone = i >= 0 && queueItems[i].status === 'done';
    if (i >= 0) queueItems[i] = item; else queueItems.push(item);
    if (item.task_id) queueTaskToItem[item.task_id] = item.id;
    renderQueue();
    if (item.status === 'done' && !wasDone && item.filepath) {
        showToast(`Tải xong: ${item.title || item.url}`, 'success');
        loadHistory();
    } else if (item.status === 'error') {
        showToast(`Lỗi tải: ${item.title || item.url}`, 'error');
    }
}

/** Vẽ tiến trình của một task thuộc danh sách chờ vào đúng dòng. */
function handleQueueProgress(data) {
    const id = queueTaskToItem[data.task_id];
    if (!id) return false;
    const box = document.getElementById(`qp-${id}`);
    if (!box) return true;
    box.style.display = '';
    const bar = document.getElementById(`qp-bar-${id}`);
    const pct = document.getElementById(`qp-pct-${id}`);
    const spd = document.getElementById(`qp-spd-${id}`);
    if (data.status === 'merging') {
        bar.style.width = '100%'; pct.textContent = 'Đang ghép video + audio...'; spd.textContent = '';
    } else {
        bar.style.width = `${data.percent}%`;
        pct.textContent = `${data.percent}%`;
        spd.textContent = data.speed || '';
    }
    return true;
}
