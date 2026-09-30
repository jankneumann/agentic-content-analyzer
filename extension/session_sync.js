// Session sync: read a site's login cookies from this browser and PUT them to
// the API's /api/v1/browser-sessions/<site> endpoint, which validates them and
// writes them to OpenBao.
//
// Pure logic, no DOM: chrome.cookies, chrome.permissions and fetch are passed in
// so extension/tests/ can exercise it under `node --test`.
//
// Secrecy rules: cookie values are never logged, displayed, or written to
// chrome.storage; references are dropped as soon as the request is sent.
// Status messages are fixed strings built from the HTTP status, a problem
// `code` that matches CODE_PATTERN, `saved_at`, and a numeric Retry-After only.

/** Sites and the cookies each endpoint takes. `field` is the request body key. */
export const SITES = Object.freeze({
  substack: Object.freeze({
    label: 'Substack',
    // substack.sid is set on .substack.com; this URL selects it.
    cookieUrl: 'https://substack.com',
    cookies: Object.freeze([{ name: 'substack.sid', field: 'substack_sid' }]),
  }),
  x: Object.freeze({
    label: 'X',
    // x.com only: twitter.com redirects here and holds no current session.
    cookieUrl: 'https://x.com',
    cookies: Object.freeze([
      { name: 'auth_token', field: 'auth_token' },
      { name: 'ct0', field: 'ct0' },
    ]),
  }),
});

const CODE_PATTERN = /^[a-z][a-z0-9_]{0,63}$/;

function siteFor(siteId) {
  const site = Object.prototype.hasOwnProperty.call(SITES, siteId) ? SITES[siteId] : null;
  if (!site) throw new Error(`Unknown site: ${siteId}`);
  return site;
}

/**
 * Read the site's session cookies with chrome.cookies.
 * Returns the request body ({field: value}) or null when any cookie is missing
 * or empty, so a partial X pair is never sent.
 */
export async function readSessionCookies(siteId, cookiesApi) {
  const site = siteFor(siteId);
  const body = {};
  for (const { name, field } of site.cookies) {
    const cookie = await cookiesApi.get({ url: site.cookieUrl, name });
    if (!cookie || !cookie.value) return null;
    body[field] = cookie.value;
  }
  return body;
}

/**
 * Host-permission origins to request for the API URL. Only https hosts under
 * ts.net qualify: the manifest's optional_host_permissions is https://*.ts.net/*,
 * and chrome.permissions.request throws for anything outside it. The pattern
 * omits the port so it matches the host on any port.
 */
export function apiPermissionOrigins(apiUrl) {
  let url;
  try {
    url = new URL(apiUrl);
  } catch {
    return [];
  }
  if (url.protocol !== 'https:' || !url.hostname.endsWith('.ts.net')) return [];
  return [`https://${url.hostname}/*`];
}

/**
 * Request host permission for the API origin. Calls chrome.permissions.request
 * synchronously (before any await) so it runs inside the click's user gesture;
 * once granted it resolves without a prompt.
 * Resolves to 'granted' | 'denied' | 'error' | 'not-needed'.
 */
export function requestApiAccess(apiUrl, permissionsApi) {
  const origins = apiPermissionOrigins(apiUrl);
  if (origins.length === 0 || !permissionsApi) return Promise.resolve('not-needed');
  let pending;
  try {
    pending = permissionsApi.request({ origins });
  } catch {
    return Promise.resolve('error');
  }
  return Promise.resolve(pending).then(
    (granted) => (granted ? 'granted' : 'denied'),
    () => 'error',
  );
}

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

/** True when cookies may be sent to this API URL: https, or http on loopback. */
export function isSecureApiUrl(apiUrl) {
  let url;
  try {
    url = new URL(apiUrl);
  } catch {
    return false;
  }
  return url.protocol === 'https:' || (url.protocol === 'http:' && LOOPBACK_HOSTS.has(url.hostname));
}

export function sessionSyncEndpoint(apiUrl, siteId) {
  siteFor(siteId);
  return `${apiUrl.replace(/\/+$/, '')}/api/v1/browser-sessions/${siteId}`;
}

function formatSavedAt(value) {
  const date = typeof value === 'string' ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return 'time unknown';
  return date.toLocaleString();
}

function problemCode(body) {
  const code = body && typeof body === 'object' ? body.code : null;
  return typeof code === 'string' && CODE_PATTERN.test(code) ? code : null;
}

/**
 * Map an API response to {ok, message}. `retryAfter` is the Retry-After header.
 * Status 0 is the opaque response of a redirect (fetch uses redirect: 'manual').
 */
