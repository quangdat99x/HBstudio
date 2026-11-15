/* ============================================================
   Video Cutter Portable — Frontend Logic
   ============================================================ */

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let transcript = [];
let segments = JSON.parse(localStorage.getItem("vc_segments") || "[]");
let videoLoaded = false;
let cutPollId = null;

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
function toast(msg, type = "info") {
    let container = document.querySelector(".toast-container");
    if (!container) {
        container = document.createElement("div");
        container.className = "toast-container";
        document.body.appendChild(container);
    }
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => { el.remove(); }, 4000);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmtTime(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function parseTime(ts) {
    ts = ts.trim();
    const num = parseFloat(ts);
    if (!isNaN(num) && !ts.includes(":")) return num;
    const parts = ts.split(":");
    if (parts.length === 3) return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2]);
    if (parts.length === 2) return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
    return 0;
}

function saveSegments() {
    localStorage.setItem("vc_segments", JSON.stringify(segments));
}

// ---------------------------------------------------------------------------
// Select Video
// ---------------------------------------------------------------------------
async function selectVideo() {
    $("btn-select-video").disabled = true;
    $("video-info").textContent = "Đang mở hộp thoại...";

    try {
        const res = await fetch("/api/select-video", { method: "POST" });
        const data = await res.json();

        if (data.error) {
            toast(data.error, "error");
            $("video-info").textContent = "Chưa chọn video";
            return;
        }

        // Update UI
        $("video-info").textContent = data.video_name;
        $("video-info").classList.add("loaded");

        // Load video player
        const player = $("video-player");
        showVideoLoadingOverlay();
        player.src = "/api/video?t=" + Date.now();
        player.load();
        $("video-placeholder").classList.add("hidden");
        $("video-area").classList.remove("hidden");
        $("card-segments").classList.remove("hidden");
        videoLoaded = true;

        // --- Clear old transcript data for new video ---
        transcript = [];
        $("transcript-list").innerHTML = "";
        $("card-transcript").classList.add("hidden");

        // Transcript
        if (data.transcript_found) {
            $("transcript-status").innerHTML =
                `<span class="material-icons-round" style="color:var(--success);font-size:16px;vertical-align:middle">check_circle</span> ` +
                `Transcript: <strong>${data.transcript_file}</strong> (${data.transcript_count} đoạn)`;
            $("btn-load-transcript").style.display = "inline-flex";
            loadTranscriptData();
        } else {
            $("transcript-status").innerHTML =
                `<span class="material-icons-round" style="color:var(--warning);font-size:16px;vertical-align:middle">warning</span> ` +
                `Chưa có transcript. Dùng Whisper hoặc chọn file thủ công.`;
            $("btn-load-transcript").style.display = "inline-flex";
        }
        $("transcript-row").style.display = "flex";

        // Show Whisper panel (always, for re-transcription option)
        showWhisperPanel();

        // Render segments if any saved
        renderSegments();
        toast(`Đã load: ${data.video_name}`, "success");

    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
        $("video-info").textContent = "Chưa chọn video";
    } finally {
        $("btn-select-video").disabled = false;
    }
}

// ---------------------------------------------------------------------------
// Video loading overlay (% buffered while the video downloads)
// ---------------------------------------------------------------------------
function showVideoLoadingOverlay() {
    const overlay = $("video-loading-overlay");
    if (!overlay) return;
    overlay.classList.remove("hidden");
    $("video-loading-pct").textContent = "0%";
}

function hideVideoLoadingOverlay() {
    const overlay = $("video-loading-overlay");
    if (overlay) overlay.classList.add("hidden");
}

function updateVideoLoadingPct() {
    const player = $("video-player");
    const overlay = $("video-loading-overlay");
    if (!player || !overlay || overlay.classList.contains("hidden")) return;

    const duration = player.duration;
    if (!duration || !isFinite(duration) || player.buffered.length === 0) return;

    const bufferedEnd = player.buffered.end(player.buffered.length - 1);
    const pct = Math.min(100, Math.round((bufferedEnd / duration) * 100));
    $("video-loading-pct").textContent = pct + "%";

    if (pct >= 100) hideVideoLoadingOverlay();
}

// ---------------------------------------------------------------------------
// Load Transcript
// ---------------------------------------------------------------------------
async function loadTranscript() {
    try {
        const res = await fetch("/api/load-transcript", { method: "POST" });
        const data = await res.json();
        if (data.error) { toast(data.error, "error"); return; }

        $("transcript-status").innerHTML =
            `<span class="material-icons-round" style="color:var(--success);font-size:18px;vertical-align:middle">check_circle</span> ` +
            `Transcript: <strong>${data.transcript_file}</strong> (${data.transcript_count} đoạn)`;
        loadTranscriptData();
        toast(`Đã load transcript: ${data.transcript_file}`, "success");
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    }
}

async function loadTranscriptData() {
    try {
        const res = await fetch("/api/transcript");
        const data = await res.json();
        transcript = data.segments || [];
        renderTranscript();
    } catch (e) {
        console.error("Failed to load transcript:", e);
    }
}

// ---------------------------------------------------------------------------
// Transcript Panel
// ---------------------------------------------------------------------------
let transcriptCollapsed = false;

function renderTranscript() {
    if (!transcript.length) {
        $("card-transcript").classList.add("hidden");
        return;
    }

    $("card-transcript").classList.remove("hidden");
    $("seg-count").textContent = `${transcript.length} đoạn`;

    let html = "";
    for (let i = 0; i < transcript.length; i++) {
        const seg = transcript[i];
        const hasWords = seg.words && seg.words.length > 0;

        // Build text content: word-level spans if available, else plain text
        let textContent = "";
        if (hasWords) {
            textContent = seg.words.map((w, wi) =>
                `<span class="tword" data-seg="${i}" data-wi="${wi}" data-start="${w.start}" data-end="${w.end}"` +
                ` onclick="event.stopPropagation(); onWordClick(${i}, ${wi})"` +
                ` title="${fmtTime(w.start)} → ${fmtTime(w.end)}"` +
                `>${escapeHtml(w.word)}</span>`
            ).join(" ");
        } else {
            textContent = escapeHtml(seg.text);
        }

        html += `<div class="transcript-seg" data-idx="${i}" data-start="${seg.start}" onclick="seekTo(${seg.start})">
            <span class="ts">${fmtTime(seg.start)}</span>
            <span class="txt">${textContent}</span>
        </div>`;
    }
    $("transcript-list").innerHTML = html;
}

