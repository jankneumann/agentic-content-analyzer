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

// Load config and current tab info on popup open
async function init() {
  const config = await loadConfig();

  if (!config.apiUrl) {
    configWarning.classList.remove('hidden');
    formContainer.classList.add('hidden');
    return;
  }

  // Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    currentUrl = tab.url || '';
    urlDisplay.textContent = currentUrl;
    titleInput.value = tab.title || '';
  }

  // Get selected text from the page
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

  // Disable button and show loading
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';
  showStatus('loading', 'Saving URL...');

  try {
    const body = {
      url: currentUrl,
      title: titleInput.value || null,
      excerpt: excerptInput.value || null,
      tags: parseTags(tagsInput.value),
      source: 'chrome_extension',
    };

    const headers = { 'Content-Type': 'application/json' };
    if (config.apiKey) {
      headers['Authorization'] = `Bearer ${config.apiKey}`;
    }

    const response = await fetch(`${config.apiUrl}/api/v1/content/save-url`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    const result = await response.json();

    if (response.ok) {
      if (result.duplicate) {
        showStatus('success', `Already saved (ID: ${result.content_id})`);
      } else {
        showStatus('success', `Saved! (ID: ${result.content_id})`);
      }
      saveBtn.textContent = 'Saved';
    } else {
      const detail = result.detail || 'Save failed';
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

// Initialize
init();
