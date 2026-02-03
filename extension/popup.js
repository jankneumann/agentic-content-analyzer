/* global chrome */

const DEFAULT_CONFIG = {
  apiUrl: '',
  apiKey: '',
  captureFullPage: true, // Default: full page capture enabled
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
const captureToggle = document.getElementById('capture-toggle');
const captureStatus = document.getElementById('capture-status');

let currentUrl = '';
let capturedHtml = null; // Stores the captured DOM content

// Capture the rendered DOM from the current tab
async function captureDOM(tabId) {
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => document.documentElement.outerHTML,
    });
    if (result && result.result) {
      return result.result;
    }
  } catch (error) {
    console.warn('DOM capture failed:', error);
  }
  return null;
}

// Update the capture status indicator
function updateCaptureStatus(html, isFullCaptureEnabled) {
  if (!captureStatus) return;

  if (!isFullCaptureEnabled) {
    captureStatus.textContent = 'URL only';
    captureStatus.className = 'capture-status url-only';
  } else if (html) {
    captureStatus.textContent = 'Full page captured ✓';
    captureStatus.className = 'capture-status captured';
  } else {
    captureStatus.textContent = 'Capture failed (URL only)';
    captureStatus.className = 'capture-status fallback';
  }
}

// Load config and current tab info on popup open
async function init() {
  const config = await loadConfig();

  if (!config.apiUrl) {
    configWarning.classList.remove('hidden');
    formContainer.classList.add('hidden');
    return;
  }

  // Set capture toggle state from saved preference
  if (captureToggle) {
    captureToggle.checked = config.captureFullPage !== false; // Default true
  }

  // Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    currentUrl = tab.url || '';
    urlDisplay.textContent = currentUrl;
    titleInput.value = tab.title || '';
  }

  // Get selected text and capture DOM in parallel
  if (tab && tab.id) {
    const capturePromises = [];

    // Capture selected text
    capturePromises.push(
      chrome.scripting
        .executeScript({
          target: { tabId: tab.id },
          func: () => window.getSelection().toString(),
        })
        .then(([result]) => {
          if (result && result.result) {
            excerptInput.value = result.result.slice(0, 5000);
          }
        })
        .catch(() => {
          // Can't access page (e.g., chrome:// URLs) — ignore
        })
    );

    // Capture DOM if full page capture is enabled
    if (config.captureFullPage !== false) {
      capturePromises.push(
        captureDOM(tab.id).then((html) => {
          capturedHtml = html;
        })
      );
    }

    // Wait for all captures to complete
    await Promise.all(capturePromises);
  }

  // Update capture status indicator
  updateCaptureStatus(capturedHtml, config.captureFullPage !== false);
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

  const isFullCapture = config.captureFullPage !== false && capturedHtml;

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (config.apiKey) {
      headers['Authorization'] = `Bearer ${config.apiKey}`;
    }

    let endpoint;
    let body;

    if (isFullCapture) {
      // Full page capture: send HTML to save-page endpoint
      showStatus('loading', 'Saving full page...');
      endpoint = `${config.apiUrl}/api/v1/content/save-page`;
      body = {
        url: currentUrl,
        html: capturedHtml,
        title: titleInput.value || null,
        excerpt: excerptInput.value || null,
        tags: parseTags(tagsInput.value),
        source: 'chrome_extension',
      };
    } else {
      // URL-only: use existing save-url endpoint
      showStatus('loading', 'Saving URL...');
      endpoint = `${config.apiUrl}/api/v1/content/save-url`;
      body = {
        url: currentUrl,
        title: titleInput.value || null,
        excerpt: excerptInput.value || null,
        tags: parseTags(tagsInput.value),
        source: 'chrome_extension',
      };
    }

    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    const result = await response.json();

    if (response.ok) {
      if (result.duplicate) {
        showStatus('success', `Already saved (ID: ${result.content_id})`);
      } else {
        const mode = isFullCapture ? 'Full page' : 'URL';
        showStatus('success', `${mode} saved! (ID: ${result.content_id})`);
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

// Handle capture toggle changes
if (captureToggle) {
  captureToggle.addEventListener('change', async () => {
    const newValue = captureToggle.checked;

    // Save preference to chrome.storage.sync
    await chrome.storage.sync.set({ captureFullPage: newValue });

    // If enabling and we don't have HTML captured yet, try to capture now
    if (newValue && !capturedHtml) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.id) {
        capturedHtml = await captureDOM(tab.id);
      }
    }

    // Update status indicator
    updateCaptureStatus(capturedHtml, newValue);
  });
}

// Initialize
init();
