/* global chrome */

import { requestApiAccess } from './session_sync.js';

const apiUrlInput = document.getElementById('api-url');
const apiKeyInput = document.getElementById('api-key');
const saveBtn = document.getElementById('save-btn');
const statusSpan = document.getElementById('status');

function showStatus(type, message, durationMs = 2000) {
  statusSpan.textContent = message;
  statusSpan.className = `status show ${type}`;
  setTimeout(() => {
    statusSpan.className = 'status';
  }, durationMs);
}

// Outcome of the host-permission request for a tailnet API origin.
const ACCESS_STATUS = {
  'not-needed': ['success', 'Settings saved'],
  granted: ['success', 'Settings saved; API access granted'],
  denied: ['error', 'Settings saved; API access not granted, so the API must allow this extension in ALLOWED_ORIGINS'],
  error: ['error', 'Settings saved, but API access could not be requested'],
};

// Load saved settings
chrome.storage.sync.get({ apiUrl: '', apiKey: '' }, (items) => {
  apiUrlInput.value = items.apiUrl;
  apiKeyInput.value = items.apiKey;
});

// Save settings
saveBtn.addEventListener('click', () => {
  let apiUrl = apiUrlInput.value.trim();

  // Strip trailing slash
  if (apiUrl.endsWith('/')) {
    apiUrl = apiUrl.replace(/\/+$/, '');
  }

  // Basic URL validation
  if (apiUrl && !apiUrl.startsWith('http://') && !apiUrl.startsWith('https://')) {
    showStatus('error', 'URL must start with http:// or https://');
    return;
  }

  // Ask for host permission on a tailnet API origin (https://*.ts.net) now,
  // inside this click's user gesture. It exempts the extension's requests from
  // CORS, so ALLOWED_ORIGINS needs no chrome-extension:// entry. Settings are
  // saved whether or not it is granted.
  const access = requestApiAccess(apiUrl, chrome.permissions);

  chrome.storage.sync.set(
    {
      apiUrl: apiUrl,
      apiKey: apiKeyInput.value.trim(),
    },
    async () => {
      const [type, message] = ACCESS_STATUS[await access];
      showStatus(type, message, type === 'success' ? 2000 : 6000);
    }
  );
});
