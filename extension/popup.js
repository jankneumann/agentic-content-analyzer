/* global chrome */

const DEFAULT_CONFIG = {
  apiUrl: '',
  apiKey: '',
};

const urlDisplay = document.getElementById('page-url');
const titleInput = document.getElementById('title');
const excerptInput = document.getElementById('excerpt');
const tagsInput = document.getElementById('tags');
const saveBtn = document.getElementById('save-btn');
const statusDiv = document.getElementById('status');
const configWarning = document.getElementById('config-warning');
const formContainer = document.getElementById('save-form-container');
const openOptionsLink = document.getElementById('open-options');

let currentUrl = '';

async function init() {
  const config = await loadConfig();

  if (!config.apiUrl) {
    configWarning.classList.remove('hidden');
    formContainer.classList.add('hidden');
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    currentUrl = tab.url || '';
    urlDisplay.textContent = currentUrl;
    titleInput.value = tab.title || '';
  }

  if (tab && tab.id) {
    try {
      const [result] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => window.getSelection().toString(),
      });
      if (result && result.result) {
        excerptInput.value = result.result.slice(0, 5000);
      }
    } catch {
      // Can't access page (e.g., chrome:// URLs) — ignore
    }
  }
}

async function loadConfig() {
  try {
    const items = await chrome.storage.sync.get(DEFAULT_CONFIG);
    return items;
  } catch {
    return DEFAULT_CONFIG;
  }
}

function showStatus(type, message) {
  statusDiv.className = `status ${type}`;
  statusDiv.textContent = message;
  statusDiv.classList.remove('hidden');
}

function parseTags(input) {
  if (!input.trim()) return null;
  return input
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

async function saveUrl() {
  const config = await loadConfig();

  if (!currentUrl) {
    showStatus('error', 'No URL to save');
    return;
  }

  if (!currentUrl.startsWith('http://') && !currentUrl.startsWith('https://')) {
    showStatus('error', 'Only http:// and https:// URLs can be saved');
    return;
  }

  // Disable button and show loading
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (config.apiKey) {
      headers['X-Admin-Key'] = config.apiKey;
    }

    showStatus('loading', 'Saving URL...');
    const endpoint = `${config.apiUrl}/api/v1/ingestions`;
    const body = {
      kind: 'url',
      url: currentUrl,
      title: titleInput.value || null,
      tags: parseTags(tagsInput.value),
      notes: excerptInput.value || null,
    };

    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    const result = await response.json();

    if (response.ok) {
      const operationId = result.operation_id || 'unknown';
      showStatus('success', `Queued (operation ${operationId})`);
      saveBtn.textContent = 'Saved';
    } else {
      const detail = result.detail || result.title || 'Save failed';
      const message = typeof detail === 'string' ? detail : JSON.stringify(detail);
      throw new Error(message);
    }
  } catch (error) {
    showStatus('error', `Error: ${error.message}`);
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save';
  }
}

// Event listeners
saveBtn.addEventListener('click', saveUrl);

openOptionsLink.addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

init();