function toggleTranscript() {
    transcriptCollapsed = !transcriptCollapsed;
    $("transcript-body").classList.toggle("collapsed", transcriptCollapsed);
    $("transcript-chevron").classList.toggle("rotated", transcriptCollapsed);
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// Auto-highlight active transcript segment
function updateActiveTranscript() {
    const player = $("video-player");
    if (!player || !transcript.length) return;

    const time = player.currentTime;
    const segs = document.querySelectorAll(".transcript-seg");

    let activeIdx = -1;
    for (let i = 0; i < transcript.length; i++) {
        if (time >= transcript[i].start && time < (transcript[i].end || transcript[i].start + 10)) {
            activeIdx = i;
            break;
        }
    }

    segs.forEach((el, i) => {
        el.classList.toggle("active", i === activeIdx);
    });

    // Auto-scroll to active
    if (activeIdx >= 0 && segs[activeIdx] && !transcriptCollapsed) {
        segs[activeIdx].scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

// ---------------------------------------------------------------------------
// Video Player
// ---------------------------------------------------------------------------
function seekTo(sec) {
    const player = $("video-player");
    if (player) {
        player.currentTime = sec;
        player.play();
    }
}

function skip(sec) {
    const player = $("video-player");
    if (player) player.currentTime = Math.max(0, player.currentTime + sec);
}

function togglePlay() {
    const player = $("video-player");
    if (!player) return;
    if (player.paused) { player.play(); } else { player.pause(); }
}

// Update current time display + play icon
document.addEventListener("DOMContentLoaded", () => {
    const player = $("video-player");
    if (player) {
        player.addEventListener("timeupdate", () => {
            $("current-time").textContent = fmtTime(player.currentTime);
            updateActiveTranscript();
        });
        player.addEventListener("play", () => {
            $("play-icon").textContent = "pause";
        });
        player.addEventListener("pause", () => {
            $("play-icon").textContent = "play_arrow";
        });

        // --- Loading progress overlay ---
        player.addEventListener("progress", updateVideoLoadingPct);
        player.addEventListener("loadedmetadata", updateVideoLoadingPct);
        player.addEventListener("canplay", hideVideoLoadingOverlay);
        player.addEventListener("loadeddata", hideVideoLoadingOverlay);
        player.addEventListener("error", hideVideoLoadingOverlay);
    }

    // Keyboard shortcuts
    document.addEventListener("keydown", (e) => {
        // Don't trigger when typing in inputs
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

        const player = $("video-player");
        if (!player) return;

        if (e.code === "Space") {
            e.preventDefault();
            togglePlay();
        } else if (e.code === "ArrowLeft") {
            e.preventDefault();
            skip(e.shiftKey ? -30 : -5);
        } else if (e.code === "ArrowRight") {
            e.preventDefault();
            skip(e.shiftKey ? 30 : 5);
        }
    });

    // Render saved segments
    renderSegments();
});

// ---------------------------------------------------------------------------
// Cut Segments
// ---------------------------------------------------------------------------
function addSegment() {
    const player = $("video-player");
    const currentTime = player ? fmtTime(player.currentTime) : "00:00:00";

    segments.push({
        start: currentTime,
        end: "00:00:00",
        title: "",
    });
    saveSegments();
    renderSegments();
}

function removeSegment(idx) {
    segments.splice(idx, 1);
    saveSegments();
    renderSegments();
}

function updateSegment(idx, field, value) {
    if (segments[idx]) {
        segments[idx][field] = value;
        saveSegments();
    }
}

function setCurrentTime(idx, field) {
    const player = $("video-player");
    if (!player) { toast("Chưa load video", "error"); return; }

    const time = fmtTime(player.currentTime);
    segments[idx][field] = time;
    saveSegments();
    renderSegments();
    toast(`Đã lấy thời gian: ${time}`, "info");
}

function previewSegment(idx) {
    const seg = segments[idx];
    if (!seg) return;

    const player = $("video-player");
    if (!player) { toast("Chưa load video", "error"); return; }

    const startSec = parseTime(seg.start);
    const endSec = parseTime(seg.end);

    if (endSec <= startSec) {
        toast("Thời gian kết thúc phải sau thời gian bắt đầu", "error");
        return;
    }

    player.currentTime = startSec;
    player.play();

    // Auto-pause at end
    const checkEnd = () => {
        if (player.currentTime >= endSec) {
            player.pause();
            player.removeEventListener("timeupdate", checkEnd);
        }
    };
    player.addEventListener("timeupdate", checkEnd);
    toast(`Xem trước: ${seg.start} → ${seg.end}`, "info");
}

function renderSegments() {
    const list = $("segments-list");
    if (!list) return;

    $("segments-count").textContent = segments.length;
    $("btn-export").disabled = segments.length === 0;

    if (!segments.length) {
        list.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:20px;font-size:0.9rem">
            Chưa có đoạn cắt nào. Nhấn "Thêm đoạn cắt" để bắt đầu.
        </p>`;
        renderTimelineMarkers();
        return;
    }

    // Segment colors for visual distinction
    const colors = ["#a78bfa", "#f472b6", "#34d399", "#fbbf24", "#60a5fa", "#f87171"];

    let html = "";
    segments.forEach((seg, i) => {
        const color = colors[i % colors.length];
        html += `
        <div class="segment-card" style="border-left: 3px solid ${color}">
            <div class="segment-num" style="color:${color}">Đoạn ${i + 1}</div>
            <div class="segment-row">
                <label>Bắt đầu:</label>
                <input type="text" class="time-input" id="seg-start-${i}" value="${escapeHtml(seg.start)}"
                       onchange="onSegmentInputChange(${i}, 'start', this.value)"
                       placeholder="00:00:00">
                <button class="btn-pin" onclick="pinMarker(${i}, 'start')" title="Ghim vạch trên timeline">📌</button>
                <button class="btn-set" onclick="setCurrentTime(${i}, 'start')" title="Lấy thời gian từ video player">⏱</button>
            </div>
            <div class="segment-row">
                <label>Kết thúc:</label>
                <input type="text" class="time-input" id="seg-end-${i}" value="${escapeHtml(seg.end)}"
                       onchange="onSegmentInputChange(${i}, 'end', this.value)"
                       placeholder="00:00:00">
                <button class="btn-pin" onclick="pinMarker(${i}, 'end')" title="Ghim vạch trên timeline">📌</button>
                <button class="btn-set" onclick="setCurrentTime(${i}, 'end')" title="Lấy thời gian từ video player">⏱</button>
            </div>
            <div class="segment-row">
                <label>Tên clip:</label>
                <input type="text" value="${escapeHtml(seg.title)}"
                       onchange="onSegmentInputChange(${i}, 'title', this.value)"
                       placeholder="VD: Đoạn hay về AI...">
            </div>
            <div class="segment-actions">
                <button class="btn btn-ghost btn-sm" onclick="previewSegment(${i})">
                    <span class="material-icons-round">play_circle</span>
                    Xem trước
                </button>
                <button class="btn btn-ghost btn-sm" onclick="removeSegment(${i})" style="color:var(--error)">
                    <span class="material-icons-round">delete</span>
                    Xoá
                </button>
            </div>
        </div>`;
    });
    list.innerHTML = html;
    renderTimelineMarkers();
}

function onSegmentInputChange(idx, field, value) {
    if (idx >= 0 && idx < segments.length) {
        segments[idx][field] = value;
        saveSegments();
        renderTimelineMarkers();
    }
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------
async function exportAll() {
    if (!segments.length) { toast("Chưa có đoạn cắt nào", "error"); return; }
    if (!videoLoaded) { toast("Chưa chọn video", "error"); return; }

    // Validate segments
    for (let i = 0; i < segments.length; i++) {
        const s = segments[i];
        const startSec = parseTime(s.start);
        const endSec = parseTime(s.end);
        if (endSec <= startSec) {
            toast(`Đoạn ${i + 1}: Thời gian kết thúc phải sau thời gian bắt đầu`, "error");
            return;
        }
    }

    // Step 1: Pick output folder
    toast("Chọn thư mục lưu video đã cắt...", "info");
    try {
        const folderRes = await fetch("/api/pick-folder", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "Chọn thư mục lưu video cắt" }),
        });
        const folderData = await folderRes.json();

        if (folderData.error) {
            return; // User cancelled
        }

        var outputFolder = folderData.folder;
    } catch (e) {
        toast(`Lỗi mở thư mục: ${e.message}`, "error");
        return;
    }

    // Step 2: Start cutting
    $("btn-export").disabled = true;
    $("export-progress").classList.remove("hidden");
    $("export-results").classList.add("hidden");
    $("export-fill").style.width = "0%";
    $("export-pct").textContent = "0%";
    $("export-status-text").textContent = "Đang chuẩn bị cắt video…";
    $("export-segment-label").textContent = "Đang chuẩn bị…";
    if ($("export-speed")) $("export-speed").textContent = "";
    if ($("export-eta")) $("export-eta").textContent = "";
    if ($("export-seg-pct")) $("export-seg-pct").textContent = "";

    try {
        console.log(`[Export] Sending ${segments.length} segments to /api/cut:`, JSON.stringify(segments));
        const res = await fetch("/api/cut", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ segments, output_folder: outputFolder,
                                   write_sidecars: !!(document.getElementById("chk-sidecars") && document.getElementById("chk-sidecars").checked) }),
        });
        const data = await res.json();
        console.log(`[Export] /api/cut response:`, data);

        if (data.error) {
            toast(data.error, "error");
            $("btn-export").disabled = false;
            $("export-progress").classList.add("hidden");
            return;
        }

        // Clear any stale polling from previous export
        if (cutPollId) {
            clearInterval(cutPollId);
            cutPollId = null;
        }

        // Poll progress more frequently for smooth updates
        cutPollId = setInterval(pollCutStatus, 500);
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
        $("btn-export").disabled = false;
        $("export-progress").classList.add("hidden");
    }
}

let _pollStuckSince = 0;

async function pollCutStatus() {
    try {
        const res = await fetch("/api/cut/status");
        const data = await res.json();

        console.log(`[Poll] status=${data.status}, progress=${data.progress}%, segment=${data.current_segment}/${data.total_segments}, results=${data.results?.length || 0}`);

        // Stuck detection: if still at 0% after 15 seconds, fetch debug log
        if (data.status === "running" && data.progress === 0 && data.current_segment === 0) {
            if (_pollStuckSince === 0) _pollStuckSince = Date.now();
            if (Date.now() - _pollStuckSince > 15000) {
                // Likely the thread crashed silently — fetch debug log
                try {
                    const logRes = await fetch("/api/debug-log");
                    const logData = await logRes.json();
                    console.error("[Poll] Thread stuck! Debug log:", logData.lines?.join("\n"));
                    // Show error to user
                    clearInterval(cutPollId);
                    cutPollId = null;
                    $("export-progress").classList.add("hidden");
                    $("export-results").classList.remove("hidden");
                    const logText = (logData.lines || []).slice(-10).join("\n");
                    $("results-list").innerHTML = `<div class="result-item error">
                        <span class="material-icons-round">error</span>
                        Thread cắt video bị treo. Kiểm tra file cutter.log.<br>
                        <pre style="font-size:11px;margin-top:8px;max-height:200px;overflow:auto;white-space:pre-wrap">${logText || "Không có log"}</pre>
                    </div>`;
                    toast("Thread cắt video bị treo — xem chi tiết bên dưới", "error");
                    $("btn-export").disabled = false;
                    return;
                } catch (e) {
                    console.error("Failed to fetch debug log:", e);
                }
            }
        } else {
            _pollStuckSince = 0;
        }

        $("export-fill").style.width = data.progress + "%";
        $("export-pct").textContent = data.progress + "%";

        // Current segment info
        const segLabel = $("export-segment-label");
        if (segLabel && data.current_segment) {
            const title = data.segment_title || `Đoạn ${data.current_segment}`;
            segLabel.textContent = `Đoạn ${data.current_segment}/${data.total_segments}: ${title}`;
        }

        // Status text with completed count
        const doneCount = data.results?.length || 0;
        if (data.current_segment > 0) {
            $("export-status-text").textContent =
                `Đang encode đoạn ${data.current_segment}/${data.total_segments}` +
                (doneCount > 0 ? ` (${doneCount} xong)` : ``);
        }

        // Speed, ETA, segment progress
        const speedEl = $("export-speed");
        const etaEl = $("export-eta");
        const segPctEl = $("export-seg-pct");

        if (speedEl) speedEl.textContent = data.speed ? `⚡ ${data.speed}` : "";
        if (etaEl) etaEl.textContent = data.eta ? `⏱ Còn ${data.eta}` : "";
        if (segPctEl && data.segment_progress > 0) {
            segPctEl.textContent = `📊 Đoạn: ${data.segment_progress}%`;
        } else if (segPctEl) {
            segPctEl.textContent = "";
        }

        if (data.status === "done") {
            console.log(`[Poll] === DONE === results:`, JSON.stringify(data.results));
            clearInterval(cutPollId);
            cutPollId = null;

            $("export-progress").classList.add("hidden");
            $("export-results").classList.remove("hidden");

            let html = "";
            for (const r of data.results) {
                if (r.status === "done") {
                    const fname = r.file.split(/[/\\]/).pop();
                    const warning = r.warning ? ` <span style="color:var(--warning)">(${escapeHtml(r.warning)})</span>` : "";
                    const manifestBadge = r.manifest_file
                        ? `<span class="manifest-badge" title="Skeleton manifest cho documentary builder: ${escapeHtml(r.manifest_file)}">` +
                          `<span class="material-icons-round" style="font-size:13px;vertical-align:middle">article</span> ` +
                          `manifest (${r.manifest_segments} segs)</span>`
                        : "";
                    html += `<div class="result-item done">
                        <span class="material-icons-round">check_circle</span>
                        <span>Đoạn ${r.index}: ${escapeHtml(r.title)} — ${fname}${warning}</span>
                        ${manifestBadge}
                    </div>`;
                } else {
                    html += `<div class="result-item error">
                        <span class="material-icons-round">error</span>
                        Đoạn ${r.index}: ${escapeHtml(r.title)} — Lỗi: ${escapeHtml(r.error || "?")}
                    </div>`;
                }
            }
            $("results-list").innerHTML = html;

            const finalDoneCount = data.results.filter(r => r.status === "done").length;
            toast(`Xuất xong! ${finalDoneCount}/${data.results.length} đoạn thành công`, "success");
            $("btn-export").disabled = false;
        } else if (data.status === "error") {
            // Backend thread crashed — show error and stop polling
            console.error(`[Poll] === ERROR === `, data.error);
            clearInterval(cutPollId);
            cutPollId = null;

            $("export-progress").classList.add("hidden");
            $("export-results").classList.remove("hidden");
            $("results-list").innerHTML = `<div class="result-item error">
                <span class="material-icons-round">error</span>
                Lỗi: ${escapeHtml(data.error || "Lỗi không xác định")}
            </div>`;
            toast(`Lỗi cắt video: ${data.error || "Lỗi không xác định"}`, "error");
            $("btn-export").disabled = false;
        }
    } catch (e) {
        console.error("Poll error:", e);
    }
}

// ---------------------------------------------------------------------------
// Import Cutlist (từ skill /chon-noi-dung-jre)
// ---------------------------------------------------------------------------
async function importCutlist() {
    const btn = $("btn-import-cutlist");
    btn.disabled = true;
    btn.querySelector(".material-icons-round").textContent = "sync";

    try {
        const res = await fetch("/api/import-cutlist", { method: "POST" });
        const data = await res.json();

        if (data.error) {
            toast(data.error, "error");
            return;
        }

        // Append imported segments (không xóa đoạn cũ)
        const before = segments.length;
        for (const seg of data.segments) {
            segments.push({ start: seg.start, end: seg.end, title: seg.title });
        }
        saveSegments();
        renderSegments();

        const src = data.source ? ` (${data.source})` : "";
        toast(`Đã import ${data.count} đoạn${src} — tổng: ${segments.length}`, "success");

        // Cuộn xuống danh sách đoạn cắt
        const list = $("segments-list");
        if (list) list.scrollIntoView({ behavior: "smooth", block: "start" });

    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    } finally {
        btn.disabled = false;
        btn.querySelector(".material-icons-round").textContent = "file_open";
    }
}

// ---------------------------------------------------------------------------
// Open Output
// ---------------------------------------------------------------------------
async function openOutput() {
    try {
        await fetch("/api/open-folder", { method: "POST" });
    } catch (e) {
        toast("Không mở được thư mục", "error");
    }
}

// ---------------------------------------------------------------------------
// Batch Mode — Cắt Theo Folder (Đa Tập, từ skill /tong-hop-rabbit-hole)
// ---------------------------------------------------------------------------
let batchSegments = [];
let batchFolderSelected = false;
let batchPollId = null;

async function selectSourceFolder() {
    const btn = $("btn-select-folder");
    btn.disabled = true;

    try {
        const res = await fetch("/api/select-source-folder", { method: "POST" });
        const data = await res.json();

        if (data.error) {
            toast(data.error, "error");
            return;
        }

        batchFolderSelected = true;
        $("folder-info").textContent = `${data.folder} (${data.count} video)`;
        $("folder-info").classList.add("loaded");
        toast(`Đã chọn thư mục: ${data.count} video`, "success");

        if (batchSegments.length) renderBatchSegments();

    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    } finally {
        btn.disabled = false;
    }
}

async function importCutlistMulti() {
    const btn = $("btn-import-cutlist-multi");
    btn.disabled = true;
    btn.querySelector(".material-icons-round").textContent = "sync";

    try {
        const res = await fetch("/api/import-cutlist-multi", { method: "POST" });
        const data = await res.json();

        if (data.error) {
            toast(data.error, "error");
            return;
        }

        batchSegments = data.segments;
        const themeLabel = data.theme ? ` — chủ đề: ${data.theme}` : "";
        $("batch-cutlist-info").textContent = `${data.count} đoạn${themeLabel}`;
        $("batch-cutlist-info").classList.add("loaded");

        renderBatchSegments();

        const missing = batchSegments.filter(s => !s.matched).length;
        if (!batchFolderSelected) {
            toast(`Đã import ${data.count} đoạn — chọn thư mục nguồn để tool kiểm tra khớp video`, "info");
        } else if (missing > 0) {
            toast(`Đã import ${data.count} đoạn — ${missing} đoạn KHÔNG tìm thấy video nguồn trong thư mục`, "error");
        } else {
            toast(`Đã import ${data.count} đoạn — tất cả đã khớp video nguồn`, "success");
        }

        $("batch-segments-list").scrollIntoView({ behavior: "smooth", block: "start" });

    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    } finally {
        btn.disabled = false;
        btn.querySelector(".material-icons-round").textContent = "file_open";
    }
}

function renderBatchSegments() {
    const list = $("batch-segments-list");
    if (!list) return;

    if (!batchSegments.length) {
        list.classList.add("hidden");
        $("btn-batch-cut").disabled = true;
        return;
    }

    list.classList.remove("hidden");

    let html = "";
    for (const seg of batchSegments) {
        const matched = batchFolderSelected ? !!seg.matched : true; // unknown until folder chosen
        const statusIcon = !batchFolderSelected
            ? `<span class="material-icons-round batch-seg-status" title="Chưa chọn thư mục để kiểm tra">help_outline</span>`
            : matched
                ? `<span class="material-icons-round batch-seg-status ok" title="Đã tìm thấy video nguồn">check_circle</span>`
                : `<span class="material-icons-round batch-seg-status missing" title="KHÔNG tìm thấy video nguồn trong thư mục đã chọn">error</span>`;

        html += `
        <div class="batch-seg-item ${batchFolderSelected && !matched ? "unmatched" : ""}">
            <span class="batch-seg-order">${seg.order}</span>
            <div class="batch-seg-main">
                <span class="batch-seg-title">${escapeHtml(seg.title)}</span>
                <span class="batch-seg-meta">${escapeHtml(seg.episode_id || "")} · ${escapeHtml(seg.source_video)} · ${seg.start}–${seg.end}</span>
            </div>
            ${statusIcon}
        </div>`;
    }
    list.innerHTML = html;

    const anyMissing = batchFolderSelected && batchSegments.some(s => !s.matched);
    $("btn-batch-cut").disabled = !batchFolderSelected || anyMissing;
}

async function startBatchCut() {
    if (!batchSegments.length) { toast("Chưa import cutlist đa nguồn", "error"); return; }
    if (!batchFolderSelected) { toast("Chưa chọn thư mục chứa các tập", "error"); return; }

    // Step 1: Pick output folder
    toast("Chọn thư mục lưu video đã cắt...", "info");
    let outputFolder;
    try {
        const folderRes = await fetch("/api/pick-folder", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "Chọn thư mục lưu video cắt (đa tập)" }),
        });
        const folderData = await folderRes.json();
        if (folderData.error) return; // user cancelled
        outputFolder = folderData.folder;
    } catch (e) {
        toast(`Lỗi mở thư mục: ${e.message}`, "error");
        return;
    }

    $("btn-batch-cut").disabled = true;
    $("batch-progress").classList.remove("hidden");
    $("batch-results").classList.add("hidden");
    $("batch-fill").style.width = "0%";
    $("batch-pct").textContent = "0%";
    $("batch-status-text").textContent = "Đang chuẩn bị cắt video…";
    $("batch-segment-label").textContent = "Đang chuẩn bị…";
    if ($("batch-speed")) $("batch-speed").textContent = "";
    if ($("batch-eta")) $("batch-eta").textContent = "";
    if ($("batch-seg-pct")) $("batch-seg-pct").textContent = "";

    try {
        const res = await fetch("/api/cut-multi", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ segments: batchSegments, output_folder: outputFolder }),
        });
        const data = await res.json();

        if (data.error) {
            toast(data.error, "error");
            $("btn-batch-cut").disabled = false;
            $("batch-progress").classList.add("hidden");
            return;
        }

        if (batchPollId) {
            clearInterval(batchPollId);
            batchPollId = null;
        }
        batchPollId = setInterval(pollBatchCutStatus, 500);

    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
        $("btn-batch-cut").disabled = false;
        $("batch-progress").classList.add("hidden");
    }
}

async function pollBatchCutStatus() {
    try {
        const res = await fetch("/api/cut-multi/status");
        const data = await res.json();

        $("batch-fill").style.width = data.progress + "%";
        $("batch-pct").textContent = data.progress + "%";

        const segLabel = $("batch-segment-label");
        if (segLabel && data.current_segment) {
            const title = data.segment_title || `Đoạn ${data.current_segment}`;
            segLabel.textContent = `Đoạn ${data.current_segment}/${data.total_segments}: ${title}`;
        }

        const doneCount = data.results?.length || 0;
        if (data.current_segment > 0) {
            $("batch-status-text").textContent =
                `Đang encode đoạn ${data.current_segment}/${data.total_segments}` +
                (doneCount > 0 ? ` (${doneCount} xong)` : ``);
        }

        if ($("batch-speed")) $("batch-speed").textContent = data.speed ? `⚡ ${data.speed}` : "";
        if ($("batch-eta")) $("batch-eta").textContent = data.eta ? `⏱ Còn ${data.eta}` : "";
        if ($("batch-seg-pct")) {
            $("batch-seg-pct").textContent = data.segment_progress > 0 ? `📊 Đoạn: ${data.segment_progress}%` : "";
        }

        if (data.status === "done") {
            clearInterval(batchPollId);
            batchPollId = null;

            $("batch-progress").classList.add("hidden");
            $("batch-results").classList.remove("hidden");

            let html = "";
            for (const r of data.results) {
                if (r.status === "done") {
                    const fname = r.file.split(/[/\\]/).pop();
                    const warning = r.warning ? ` <span style="color:var(--warning)">(${escapeHtml(r.warning)})</span>` : "";
                    html += `<div class="result-item done">
                        <span class="material-icons-round">check_circle</span>
                        <span>[${escapeHtml(r.episode_id || "")}] ${escapeHtml(r.title)} — ${fname}${warning}</span>
                    </div>`;
                } else {
                    html += `<div class="result-item error">
                        <span class="material-icons-round">error</span>
                        [${escapeHtml(r.episode_id || "")}] ${escapeHtml(r.title)} — Lỗi: ${escapeHtml(r.error || "?")}
                    </div>`;
                }
            }
            $("batch-results-list").innerHTML = html;

            const finalDoneCount = data.results.filter(r => r.status === "done").length;
            toast(`Cắt xong! ${finalDoneCount}/${data.results.length} đoạn thành công`, "success");
            $("btn-batch-cut").disabled = false;

        } else if (data.status === "error") {
            clearInterval(batchPollId);
            batchPollId = null;

            $("batch-progress").classList.add("hidden");
            $("batch-results").classList.remove("hidden");
            $("batch-results-list").innerHTML = `<div class="result-item error">
                <span class="material-icons-round">error</span>
                Lỗi: ${escapeHtml(data.error || "Lỗi không xác định")}
            </div>`;
            toast(`Lỗi cắt video: ${data.error || "Lỗi không xác định"}`, "error");
            $("btn-batch-cut").disabled = false;
        }
    } catch (e) {
        console.error("Batch poll error:", e);
    }
}

async function openOutputMulti() {
    try {
        await fetch("/api/open-folder-multi", { method: "POST" });
    } catch (e) {
        toast("Không mở được thư mục", "error");
    }
}

// ---------------------------------------------------------------------------
// Whisper Transcription
// ---------------------------------------------------------------------------
let whisperPollId = null;
let whisperInstalled = false;

async function checkWhisper() {
    try {
        const res = await fetch("/api/whisper/check");
        const data = await res.json();
        whisperInstalled = data.installed;

        if (!data.installed) {
            $("whisper-not-installed").classList.remove("hidden");
            $("whisper-controls").classList.add("hidden");
        } else {
            $("whisper-not-installed").classList.add("hidden");
            $("whisper-controls").classList.remove("hidden");

            // Show device info
            let deviceText = `CPU`;
            if (data.gpu) {
                deviceText = `🚀 GPU: ${data.device}`;
            }
            $("whisper-device-text").textContent = deviceText;
        }
    } catch (e) {
        console.error("Whisper check failed:", e);
    }
}

function showWhisperPanel() {
    $("card-whisper").classList.remove("hidden");
    checkWhisper();
}

async function startWhisper() {
    if (!whisperInstalled) {
        toast("Chưa cài faster-whisper!", "error");
        return;
    }

    const model = $("whisper-model").value;
    const language = $("whisper-language").value;

    $("btn-whisper").disabled = true;
    $("whisper-progress").classList.remove("hidden");
    $("whisper-result").classList.add("hidden");
    $("whisper-fill").style.width = "0%";
    $("whisper-pct").textContent = "0%";
    $("whisper-status-text").textContent = "Đang khởi tạo Whisper...";

    try {
        const res = await fetch("/api/transcribe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model, language }),
        });
        const data = await res.json();

        if (data.error) {
            toast(data.error, "error");
            $("btn-whisper").disabled = false;
            $("whisper-progress").classList.add("hidden");
            return;
        }

        toast(`Bắt đầu Whisper (model: ${model})`, "info");
        whisperPollId = setInterval(pollWhisperStatus, 1500);
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
        $("btn-whisper").disabled = false;
        $("whisper-progress").classList.add("hidden");
    }
}

async function pollWhisperStatus() {
    try {
        const res = await fetch("/api/transcribe/status");
        const data = await res.json();

        $("whisper-fill").style.width = data.progress + "%";
        $("whisper-pct").textContent = data.progress + "%";
        $("whisper-status-text").textContent = data.message || "Đang xử lý...";

        if (data.status === "done") {
            clearInterval(whisperPollId);
            whisperPollId = null;

            $("whisper-progress").classList.add("hidden");
            $("whisper-result").classList.remove("hidden");

            // Reset to success style
            $("whisper-result-alert").className = "alert alert-success";
            $("whisper-result-icon").textContent = "check_circle";
            $("whisper-result-text").textContent = data.message;

            // Show save buttons
            $("save-transcript-row").classList.remove("hidden");
            $("save-status").textContent = "";

            $("btn-whisper").disabled = false;

            // Reload transcript data
            await loadTranscriptData();

            // Update transcript status
            $("transcript-status").innerHTML =
                `<span class="material-icons-round" style="color:var(--success);font-size:18px;vertical-align:middle">check_circle</span> ` +
                `Transcript Whisper: <strong>${data.segments_count} đoạn</strong>`;
            $("btn-load-transcript").style.display = "inline-flex";
            $("transcript-row").style.display = "flex";

            toast(`Whisper hoàn tất! ${data.segments_count} đoạn`, "success");
        } else if (data.status === "error") {
            clearInterval(whisperPollId);
            whisperPollId = null;

            $("whisper-progress").classList.add("hidden");
            $("whisper-result").classList.remove("hidden");

            // Set error style
            $("whisper-result-alert").className = "alert alert-error";
            $("whisper-result-icon").textContent = "error";
            $("whisper-result-text").textContent = data.error;

            // Hide save buttons on error
            $("save-transcript-row").classList.add("hidden");

            $("btn-whisper").disabled = false;
            toast(`Whisper lỗi: ${data.error}`, "error");
        }
    } catch (e) {
        console.error("Whisper poll error:", e);
    }
}

async function stopWhisper() {
    try {
        $("btn-whisper-stop").disabled = true;
        $("btn-whisper-stop").textContent = "Đang dừng...";

        const res = await fetch("/api/transcribe/stop", { method: "POST" });
        const data = await res.json();

        // Stop polling
        if (whisperPollId) {
            clearInterval(whisperPollId);
            whisperPollId = null;
        }

        // Reset UI
        $("whisper-progress").classList.add("hidden");
        $("whisper-result").classList.remove("hidden");
        $("whisper-result-alert").className = "alert alert-warning";
        $("whisper-result-icon").textContent = "cancel";
        $("whisper-result-text").textContent = "Đã dừng Whisper theo yêu cầu.";
        $("save-transcript-row").classList.add("hidden");

        $("btn-whisper").disabled = false;
        toast("Đã dừng Whisper", "info");
    } catch (e) {
        toast(`Lỗi khi dừng: ${e.message}`, "error");
    } finally {
        $("btn-whisper-stop").disabled = false;
        $("btn-whisper-stop").innerHTML =
            '<span class="material-icons-round">stop_circle</span> Dừng Whisper';
    }
}

// ---------------------------------------------------------------------------
// Save Transcript
// ---------------------------------------------------------------------------
async function saveTranscript(format) {
    $("save-status").textContent = "Đang mở thư mục...";
    $("save-status").style.color = "var(--text-muted)";

    try {
        // Step 1: Pick folder
        const folderRes = await fetch("/api/pick-folder", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "Chọn thư mục lưu transcript" }),
        });
        const folderData = await folderRes.json();

        if (folderData.error) {
            $("save-status").textContent = "";
            return; // User cancelled
        }

        $("save-status").textContent = "Đang lưu...";

        // Step 2: Save transcript to chosen folder
        const res = await fetch("/api/save-transcript", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ format, folder: folderData.folder }),
        });
        const data = await res.json();

        if (data.error) {
            $("save-status").textContent = `❌ ${data.error}`;
            $("save-status").style.color = "var(--error)";
            toast(data.error, "error");
            return;
        }

        $("save-status").textContent = `✅ ${data.filename}`;
        $("save-status").style.color = "var(--success)";
        toast(`Đã lưu: ${data.path}`, "success");
    } catch (e) {
        $("save-status").textContent = `❌ Lỗi: ${e.message}`;
        $("save-status").style.color = "var(--error)";
        toast(`Lỗi lưu file: ${e.message}`, "error");
    }
}

// ---------------------------------------------------------------------------
// Resizable Panels
// ---------------------------------------------------------------------------
function initResizer() {
    const handle = $("resize-handle");
    const panelLeft = document.querySelector(".panel-left");
    if (!handle || !panelLeft) return;

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    // Restore saved width
    const savedWidth = localStorage.getItem("vc_panel_width");
    if (savedWidth) {
        const w = parseInt(savedWidth, 10);
        if (w >= 280 && w <= window.innerWidth * 0.7) {
            panelLeft.style.width = w + "px";
        }
    }

    handle.addEventListener("mousedown", (e) => {
        e.preventDefault();
        isResizing = true;
        startX = e.clientX;
        startWidth = panelLeft.getBoundingClientRect().width;

        handle.classList.add("active");
        document.body.classList.add("resizing");
    });

    document.addEventListener("mousemove", (e) => {
        if (!isResizing) return;

        const dx = e.clientX - startX;
        let newWidth = startWidth + dx;

        // Clamp within min/max
        const minW = 280;
        const maxW = window.innerWidth * 0.7;
        newWidth = Math.max(minW, Math.min(maxW, newWidth));

        panelLeft.style.width = newWidth + "px";
    });

    document.addEventListener("mouseup", () => {
        if (!isResizing) return;
        isResizing = false;

        handle.classList.remove("active");
        document.body.classList.remove("resizing");

        // Persist
        const finalWidth = panelLeft.getBoundingClientRect().width;
        localStorage.setItem("vc_panel_width", Math.round(finalWidth));
    });
}

// ---------------------------------------------------------------------------
// Timeline Markers System
// ---------------------------------------------------------------------------
const MARKER_COLORS = ["#a78bfa", "#f472b6", "#34d399", "#fbbf24", "#60a5fa", "#f87171"];

function getVideoDuration() {
    const player = $("video-player");
    return (player && player.duration && isFinite(player.duration)) ? player.duration : 0;
}

function renderTimelineMarkers() {
    const bar = $("timeline-bar");
    if (!bar) return;

    const duration = getVideoDuration();
    if (duration <= 0) return;

    // Remove old markers and regions (keep playhead)
    bar.querySelectorAll(".tl-region, .tl-marker").forEach(el => el.remove());

    segments.forEach((seg, i) => {
        const color = MARKER_COLORS[i % MARKER_COLORS.length];
        const startSec = parseTime(seg.start);
        const endSec = parseTime(seg.end);

        const startPct = Math.max(0, Math.min(100, (startSec / duration) * 100));
        const endPct = Math.max(0, Math.min(100, (endSec / duration) * 100));

        // Highlight region between start and end
        if (endPct > startPct) {
            const region = document.createElement("div");
            region.className = "tl-region";
            region.style.left = startPct + "%";
            region.style.width = (endPct - startPct) + "%";
            region.style.background = color;
            region.title = `Đoạn ${i + 1}: ${seg.start} → ${seg.end}`;
            bar.appendChild(region);
        }

        // Start marker
        const startMarker = createMarker(i, "start", startPct, color, seg.start);
        bar.appendChild(startMarker);

        // End marker
        const endMarker = createMarker(i, "end", endPct, color, seg.end);
        bar.appendChild(endMarker);
    });
}

function createMarker(segIdx, field, pct, color, timeLabel) {
    const marker = document.createElement("div");
    marker.className = "tl-marker";
    marker.dataset.segIdx = segIdx;
    marker.dataset.field = field;
    marker.style.left = pct + "%";
    marker.style.setProperty("--marker-color", color);
    marker.title = `Đoạn ${segIdx + 1} ${field === "start" ? "Bắt đầu" : "Kết thúc"}: ${timeLabel}`;

    // Label
    const label = document.createElement("span");
    label.className = "tl-marker-label";
    label.textContent = (segIdx + 1) + (field === "start" ? "S" : "E");
    marker.appendChild(label);

    // Make draggable
    initMarkerDrag(marker, segIdx, field);

    return marker;
}

function initMarkerDrag(marker, segIdx, field) {
    let dragging = false;

    marker.addEventListener("mousedown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragging = true;
        document.body.classList.add("marker-dragging");

        const bar = $("timeline-bar");
        const duration = getVideoDuration();
        if (!bar || duration <= 0) return;

        const onMove = (ev) => {
            if (!dragging) return;
            const rect = bar.getBoundingClientRect();
            let pct = ((ev.clientX - rect.left) / rect.width) * 100;
            pct = Math.max(0, Math.min(100, pct));
            marker.style.left = pct + "%";

            // Update time
            const newTime = (pct / 100) * duration;
            const formatted = fmtTime(newTime);

            // Update segment data
            if (segIdx < segments.length) {
                segments[segIdx][field] = formatted;
                // Update input without re-rendering
                const input = $(`seg-${field}-${segIdx}`);
                if (input) input.value = formatted;
            }

            // Update marker tooltip
            marker.title = `Đoạn ${segIdx + 1} ${field === "start" ? "Bắt đầu" : "Kết thúc"}: ${formatted}`;
        };

        const onUp = () => {
            dragging = false;
            document.body.classList.remove("marker-dragging");
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);

            // Save and re-render regions
            saveSegments();
            renderTimelineMarkers();

            // Seek video to marker position
            const player = $("video-player");
            if (player && segIdx < segments.length) {
                player.currentTime = parseTime(segments[segIdx][field]);
            }
        };

        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    });
}

function pinMarker(segIdx, field) {
    const player = $("video-player");
    if (!player || !player.duration || !isFinite(player.duration)) {
        toast("Chưa load video", "error");
        return;
    }

    // Read time from the input field (what user typed)
    const input = $(`seg-${field}-${segIdx}`);
    if (!input) return;

    const typedValue = input.value.trim();
    if (!typedValue || typedValue === "00:00:00") {
        toast("Nhập thời gian trước khi ghim", "error");
        return;
    }

    const timeSec = parseTime(typedValue);
    if (timeSec > player.duration) {
        toast(`Thời gian vượt quá video (${fmtTime(player.duration)})`, "error");
        return;
    }

    // Save to segment data
    segments[segIdx][field] = typedValue;
    saveSegments();

    // Seek video to this position
    player.currentTime = timeSec;

    // Re-render markers
    renderTimelineMarkers();

    // Auto-scroll timeline to pinned position if zoomed
    if (tlZoom > 1) {
        timelineScrollToTime(timeSec);
    }

    toast(`📌 Đã ghim ${field === "start" ? "Bắt đầu" : "Kết thúc"} Đoạn ${segIdx + 1} tại ${typedValue}`, "success");
}

// ---------------------------------------------------------------------------
// Timeline Zoom
// ---------------------------------------------------------------------------
let tlZoom = 1;

function timelineSetZoom(level) {
    const viewport = $("timeline-viewport");
    const bar = $("timeline-bar");
    if (!viewport || !bar) return;

    // Clamp
    level = Math.max(1, Math.min(20, level));

    // Save scroll center position (as fraction of total width)
    const oldWidth = bar.offsetWidth;
    const scrollCenter = (viewport.scrollLeft + viewport.offsetWidth / 2) / oldWidth;

    tlZoom = level;
    bar.style.width = (level * 100) + "%";

    // Update slider + label
    const slider = $("timeline-zoom-slider");
    if (slider) slider.value = level;
    const label = $("zoom-label");
    if (label) label.textContent = level.toFixed(level % 1 === 0 ? 0 : 1) + "x";

    // Restore scroll to keep same center
    const newWidth = bar.offsetWidth;
    viewport.scrollLeft = scrollCenter * newWidth - viewport.offsetWidth / 2;
}

function timelineZoom(delta) {
    let step = tlZoom < 5 ? 1 : 2;
    timelineSetZoom(tlZoom + delta * step);
}

function timelineScrollToTime(timeSec) {
    const viewport = $("timeline-viewport");
    const bar = $("timeline-bar");
    if (!viewport || !bar) return;

    const duration = getVideoDuration();
    if (duration <= 0) return;

    const pct = timeSec / duration;
    const targetX = pct * bar.offsetWidth;
    const viewCenter = viewport.offsetWidth / 2;

    viewport.scrollLeft = targetX - viewCenter;
}

function initTimeline() {
    const bar = $("timeline-bar");
    const player = $("video-player");
    const viewport = $("timeline-viewport");
    if (!bar || !player) return;

    // Click on timeline bar to seek
    bar.addEventListener("click", (e) => {
        if (e.target.classList.contains("tl-marker") || e.target.closest(".tl-marker")) return;
        const duration = getVideoDuration();
        if (duration <= 0) return;

        const rect = bar.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        player.currentTime = pct * duration;
    });

    // Mouse wheel zoom on timeline
    if (viewport) {
        viewport.addEventListener("wheel", (e) => {
            e.preventDefault();
            const delta = e.deltaY < 0 ? 1 : -1;
            const step = tlZoom < 5 ? 0.5 : 1;

            // Zoom centered on cursor
            const rect = bar.getBoundingClientRect();
            const cursorFrac = (e.clientX - rect.left) / rect.width;

            const oldZoom = tlZoom;
            const newZoom = Math.max(1, Math.min(20, tlZoom + delta * step));
            if (newZoom === oldZoom) return;

            tlZoom = newZoom;
            bar.style.width = (newZoom * 100) + "%";

            const slider = $("timeline-zoom-slider");
            if (slider) slider.value = newZoom;
            const label = $("zoom-label");
            if (label) label.textContent = newZoom.toFixed(newZoom % 1 === 0 ? 0 : 1) + "x";

            // Keep cursor position stable
            const newBarWidth = bar.offsetWidth;
            viewport.scrollLeft = cursorFrac * newBarWidth - (e.clientX - viewport.getBoundingClientRect().left);
        }, { passive: false });
    }

    // Update playhead and time display on timeupdate
    player.addEventListener("timeupdate", () => {
        const duration = getVideoDuration();
        if (duration <= 0) return;

        const pct = (player.currentTime / duration) * 100;
        const playhead = $("timeline-playhead");
        if (playhead) playhead.style.left = pct + "%";

        $("current-time").textContent = fmtTime(player.currentTime);

        // Auto-scroll viewport to keep playhead visible when zoomed
        if (tlZoom > 1 && viewport && !document.body.classList.contains("marker-dragging")) {
            const barWidth = bar.offsetWidth;
            const playheadX = (player.currentTime / duration) * barWidth;
            const viewLeft = viewport.scrollLeft;
            const viewRight = viewLeft + viewport.offsetWidth;
            const margin = viewport.offsetWidth * 0.15;

            if (playheadX < viewLeft + margin || playheadX > viewRight - margin) {
                viewport.scrollLeft = playheadX - viewport.offsetWidth / 2;
            }
        }
    });

    // Update timeline end time when metadata loads
    player.addEventListener("loadedmetadata", () => {
        const el = $("timeline-time-end");
        if (el) el.textContent = fmtTime(player.duration);
        renderTimelineMarkers();
    });
}

// ---------------------------------------------------------------------------
// Transcript Text Search
// ---------------------------------------------------------------------------
let searchDebounceTimer = null;
let lastSearchQuery = "";
let searchResults = [];

function onTranscriptSearch(query) {
    // Debounce: wait 250ms after user stops typing
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        performTranscriptSearch(query);
    }, 250);
}

function performTranscriptSearch(query) {
    query = query.trim();
    lastSearchQuery = query;

    const clearBtn = $("btn-search-clear");
    const resultsInfo = $("search-results-info");
    const resultsList = $("search-results-list");
    const resultsCount = $("search-results-count");

    // Show/hide clear button
    if (clearBtn) {
        clearBtn.classList.toggle("hidden", !query);
    }

    if (!query || query.length < 2) {
        // Clear results
        searchResults = [];
        if (resultsInfo) resultsInfo.classList.add("hidden");
        if (resultsList) {
            resultsList.classList.add("hidden");
            resultsList.innerHTML = "";
        }
        // Show full transcript list again
        highlightTranscriptMatches("");
        return;
    }

    if (!transcript.length) {
        if (resultsList) {
            resultsList.classList.remove("hidden");
            resultsList.innerHTML = `<div class="search-no-results">
                <span class="material-icons-round">subtitles_off</span>
                Chưa có transcript để tìm kiếm
            </div>`;
        }
        if (resultsInfo) resultsInfo.classList.add("hidden");
        return;
    }

    // Search: case-insensitive substring match
    const queryLower = query.toLowerCase();
    searchResults = [];

    for (let i = 0; i < transcript.length; i++) {
        const seg = transcript[i];
        const text = (seg.text || "").toLowerCase();
        if (text.includes(queryLower)) {
            searchResults.push({ index: i, segment: seg });
        }
    }

    // Update info
    if (resultsInfo) {
        resultsInfo.classList.remove("hidden");
        resultsCount.textContent = `${searchResults.length} kết quả`;
    }

    // Render search results
    if (resultsList) {
        resultsList.classList.remove("hidden");

        if (searchResults.length === 0) {
            resultsList.innerHTML = `<div class="search-no-results">
                <span class="material-icons-round">search_off</span>
                Không tìm thấy "${escapeHtml(query)}"
            </div>`;
        } else {
            let html = "";
            searchResults.forEach((r, ri) => {
                const seg = r.segment;
                const highlighted = highlightText(seg.text, query);
                html += `<div class="search-result-item" data-search-idx="${ri}"
                              onclick="searchResultClick(${r.index})">
                    <span class="search-result-ts">${fmtTime(seg.start)}</span>
                    <span class="search-result-text">${highlighted}</span>
                    <div class="search-result-actions" onclick="event.stopPropagation()">
                        <button class="btn-search-pin btn-search-pin-start"
                                onclick="pinSearchResult(${r.index}, 'start')"
                                title="Ghim làm thời gian BẮT ĐẦU">▶ Bắt đầu</button>
                        <button class="btn-search-pin btn-search-pin-end"
                                onclick="pinSearchResult(${r.index}, 'end')"
                                title="Ghim làm thời gian KẾT THÚC">⏹ Kết thúc</button>
                    </div>
                </div>`;
            });
            resultsList.innerHTML = html;
        }
    }

    // Highlight matches in the full transcript list too
    highlightTranscriptMatches(query);

    // Auto-seek to first match
    if (searchResults.length > 0) {
        const firstSeg = searchResults[0].segment;
        seekTo(firstSeg.start);
    }
}

function highlightText(text, query) {
    if (!query) return escapeHtml(text);

    // Escape regex special chars in query
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escapedQuery})`, "gi");
    // Split on matches, escape non-match parts, wrap matches in <mark>
    const parts = text.split(regex);
    return parts.map(part => {
        if (part.toLowerCase() === query.toLowerCase()) {
            return `<mark>${escapeHtml(part)}</mark>`;
        }
        return escapeHtml(part);
    }).join("");
}

function highlightTranscriptMatches(query) {
    const segs = document.querySelectorAll(".transcript-seg");
    if (!query) {
        // Reset all to normal — rebuild word spans if available
        segs.forEach((el, i) => {
            if (transcript[i]) {
                const txtEl = el.querySelector(".txt");
                if (txtEl) {
                    const seg = transcript[i];
                    if (seg.words && seg.words.length > 0) {
                        txtEl.innerHTML = seg.words.map((w, wi) =>
                            `<span class="tword" data-seg="${i}" data-wi="${wi}" data-start="${w.start}" data-end="${w.end}"` +
                            ` onclick="event.stopPropagation(); onWordClick(${i}, ${wi})"` +
                            ` title="${fmtTime(w.start)} → ${fmtTime(w.end)}"` +
                            `>${escapeHtml(w.word)}</span>`
                        ).join(" ");
                    } else {
                        txtEl.innerHTML = escapeHtml(seg.text);
                    }
                }
            }
            el.classList.remove("search-match");
        });
        return;
    }

    const queryLower = query.toLowerCase();
    segs.forEach((el, i) => {
        if (transcript[i]) {
            const text = transcript[i].text || "";
            const txtEl = el.querySelector(".txt");
            if (text.toLowerCase().includes(queryLower)) {
                if (txtEl) txtEl.innerHTML = highlightText(text, query);
                el.classList.add("search-match");
            } else {
                // Reset to word-level spans
                const seg = transcript[i];
                if (txtEl) {
                    if (seg.words && seg.words.length > 0) {
                        txtEl.innerHTML = seg.words.map((w, wi) =>
                            `<span class="tword" data-seg="${i}" data-wi="${wi}" data-start="${w.start}" data-end="${w.end}"` +
                            ` onclick="event.stopPropagation(); onWordClick(${i}, ${wi})"` +
                            ` title="${fmtTime(w.start)} → ${fmtTime(w.end)}"` +
                            `>${escapeHtml(w.word)}</span>`
                        ).join(" ");
                    } else {
                        txtEl.innerHTML = escapeHtml(text);
                    }
                }
                el.classList.remove("search-match");
            }
        }
    });
}

function searchResultClick(transcriptIdx) {
    if (transcriptIdx < 0 || transcriptIdx >= transcript.length) return;

    const seg = transcript[transcriptIdx];
    seekTo(seg.start);

    // Highlight active result
    document.querySelectorAll(".search-result-item").forEach(el => {
        el.classList.remove("active");
    });
    const items = document.querySelectorAll(".search-result-item");
    items.forEach(el => {
        if (parseInt(el.dataset.searchIdx) === searchResults.findIndex(r => r.index === transcriptIdx)) {
            el.classList.add("active");
        }
    });

    // Scroll transcript to this segment
    const transcriptSeg = document.querySelector(`.transcript-seg[data-idx="${transcriptIdx}"]`);
    if (transcriptSeg) {
        // Expand transcript if collapsed
        if (transcriptCollapsed) {
            toggleTranscript();
        }
        transcriptSeg.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    toast(`⏩ Nhảy tới ${fmtTime(seg.start)} — "${seg.text.substring(0, 40)}..."`, "info");
}

function pinSearchResult(transcriptIdx, field) {
    if (transcriptIdx < 0 || transcriptIdx >= transcript.length) return;

    const seg = transcript[transcriptIdx];
    const timeValue = fmtTime(field === "start" ? seg.start : (seg.end || seg.start + 10));

    // If no segments exist, create one
    if (segments.length === 0) {
        segments.push({ start: "00:00:00", end: "00:00:00", title: "" });
    }

    // Find the last segment (or currently active one) to pin to
    const targetIdx = segments.length - 1;
    segments[targetIdx][field] = timeValue;

    // Auto-generate title from transcript text if empty
    if (!segments[targetIdx].title && seg.text) {
        segments[targetIdx].title = seg.text.substring(0, 50).trim();
    }

    saveSegments();
    renderSegments();

    // Seek video to the pinned time
    const player = $("video-player");
    if (player) {
        player.currentTime = field === "start" ? seg.start : (seg.end || seg.start + 10);
    }

    const label = field === "start" ? "Bắt đầu" : "Kết thúc";
    toast(`📌 Ghim ${label} Đoạn ${targetIdx + 1}: ${timeValue}`, "success");
}

function clearTranscriptSearch() {
    const input = $("transcript-search-input");
    if (input) {
        input.value = "";
        input.focus();
    }
    performTranscriptSearch("");
}

// ---------------------------------------------------------------------------
// Pin Transcript Segment to Cut (direct from transcript list)
// ---------------------------------------------------------------------------
function pinTranscriptSeg(transcriptIdx, field) {
    if (transcriptIdx < 0 || transcriptIdx >= transcript.length) return;

    const seg = transcript[transcriptIdx];
    const timeValue = fmtTime(field === "start" ? seg.start : (seg.end || seg.start + 10));

    // If no segments exist, create one
    if (segments.length === 0) {
        segments.push({ start: "00:00:00", end: "00:00:00", title: "" });
    }

    // Find the last segment to pin to
    const targetIdx = segments.length - 1;
    segments[targetIdx][field] = timeValue;

    // Auto-generate title from transcript text if title is empty
    if (!segments[targetIdx].title && seg.text) {
        segments[targetIdx].title = seg.text.substring(0, 50).trim();
    }

    saveSegments();
    renderSegments();

    // Seek video to the pinned time
    const player = $("video-player");
    if (player) {
        player.currentTime = field === "start" ? seg.start : (seg.end || seg.start + 10);
    }

    const label = field === "start" ? "Bắt đầu" : "Kết thúc";
    toast(`📌 Ghim ${label} Đoạn ${targetIdx + 1}: ${timeValue}`, "success");

    // Visual feedback on the transcript segment
    const segEl = document.querySelector(`.transcript-seg[data-idx="${transcriptIdx}"]`);
    if (segEl) {
        segEl.classList.add("seg-pinned");
        setTimeout(() => segEl.classList.remove("seg-pinned"), 1200);
    }
}

// ---------------------------------------------------------------------------
// Word-level Click & Pin (popup on word click)
// ---------------------------------------------------------------------------
let activeWordPopup = null;

function onWordClick(segIdx, wordIdx) {
    const seg = transcript[segIdx];
    if (!seg || !seg.words || !seg.words[wordIdx]) return;

    const word = seg.words[wordIdx];

    // Seek video to this word's start
    seekTo(word.start);

    // Remove previous popup
    closeWordPopup();

    // Find the clicked word element
    const wordEl = document.querySelector(`.tword[data-seg="${segIdx}"][data-wi="${wordIdx}"]`);
    if (!wordEl) return;

    // Highlight active word
    document.querySelectorAll(".tword.active").forEach(el => el.classList.remove("active"));
    wordEl.classList.add("active");

    // Create popup
    const popup = document.createElement("div");
    popup.className = "word-popup";
    popup.id = "word-popup";
    popup.innerHTML = `
        <div class="word-popup-header">
            <span class="word-popup-word">"${escapeHtml(word.word)}"</span>
            <span class="word-popup-time">${fmtTime(word.start)} → ${fmtTime(word.end)}</span>
        </div>
        <div class="word-popup-actions">
            <button class="wp-btn wp-btn-start" onclick="pinWord(${segIdx}, ${wordIdx}, 'start')">
                ▶ Ghim Bắt đầu
            </button>
            <button class="wp-btn wp-btn-end" onclick="pinWord(${segIdx}, ${wordIdx}, 'end')">
                ⏹ Ghim Kết thúc
            </button>
        </div>
    `;

    // Position popup near the word
    document.body.appendChild(popup);
    const wordRect = wordEl.getBoundingClientRect();
    let top = wordRect.bottom + 6;
    let left = wordRect.left;

    // Keep popup within viewport
    const popupRect = popup.getBoundingClientRect();
    if (top + popupRect.height > window.innerHeight) {
        top = wordRect.top - popupRect.height - 6;
    }
    if (left + popupRect.width > window.innerWidth) {
        left = window.innerWidth - popupRect.width - 10;
    }

    popup.style.top = top + "px";
    popup.style.left = Math.max(8, left) + "px";
    activeWordPopup = popup;

    // Close on click outside (delayed to avoid immediate close)
    setTimeout(() => {
        document.addEventListener("click", closeWordPopupOnOutside);
    }, 50);
}

function closeWordPopup() {
    if (activeWordPopup) {
        activeWordPopup.remove();
        activeWordPopup = null;
    }
    document.removeEventListener("click", closeWordPopupOnOutside);
    document.querySelectorAll(".tword.active").forEach(el => el.classList.remove("active"));
}

function closeWordPopupOnOutside(e) {
    if (activeWordPopup && !activeWordPopup.contains(e.target) && !e.target.classList.contains("tword")) {
        closeWordPopup();
    }
}

function pinWord(segIdx, wordIdx, field) {
    const seg = transcript[segIdx];
    if (!seg || !seg.words || !seg.words[wordIdx]) return;

    const word = seg.words[wordIdx];
    const timeValue = fmtTime(field === "start" ? word.start : word.end);

    // Create segment if none exists
    if (segments.length === 0) {
        segments.push({ start: "00:00:00", end: "00:00:00", title: "" });
    }

    const targetIdx = segments.length - 1;
    segments[targetIdx][field] = timeValue;

    // Auto-generate title from word context (nearby words)
    if (!segments[targetIdx].title && seg.text) {
        segments[targetIdx].title = seg.text.substring(0, 50).trim();
    }

    saveSegments();
    renderSegments();

    // Seek video
    const player = $("video-player");
    if (player) {
        player.currentTime = field === "start" ? word.start : word.end;
    }

    const label = field === "start" ? "Bắt đầu" : "Kết thúc";
    toast(`📌 Ghim ${label} Đoạn ${targetIdx + 1}: ${timeValue} ("${word.word}")`, "success");

    // Close popup
    closeWordPopup();

    // Flash the word
    const wordEl = document.querySelector(`.tword[data-seg="${segIdx}"][data-wi="${wordIdx}"]`);
    if (wordEl) {
        wordEl.classList.add("pinned");
        setTimeout(() => wordEl.classList.remove("pinned"), 1500);
    }
}


// ---------------------------------------------------------------------------
// Whisper Queue
// ---------------------------------------------------------------------------
let queuePollId = null;

async function queueAddVideo() {
    const model = $("queue-model").value;
    const language = $("queue-language").value;

    $("btn-queue-add").disabled = true;
    try {
        const res = await fetch("/api/whisper/queue/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model, language }),
        });
        const data = await res.json();
        if (data.error) { toast(data.error, "error"); return; }
        toast(`Đã thêm ${data.added} video (tổng: ${data.queue_length})`, "success");
        await refreshQueueStatus();
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    } finally {
        $("btn-queue-add").disabled = false;
    }
}

async function queueStart() {
    const model = $("queue-model").value;
    const language = $("queue-language").value;

    try {
        const res = await fetch("/api/whisper/queue/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model, language }),
        });
        const data = await res.json();
        if (data.error) { toast(data.error, "error"); return; }
        toast(`Bắt đầu xử lý ${data.count} video...`, "info");

        // Start polling
        if (queuePollId) clearInterval(queuePollId);
        queuePollId = setInterval(refreshQueueStatus, 1500);
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    }
}

async function queueClear() {
    try {
        await fetch("/api/whisper/queue/clear", { method: "POST" });
        await refreshQueueStatus();
        toast("Đã xóa hàng đợi", "info");
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    }
}

async function queueRemoveItem(id) {
    try {
        await fetch("/api/whisper/queue/remove", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id }),
        });
        await refreshQueueStatus();
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    }
}