export function describeSyncResult(siteId, { status, body = null, retryAfter = null }) {
  const { label } = siteFor(siteId);
  const code = problemCode(body);

  if (status >= 200 && status < 300) {
    const savedAt = body && typeof body === 'object' ? body.saved_at : null;
    // A saved_at that is not a date is reported as unknown, never echoed.
    return { ok: true, message: `Synced ${label} session (saved ${formatSavedAt(savedAt)}).` };
  }

  let message;
  switch (status) {
    case 0:
      message = 'The API URL redirected. Set the exact API origin in Options.';
      break;
    case 401:
      message =
        'API refused the request (401): set the API key in Options. The server must have ADMIN_API_KEY configured.';
      break;
    case 403:
      message = 'API key rejected (403): check the API key in Options.';
      break;
    case 404:
      message =
        'Sync endpoint not found (404): check that the API URL is the API origin and the server is up to date.';
      break;
    case 413:
      message = `The ${label} cookies are larger than the API accepts (413).`;
      break;
    case 422:
      message =
        code === 'session_invalid'
          ? `${label} refused this session: log in to ${label} again in this browser, then sync.`
          : `The API rejected the ${label} cookies (${code ?? '422'}): log in to ${label} again in this browser, then sync.`;
      break;
    case 429: {
      const seconds = typeof retryAfter === 'string' && /^\d{1,6}$/.test(retryAfter) ? retryAfter : null;
      message = `Too many sync attempts: retry in ${seconds ? `${seconds}s` : 'a few minutes'}.`;
      break;
    }
    case 502:
      if (code === 'session_validation_unavailable') {
        message = `${label} could not be reached to validate the session: retry later.`;
      } else if (code === 'openbao_write_failed') {
        message = "OpenBao refused the write: retry later, or check the server's OpenBao role.";
      } else {
        message = 'Bad gateway (502): retry later.';
      }
      break;
    case 503:
      message =
        code === 'openbao_not_configured'
          ? 'The server has no OpenBao configured (openbao_not_configured): nothing was saved.'
          : 'API unavailable (503): retry later.';
      break;
    default:
      message = `${label} sync failed (HTTP ${status}${code ? `, ${code}` : ''}).`;
  }
  return { ok: false, message };
}

function describeNetworkError(apiUrl, access) {
  let message = `Could not reach the API at ${apiUrl}. Check the API URL and that this machine is on the tailnet.`;
  const [origin] = apiPermissionOrigins(apiUrl);
  if (origin && access && access !== 'granted' && access !== 'not-needed') {
    const host = new URL(apiUrl).hostname;
    message += ` Access to ${host} was not granted: open Options and click Save Settings to grant it.`;
  }
  return { ok: false, message };
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * Read the site's cookies and PUT them to the API.
 * deps: {cookies: chrome.cookies, fetch, access?: result of requestApiAccess}.
 * Resolves to {ok, message}; never rejects for expected failures.
 */
export async function syncSession(siteId, config, deps) {
  const { label } = siteFor(siteId);
  const apiUrl = (config && config.apiUrl) || '';
  const apiKey = (config && config.apiKey) || '';

  if (!apiUrl) return { ok: false, message: 'No API URL configured: set it in Options.' };
  if (!apiKey) {
    return {
      ok: false,
      message: 'No API key configured: set it in Options (session sync requires X-Admin-Key).',
    };
  }

  if (!isSecureApiUrl(apiUrl)) {
    return {
      ok: false,
      message: 'Session sync needs an https:// API URL (plain http only for localhost): cookies are never sent unencrypted.',
    };
  }

  let body;
  try {
    body = await readSessionCookies(siteId, deps.cookies);
  } catch {
    return {
      ok: false,
      message: `Could not read ${label} cookies: reload the extension so it has the cookies permission.`,
    };
  }
  if (!body) {
    return { ok: false, message: `Not logged in to ${label} in this browser. Log in, then sync again.` };
  }

  let response;
  try {
    response = await deps.fetch(sessionSyncEndpoint(apiUrl, siteId), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': apiKey },
      body: JSON.stringify(body),
      // Never attach the API origin's cookies, never follow a redirect with the
      // cookies in the body, never cache.
      credentials: 'omit',
      redirect: 'manual',
      cache: 'no-store',
    });
  } catch {
    return describeNetworkError(apiUrl, deps.access);
  } finally {
    body = null;
  }

  const payload = await readJson(response);
  return describeSyncResult(siteId, {
    status: response.status,
    body: payload,
    retryAfter: response.headers.get('Retry-After'),
  });
}
