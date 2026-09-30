/* global chrome */

import { SITES, requestApiAccess, syncSession } from './session_sync.js';

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
const syncSection = document.getElementById('sync-section');
const syncButtons = document.querySelectorAll('#sync-section button[data-site]');

let currentUrl = '';
// Loaded once in init(); the sync click handler needs it synchronously so that
// chrome.permissions.request still runs inside the click's user gesture.
let currentConfig = DEFAULT_CONFIG;

async function init() {
  const config = await loadConfig();
  currentConfig = config;

  if (!config.apiUrl) {
    configWarning.classList.remove('hidden');
    formContainer.classList.add('hidden');
    return;
  }

  syncSection.classList.remove('hidden');

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

function setSyncStatus(siteId, type, message) {
  const line = document.getElementById(`sync-status-${siteId}`);
  line.className = `sync-status ${type}`;
  line.textContent = message;
}

// Read the site's cookies and PUT them to the API. Cookie values stay inside
// syncSession(); only its fixed status message reaches the page.
async function syncSite(event) {
  const button = event.currentTarget;
  const siteId = button.dataset.site;
  // Must be the first call: the permission prompt needs the click's gesture.
  // Resolves immediately, without a prompt, once the origin is granted.
  const access = requestApiAccess(currentConfig.apiUrl, chrome.permissions);

  button.disabled = true;
  setSyncStatus(siteId, 'loading', `Syncing ${SITES[siteId].label} session...`);
  try {
    const result = await syncSession(siteId, currentConfig, {
      cookies: chrome.cookies,
      fetch: (url, init) => fetch(url, init),
      access: await access,
    });
    setSyncStatus(siteId, result.ok ? 'success' : 'error', result.message);
  } catch {
    setSyncStatus(siteId, 'error', `${SITES[siteId].label} sync failed unexpectedly.`);
  } finally {
    button.disabled = false;
  }
}

// Event listeners
saveBtn.addEventListener('click', saveUrl);

syncButtons.forEach((button) => button.addEventListener('click', syncSite));

openOptionsLink.addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

init();