async function refreshQueueStatus() {
    try {
        const res = await fetch("/api/whisper/queue/status");
        const data = await res.json();
        renderQueue(data.queue, data.running);

        // Stop polling when done
        if (!data.running && queuePollId) {
            const stillRunning = data.queue.some(x => x.status === "running" || x.status === "pending");
            if (!stillRunning) {
                clearInterval(queuePollId);
                queuePollId = null;
                const doneCount = data.queue.filter(x => x.status === "done").length;
                const errCount = data.queue.filter(x => x.status === "error").length;
                if (doneCount > 0 || errCount > 0) {
                    toast(`Hàng đợi hoàn tất: ${doneCount} xong, ${errCount} lỗi`, doneCount > 0 ? "success" : "error");
                }
            }
        }
    } catch (e) {
        console.error("Queue poll error:", e);
    }
}

function renderQueue(queue, running) {
    const list = $("queue-list");
    const count = $("queue-count");
    const btnStart = $("btn-queue-start");
    const btnClear = $("btn-queue-clear");

    count.textContent = queue.length;
    const hasPending = queue.some(x => x.status === "pending");
    btnStart.disabled = running || !hasPending;
    btnClear.disabled = running;

    if (!queue.length) {
        list.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:8px">Chưa có video nào trong hàng</p>`;
        return;
    }

    const statusIcon = { pending: "⏳", running: "⚙️", done: "✅", error: "❌" };
    const statusColor = { pending: "var(--text-muted)", running: "var(--accent)", done: "var(--success)", error: "var(--error)" };

    list.innerHTML = queue.map(item => `
        <div class="queue-item" style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:var(--bg-card-2,rgba(255,255,255,0.04));border-radius:8px;border:1px solid var(--border)">
            <span style="font-size:1rem;flex-shrink:0">${statusIcon[item.status] || "⏳"}</span>
            <div style="flex:1;min-width:0">
                <div style="font-size:0.85rem;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(item.video_path)}">${escapeHtml(item.video_name)}</div>
                <div style="font-size:0.76rem;color:${statusColor[item.status]};margin-top:2px">${escapeHtml(item.message)}</div>
                ${item.status === "running" ? `
                <div style="margin-top:4px;height:4px;background:var(--border);border-radius:2px;overflow:hidden">
                    <div style="height:100%;width:${item.progress}%;background:var(--accent);transition:width 0.5s"></div>
                </div>` : ""}
            </div>
            ${item.status !== "running" ? `
            <button onclick="queueRemoveItem('${item.id}')" title="Xóa" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:2px">
                <span class="material-icons-round" style="font-size:16px">close</span>
            </button>` : ""}
        </div>
    `).join("");
}

