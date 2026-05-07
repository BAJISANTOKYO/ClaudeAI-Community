document.addEventListener('DOMContentLoaded', () => {
    // ============================================================
    // Elements
    // ============================================================
    const noteInput    = document.getElementById('note-input');
    const clearBtn     = document.getElementById('clear-btn');
    const discordBtn   = document.getElementById('discord-btn');
    const statusEl     = document.getElementById('status');
    const charCountEl  = document.getElementById('char-count');

    const tabNotesBtn  = document.getElementById('tab-notes-btn');
    const tabLogBtn    = document.getElementById('tab-log-btn');
    const tabNotes     = document.getElementById('tab-notes');
    const tabLog       = document.getElementById('tab-log');

    const cookieLogList = document.getElementById('cookie-log-list');
    const clearLogBtn   = document.getElementById('clear-log-btn');

    let saveTimeout;
    let statusTimeout;

    // ============================================================
    // Tab Switching
    // ============================================================
    function switchTab(tab) {
        if (tab === 'notes') {
            tabNotes.classList.add('active');
            tabLog.classList.remove('active');
            tabNotesBtn.classList.add('active');
            tabLogBtn.classList.remove('active');
        } else {
            tabLog.classList.add('active');
            tabNotes.classList.remove('active');
            tabLogBtn.classList.add('active');
            tabNotesBtn.classList.remove('active');
            loadCookieLog();
        }
    }

    tabNotesBtn.addEventListener('click', () => switchTab('notes'));
    tabLogBtn.addEventListener('click', () => switchTab('log'));

    // ============================================================
    // Notes Tab Logic
    // ============================================================

    // Load saved note
    chrome.storage.local.get(['noteText'], (result) => {
        if (result.noteText) {
            noteInput.value = result.noteText;
            updateCharCount();
        }
    });

    // Save note on input (debounced)
    noteInput.addEventListener('input', () => {
        updateCharCount();
        clearTimeout(saveTimeout);
        statusEl.classList.remove('visible');
        statusEl.classList.remove('error');
        statusEl.textContent = 'Saving...';

        saveTimeout = setTimeout(() => {
            const text = noteInput.value;
            chrome.storage.local.set({ noteText: text }, () => {
                if (chrome.runtime.lastError) {
                    showStatus('Error saving', 'error');
                } else {
                    showStatus('Saved', 'success');
                }
            });
        }, 400);
    });

    // Clear note
    clearBtn.addEventListener('click', () => {
        if (noteInput.value.trim() === '') return;
        noteInput.value = '';
        updateCharCount();
        chrome.storage.local.set({ noteText: '' }, () => {
            if (chrome.runtime.lastError) {
                showStatus('Error clearing', 'error');
            } else {
                showStatus('Cleared', 'success');
            }
        });
        noteInput.focus();
    });

    // Send note to Discord
    if (discordBtn) {
        discordBtn.addEventListener('click', () => {
            const message = noteInput.value;
            if (!message.trim()) {
                showStatus('Note is empty!', 'error');
                return;
            }

            const payload = {
                embeds: [{
                    title: "📝 New Note from Lumina",
                    description: message,
                    color: 0x5865F2,
                    timestamp: new Date().toISOString()
                }]
            };

            chrome.runtime.sendMessage({ action: 'sendToDiscord', payload }, () => {
                showStatus('Sent to Discord!', 'success');
            });
        });
    }

    function updateCharCount() {
        const count = noteInput.value.length;
        charCountEl.textContent = `${count} char${count !== 1 ? 's' : ''}`;
    }

    function showStatus(text, type = 'success') {
        clearTimeout(statusTimeout);
        statusEl.textContent = text;
        statusEl.classList.remove('error');
        if (type === 'error') statusEl.classList.add('error');
        statusEl.classList.add('visible');
        statusTimeout = setTimeout(() => {
            statusEl.classList.remove('visible');
        }, 2000);
    }

    // ============================================================
    // Cookie Log Tab Logic
    // ============================================================
    function loadCookieLog() {
        chrome.runtime.sendMessage({ action: 'getCookieLog' }, (res) => {
            renderLog(res && res.log ? res.log : []);
        });
    }

    function renderLog(log) {
        if (!log || log.length === 0) {
            cookieLogList.innerHTML = '<p class="log-empty">No events recorded yet.<br>Browse a site to see activity.</p>';
            return;
        }

        cookieLogList.innerHTML = log.map(entry => {
            const isRemoved = entry.action && entry.action.toLowerCase().includes('removed');
            const actionClass = isRemoved ? 'removed' : 'added';
            const actionLabel = isRemoved ? '🗑 Removed' : '✅ Added';
            return `
                <div class="log-item">
                    <div class="log-item-header">
                        <span class="log-item-name">${escapeHtml(entry.name)}</span>
                        <span class="log-item-action ${actionClass}">${actionLabel}</span>
                    </div>
                    <div class="log-item-domain">${escapeHtml(entry.domain)}</div>
                    <div class="log-item-time">${escapeHtml(entry.time)}</div>
                </div>
            `;
        }).join('');
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    clearLogBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'clearCookieLog' }, () => {
            renderLog([]);
        });
    });
});
