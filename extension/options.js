/* global chrome */

const apiUrlInput = document.getElementById('api-url');
const apiKeyInput = document.getElementById('api-key');
const saveBtn = document.getElementById('save-btn');
const statusSpan = document.getElementById('status');

function showStatus(type, message) {
  statusSpan.textContent = message;
  statusSpan.className = `status show ${type}`;
  setTimeout(() => {
    statusSpan.className = 'status';
  }, 2000);
}

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

  chrome.storage.sync.set(
    {
      apiUrl: apiUrl,
      apiKey: apiKeyInput.value.trim(),
    },
    () => {
      showStatus('success', 'Settings saved');
    }
  );
});