// ---------------------------------------------------------------------------
// Export Prompts → CSV
// ---------------------------------------------------------------------------
async function exportPrompts() {
    const btn = $("btn-export-prompts");
    const resultEl = $("export-prompts-result");

    btn.disabled = true;
    btn.innerHTML = '<span class="material-icons-round spin">sync</span> Đang xử lý...';
    resultEl.classList.add("hidden");
    resultEl.innerHTML = "";

    try {
        const res = await fetch("/api/export-prompts", { method: "POST" });
        const data = await res.json();

        if (data.error) {
            toast(data.error, "error");
            return;
        }

        const allFilled = data.empty_prompts === 0;
        const safePath = (data.txt_path || "").replace(/\\/g, "\\\\");

        resultEl.classList.remove("hidden");
        resultEl.innerHTML = `
            <div class="alert ${allFilled ? "alert-success" : "alert-warning"}" style="margin-bottom:10px">
                <span class="material-icons-round">${allFilled ? "check_circle" : "warning"}</span>
                <div>
                    <strong>${escapeHtml(data.txt_filename)}</strong>
                    <p style="margin:2px 0 0;font-size:0.82rem">
                        ${data.filled_prompts}/${data.total_segments} prompts
                        ${data.empty_prompts > 0
                            ? `<span style="color:var(--warning);margin-left:8px">${data.empty_prompts} dòng trống</span>`
                            : ""}
                    </p>
                    <p style="margin:2px 0 0;font-size:0.78rem;color:var(--text-muted)">
                        Mỗi dòng = 1 prompt · số dòng = số segment
                    </p>
                </div>
            </div>
            <button class="btn btn-ghost btn-sm" onclick="openFileLocation('${safePath}')">
                <span class="material-icons-round">folder_open</span>
                Mở thư mục
            </button>`;

        toast(
            allFilled
                ? `Xuất xong! ${data.filled_prompts} prompts → ${data.txt_filename}`
                : `TXT: ${data.filled_prompts}/${data.total_segments} prompts (${data.empty_prompts} trống)`,
            allFilled ? "success" : "info"
        );
    } catch (e) {
        toast(`Lỗi: ${e.message}`, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons-round">upload_file</span> Chọn manifest.json → Xuất CSV';
    }
}

async function openFileLocation(filePath) {
    try {
        await fetch("/api/open-file-location", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: filePath }),
        });
    } catch (e) {
        toast("Không mở được thư mục", "error");
    }
}

// ---------------------------------------------------------------------------
// Init on DOM ready
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    initResizer();
    initTimeline();
});

