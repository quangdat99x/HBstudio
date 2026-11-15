/**
 * Podcast Auto-Zoom — Frontend Application (Batch Queue)
 * Handles multi-file upload, queue management, SSE progress, and auto-save.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Webview Detection ──
    let isWebview = false;
    window.addEventListener('pywebviewready', () => {
        isWebview = true;
        console.log('pywebview API ready');
    });
    if (window.pywebview && window.pywebview.api) {
        isWebview = true;
    }

    // ── DOM Elements ──
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    const folderSection = document.getElementById('folder-section');
    const folderDisplay = document.getElementById('folder-display');
    const folderPath = document.getElementById('folder-path');
    const chooseFolderBtn = document.getElementById('choose-folder-btn');

    const uploadSection = document.getElementById('upload-section');
    const queueSection = document.getElementById('queue-section');
    const queueList = document.getElementById('queue-list');
    const queueTitle = document.getElementById('queue-title');
    const addMoreBtn = document.getElementById('add-more-btn');

    const settingsSection = document.getElementById('settings-section');
    const startBtn = document.getElementById('start-btn');
    const startBtnText = document.getElementById('start-btn-text');

    const summarySection = document.getElementById('summary-section');
    const summaryTitle = document.getElementById('summary-title');
    const summaryMessage = document.getElementById('summary-message');
    const newBatchBtn = document.getElementById('new-batch-btn');

    // Settings inputs
    const zoomFactor = document.getElementById('zoom-factor');
    const smoothingSpeed = document.getElementById('smoothing-speed');
    const switchDuration = document.getElementById('switch-duration');
    const maxFaces = document.getElementById('max-faces');

    // ── State ──
    let selectedFiles = [];          // Files waiting to be uploaded
    let uploadedJobs = [];           // Job IDs that have been uploaded
    let outputDir = null;            // Selected output directory
    let isProcessing = false;        // Whether batch is currently being processed
    let activeStreams = {};          // Active SSE streams by job_id
    let uploadsInFlight = 0;         // Files still uploading (mid-batch adds)

    // ── Folder Selection ──
    chooseFolderBtn.addEventListener('click', async () => {
        if (isWebview && window.pywebview && window.pywebview.api && window.pywebview.api.select_folder) {
            // Webview: native folder dialog
            try {
                const result = await window.pywebview.api.select_folder();
                if (result && result.success) {
                    setOutputDir(result.path);
                }
            } catch (err) {
                console.error('Folder select error:', err);
            }
        } else {
            // Browser: prompt for path
            const path = prompt('Enter the output folder path:', 'C:\\Users\\Videos');
            if (path && path.trim()) {
                setOutputDir(path.trim());
            }
        }
    });

    async function setOutputDir(path) {
        try {
            const res = await fetch('/api/set-output-dir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            const data = await res.json();
            if (data.success) {
                outputDir = data.path;
                folderPath.textContent = outputDir;
                folderDisplay.classList.add('folder-selected');
                updateStartButton();
            } else {
                alert('Invalid folder: ' + (data.error || 'Unknown error'));
            }
        } catch (err) {
            alert('Failed to set output folder: ' + err.message);
        }
    }

    // ── File Selection ──
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            addFiles(Array.from(e.dataTransfer.files));
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            addFiles(Array.from(fileInput.files));
            fileInput.value = '';
        }
    });

    addMoreBtn.addEventListener('click', () => fileInput.click());

    function addFiles(files) {
        const allowedExts = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'];

        let added = 0;
        for (const file of files) {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (!allowedExts.includes(ext)) {
                alert(`Skipped: ${file.name} (unsupported format: ${ext})`);
                continue;
            }
            if (file.size > 2 * 1024 * 1024 * 1024) {
                alert(`Skipped: ${file.name} (exceeds 2GB limit)`);
                continue;
            }
            // Avoid duplicates
            if (selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
                continue;
            }
            selectedFiles.push(file);
            added++;
        }

        renderQueue();
        updateStartButton();

        // Show queue & settings sections with stagger
        if (selectedFiles.length > 0 || uploadedJobs.length > 0) {
            queueSection.classList.remove('hidden');
            animateSectionIn(queueSection, 0);
            settingsSection.classList.remove('hidden');
            animateSectionIn(settingsSection, 80);
        }

        // If a batch is already running, newly added files go straight into the
        // live queue — they line up and wait their turn to be zoomed.
        if (added > 0 && isProcessing) {
            flushPendingToQueue();
        }
    }

    function removeFile(index) {
        selectedFiles.splice(index, 1);
        renderQueue();
        updateStartButton();
        if (selectedFiles.length === 0 && uploadedJobs.length === 0) {
            queueSection.classList.add('hidden');
            settingsSection.classList.add('hidden');
        }
    }

    // ── Queue Rendering ──
    function renderQueue() {
        queueList.innerHTML = '';

        // Pending files (not yet uploaded)
        selectedFiles.forEach((file, idx) => {
            const item = createQueueItem({
                name: file.name,
                size: formatSize(file.size),
                status: 'pending',
                message: 'Ready to process',
                progress: 0,
            });

            // Add remove button for pending files
            const removeBtn = item.querySelector('.qi-remove');
            if (removeBtn) {
                removeBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    removeFile(idx);
                });
            }

            queueList.appendChild(item);
        });

        // Uploaded/processing jobs
        uploadedJobs.forEach(jobId => {
            // These are managed by SSE updates, just create placeholder
            let existing = document.getElementById(`qi-${jobId}`);
            if (!existing) {
                existing = createQueueItem({
                    id: jobId,
                    name: 'Uploading...',
                    size: '',
                    status: 'uploading',
                    message: 'Uploading...',
                    progress: 0,
                });
                existing.id = `qi-${jobId}`;
            }
            queueList.appendChild(existing);
        });

        updateQueueTitle();
    }

    function createQueueItem({ id, name, size, status, message, progress }) {
        const item = document.createElement('div');
        item.className = `queue-item qi-${status}`;
        if (id) item.id = `qi-${id}`;

        const statusIcon = getStatusIcon(status);

        item.innerHTML = `
            <div class="qi-icon">${statusIcon}</div>
            <div class="qi-info">
                <div class="qi-name">${escapeHtml(name)}</div>
                <div class="qi-meta">
                    <span class="qi-size">${size}</span>
                    <span class="qi-status-text">${escapeHtml(message)}</span>
                </div>
                ${status === 'processing' ? `
                <div class="qi-progress-bar">
                    <div class="qi-progress-fill" style="width: ${progress}%"></div>
                </div>` : ''}
            </div>
            ${status === 'pending' ? `
            <button class="qi-remove btn-remove" title="Remove">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>` : ''}
            ${status === 'complete' ? `
            <div class="qi-saved-icon" title="Saved to output folder">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
            </div>` : ''}
        `;

        return item;
    }

    function getStatusIcon(status) {
        switch (status) {
            case 'pending':
                return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="icon-pending">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>`;
            case 'uploading':
                return `<div class="spinner"></div>`;
            case 'queued':
                return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="icon-queued">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>`;
            case 'processing':
                return `<div class="spinner"></div>`;
            case 'complete':
                return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon-complete">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>`;
            case 'error':
                return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon-error">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>`;
            default:
                return '';
        }
    }

    function updateQueueItem(jobId, data) {
        let item = document.getElementById(`qi-${jobId}`);
        if (!item) {
            item = createQueueItem({
                id: jobId,
                name: data.original_filename || jobId,
                size: '',
                status: data.status,
                message: data.message,
                progress: data.progress || 0,
            });
            item.id = `qi-${jobId}`;
            queueList.appendChild(item);
        }

        // Update class
        item.className = `queue-item qi-${data.status}`;

        // Update icon with spring animation
        const iconEl = item.querySelector('.qi-icon');
        if (iconEl) {
            iconEl.innerHTML = getStatusIcon(data.status);
            iconEl.classList.remove('icon-transition');
            void iconEl.offsetHeight; // reflow
            iconEl.classList.add('icon-transition');
        }

        // Update name
        const nameEl = item.querySelector('.qi-name');
        if (nameEl && data.original_filename) {
            nameEl.textContent = data.original_filename;
        }

        // Update status text
        const statusEl = item.querySelector('.qi-status-text');
        if (statusEl) statusEl.textContent = data.message || '';

        // Update progress bar
        let progressBar = item.querySelector('.qi-progress-bar');
        if (data.status === 'processing') {
            if (!progressBar) {
                const infoEl = item.querySelector('.qi-info');
                const barHtml = document.createElement('div');
                barHtml.className = 'qi-progress-bar';
                barHtml.innerHTML = `<div class="qi-progress-fill" style="width: ${data.progress}%"></div>`;
                infoEl.appendChild(barHtml);
            } else {
                const fill = progressBar.querySelector('.qi-progress-fill');
                if (fill) fill.style.width = (data.progress || 0) + '%';
            }
        } else if (progressBar) {
            progressBar.remove();
        }

        // Show saved icon for complete
        if (data.status === 'complete') {
            let savedIcon = item.querySelector('.qi-saved-icon');
            if (!savedIcon) {
                const div = document.createElement('div');
                div.className = 'qi-saved-icon';
                div.title = data.saved_path ? `Saved: ${data.saved_path}` : 'Saved to output folder';
                div.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>`;
                item.appendChild(div);
            }
            // Remove the remove button if it exists
            const removeBtn = item.querySelector('.qi-remove');
            if (removeBtn) removeBtn.remove();
        }

        updateQueueTitle();
    }

    function updateQueueTitle() {
        const total = selectedFiles.length + uploadedJobs.length;
        const processing = uploadedJobs.filter(jid => {
            const item = document.getElementById(`qi-${jid}`);
            return item && item.classList.contains('qi-processing');
        }).length;
        const complete = uploadedJobs.filter(jid => {
            const item = document.getElementById(`qi-${jid}`);
            return item && item.classList.contains('qi-complete');
        }).length;

        if (isProcessing) {
            queueTitle.textContent = `Processing (${complete}/${uploadedJobs.length} done)`;
        } else {
            queueTitle.textContent = `Video Queue (${total} file${total !== 1 ? 's' : ''})`;
        }
    }

    function updateStartButton() {
        // While a batch is running, the button stays in its processing state —
        // adding more files auto-queues them, no second click needed.
        if (isProcessing) {
            startBtn.disabled = true;
            startBtnText.textContent = 'Processing... (add more anytime)';
            return;
        }
        if (!outputDir) {
            startBtn.disabled = true;
            startBtnText.textContent = 'Select output folder first';
        } else if (selectedFiles.length === 0) {
            startBtn.disabled = true;
            startBtnText.textContent = 'Add videos to process';
        } else {
            startBtn.disabled = false;
            startBtnText.textContent = `Start Processing (${selectedFiles.length} video${selectedFiles.length !== 1 ? 's' : ''})`;
        }
    }

    // ── Settings Value Display + Slider Fill ──
    function initSlider(inputEl, displayFn) {
        function updateFill() {
            const min = parseFloat(inputEl.min);
            const max = parseFloat(inputEl.max);
            const val = parseFloat(inputEl.value);
            const pct = ((val - min) / (max - min)) * 100;
            inputEl.style.setProperty('--range-fill', pct.toFixed(1) + '%');
        }
        updateFill();
        inputEl.addEventListener('input', () => {
            updateFill();
            if (displayFn) displayFn();
        });
    }

    initSlider(zoomFactor, () => {
        document.getElementById('zoom-factor-value').textContent =
            Math.round(zoomFactor.value * 100) + '%';
    });

    initSlider(smoothingSpeed, () => {
        document.getElementById('smoothing-speed-value').textContent =
            parseFloat(smoothingSpeed.value).toFixed(2);
    });

    initSlider(switchDuration, () => {
        document.getElementById('switch-duration-value').textContent =
            parseFloat(switchDuration.value).toFixed(1) + 's';
    });

    initSlider(maxFaces, () => {
        document.getElementById('max-faces-value').textContent = maxFaces.value;
    });

    // ── Start Processing ──
    startBtn.addEventListener('click', async () => {
        if (!outputDir) {
            alert('Please select an output folder first.');
            return;
        }
        if (selectedFiles.length === 0) return;

        isProcessing = true;
        startBtn.disabled = true;
        startBtnText.textContent = 'Processing...';
        summarySection.classList.add('hidden');

        await flushPendingToQueue();
    });

    // Upload every pending file to the server queue, then make sure each job is
    // being monitored. Safe to call mid-batch — used both by "Start Processing"
    // and by "Add More" while videos are already being zoomed.
    async function flushPendingToQueue() {
        if (!outputDir || selectedFiles.length === 0) return;

        // New work is incoming, so we're processing again — hide any old summary.
        isProcessing = true;
        summarySection.classList.add('hidden');
        startBtn.disabled = true;
        startBtnText.textContent = 'Processing...';

        const filesToUpload = [...selectedFiles];
        selectedFiles = [];
        renderQueue();

        uploadsInFlight += filesToUpload.length;
        for (const file of filesToUpload) {
            await uploadAndTrack(file);
            uploadsInFlight--;
            // Watch each job as soon as it's queued so it streams progress.
            monitorAllJobs();
        }
    }

    async function uploadAndTrack(file) {
        const formData = new FormData();
        formData.append('video', file);
        formData.append('zoom_factor', zoomFactor.value);
        formData.append('smoothing_speed', smoothingSpeed.value);
        formData.append('min_switch_duration', switchDuration.value);
        formData.append('max_faces', maxFaces.value);
        formData.append('analysis_fps', '10');
        formData.append('mar_threshold', '0.12');

        // Create a temporary queue item for upload progress
        const tempId = 'upload-' + Math.random().toString(36).substr(2, 6);
        const tempItem = createQueueItem({
            id: tempId,
            name: file.name,
            size: formatSize(file.size),
            status: 'uploading',
            message: 'Uploading...',
            progress: 0,
        });
        tempItem.id = `qi-${tempId}`;
        queueList.appendChild(tempItem);

        try {
            const response = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();

                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        const pct = Math.round((e.loaded / e.total) * 100);
                        const statusEl = tempItem.querySelector('.qi-status-text');
                        if (statusEl) statusEl.textContent = `Uploading... ${pct}%`;
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status === 200) {
                        resolve(JSON.parse(xhr.responseText));
                    } else {
                        try {
                            const err = JSON.parse(xhr.responseText);
                            reject(new Error(err.error || 'Upload failed'));
                        } catch {
                            reject(new Error('Upload failed: ' + xhr.status));
                        }
                    }
                });

                xhr.addEventListener('error', () => reject(new Error('Network error')));
                xhr.open('POST', '/api/upload');
                xhr.send(formData);
            });

            // Replace temp item with real job tracking
            tempItem.remove();
            uploadedJobs.push(response.job_id);

            const jobItem = createQueueItem({
                id: response.job_id,
                name: file.name,
                size: formatSize(file.size),
                status: 'queued',
                message: 'Waiting in queue...',
                progress: 0,
            });
            jobItem.id = `qi-${response.job_id}`;
            queueList.appendChild(jobItem);

        } catch (err) {
            // Show error on this item
            tempItem.className = 'queue-item qi-error';
            const iconEl = tempItem.querySelector('.qi-icon');
            if (iconEl) iconEl.innerHTML = getStatusIcon('error');
            const statusEl = tempItem.querySelector('.qi-status-text');
            if (statusEl) statusEl.textContent = `Upload failed: ${err.message}`;
        }
    }

    // ── Monitor all jobs via SSE ──
    function monitorAllJobs() {
        for (const jobId of uploadedJobs) {
            if (activeStreams[jobId]) continue;
            startJobStream(jobId);
        }
    }

    function startJobStream(jobId) {
        const es = new EventSource(`/api/stream/${jobId}`);
        activeStreams[jobId] = es;

        es.addEventListener('message', (e) => {
            const data = JSON.parse(e.data);
            updateQueueItem(jobId, data);

            if (data.status === 'complete' || data.status === 'error') {
                es.close();
                delete activeStreams[jobId];
                checkAllDone();
            }
        });

        es.addEventListener('error', () => {
            es.close();
            delete activeStreams[jobId];
            // Fallback to polling
            startJobPolling(jobId);
        });
    }

    function startJobPolling(jobId) {
        const poll = setInterval(async () => {
            try {
                const res = await fetch(`/api/status/${jobId}`);
                const data = await res.json();
                updateQueueItem(jobId, data);

                if (data.status === 'complete' || data.status === 'error') {
                    clearInterval(poll);
                    checkAllDone();
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 1000);
    }

    function checkAllDone() {
        // Don't declare victory while files are still uploading into the queue
        // or pending files are waiting to be flushed — more work is coming.
        if (uploadsInFlight > 0 || selectedFiles.length > 0) return;

        const allDone = uploadedJobs.every(jid => {
            const item = document.getElementById(`qi-${jid}`);
            return item && (item.classList.contains('qi-complete') || item.classList.contains('qi-error'));
        });

        if (allDone && uploadedJobs.length > 0) {
            isProcessing = false;

            const completeCount = uploadedJobs.filter(jid => {
                const item = document.getElementById(`qi-${jid}`);
                return item && item.classList.contains('qi-complete');
            }).length;
            const errorCount = uploadedJobs.length - completeCount;

            // Show summary
            if (errorCount === 0) {
                summaryTitle.textContent = 'All Videos Processed!';
                summaryMessage.textContent = `${completeCount} video${completeCount !== 1 ? 's' : ''} processed and saved to: ${outputDir}`;
            } else {
                summaryTitle.textContent = 'Processing Complete';
                summaryMessage.textContent = `${completeCount} completed, ${errorCount} failed. Saved to: ${outputDir}`;
            }
            summarySection.classList.remove('hidden');
            if (errorCount === 0) launchConfetti();

            updateQueueTitle();
            startBtn.disabled = false;
            startBtnText.textContent = 'All done!';
            addMoreBtn.style.display = '';
        }
    }

    // ── Confetti burst ──
    function launchConfetti() {
        const container = document.getElementById('confetti-container');
        if (!container) return;
        const colors = ['#8b5cf6', '#22c55e', '#6366f1', '#f59e0b', '#ec4899'];
        for (let i = 0; i < 48; i++) {
            const p = document.createElement('div');
            p.className = 'confetti-particle';
            p.style.cssText = [
                'left:' + (30 + Math.random() * 40) + 'vw',
                'top:' + (20 + Math.random() * 30) + 'vh',
                'background:' + colors[Math.floor(Math.random() * colors.length)],
                '--tx:' + (Math.random() * 200 - 100) + 'px',
                '--ty:' + (Math.random() * 300 + 50) + 'px',
                'animation-delay:' + (Math.random() * 400) + 'ms',
                'animation-duration:' + (600 + Math.random() * 600) + 'ms',
                'transform:rotate(' + (Math.random() * 360) + 'deg)',
                'width:' + (4 + Math.random() * 6) + 'px',
                'height:' + (4 + Math.random() * 8) + 'px',
            ].join(';');
            container.appendChild(p);
        }
        setTimeout(() => { container.innerHTML = ''; }, 1500);
    }

    // ── Reset / New Batch ──
    newBatchBtn.addEventListener('click', resetAll);

    function resetAll() {
        // Close all streams
        Object.values(activeStreams).forEach(es => es.close());
        activeStreams = {};

        selectedFiles = [];
        uploadedJobs = [];
        isProcessing = false;
        queueList.innerHTML = '';

        summarySection.classList.add('hidden');
        queueSection.classList.add('hidden');
        settingsSection.classList.add('hidden');

        updateStartButton();

        // Clear server queue
        fetch('/api/clear-queue', { method: 'POST' }).catch(() => {});
    }

    // ── Helpers ──
    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Section entrance animation ──
    function animateSectionIn(sectionEl, delayMs) {
        sectionEl.style.animationDelay = (delayMs || 0) + 'ms';
        sectionEl.style.animation = 'none';
        void sectionEl.offsetHeight;
        sectionEl.style.animation = '';
    }

    // Stagger visible sections on load
    document.querySelectorAll('.section:not(.hidden)').forEach((s, i) => {
        animateSectionIn(s, i * 60);
    });

    // ── Ripple effect on primary buttons ──
    function attachRipple(btn) {
        btn.addEventListener('click', function(e) {
            if (btn.disabled) return;
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const ripple = document.createElement('span');
            ripple.className = 'btn-ripple';
            ripple.style.left = (x - 10) + 'px';
            ripple.style.top  = (y - 10) + 'px';
            btn.appendChild(ripple);
            ripple.addEventListener('animationend', () => ripple.remove());
        });
    }
    document.querySelectorAll('.btn-primary').forEach(attachRipple);

    // ── Settings collapsible ──
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsBody = document.getElementById('settings-body');
    const collapseBtn = settingsToggle ? settingsToggle.querySelector('.btn-collapse') : null;

    if (settingsToggle && settingsBody && collapseBtn) {
        settingsToggle.addEventListener('click', () => {
            const isExpanded = collapseBtn.getAttribute('aria-expanded') === 'true';
            collapseBtn.setAttribute('aria-expanded', String(!isExpanded));
            if (isExpanded) {
                settingsBody.style.maxHeight = settingsBody.scrollHeight + 'px';
                requestAnimationFrame(() => {
                    settingsBody.classList.add('collapsed');
                    settingsBody.style.maxHeight = '';
                });
            } else {
                settingsBody.classList.remove('collapsed');
                settingsBody.style.maxHeight = settingsBody.scrollHeight + 'px';
                settingsBody.addEventListener('transitionend', () => {
                    settingsBody.style.maxHeight = '';
                }, { once: true });
            }
        });
    }

    // ── Init ──
    updateStartButton();
});
