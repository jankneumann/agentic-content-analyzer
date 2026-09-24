// Unit tests for the extension's session-sync logic. Run from the repo root:
//   node --test extension/tests/
// chrome.cookies, chrome.permissions and fetch are faked; nothing touches the network.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import {
  SITES,
  apiPermissionOrigins,
  describeSyncResult,
  isSecureApiUrl,
  readSessionCookies,
  requestApiAccess,
  sessionSyncEndpoint,
  syncSession,
} from '../session_sync.js';

const SID = 'SENTINEL-substack-sid-value';
const AUTH = 'SENTINEL-auth-token-value';
const CT0 = 'SENTINEL-ct0-value';
const SECRETS = [SID, AUTH, CT0];

/** Fake chrome.cookies: jar maps "<url>|<name>" to a value. Records every call. */
function fakeCookies(jar) {
  const calls = [];
  return {
    calls,
    async get(details) {
      calls.push(details);
      const value = jar[`${details.url}|${details.name}`];
      return value === undefined ? null : { name: details.name, value, domain: '.example' };
    },
  };
}

function jsonResponse(status, body, headers = {}) {
  const lower = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: (name) => lower[name.toLowerCase()] ?? null },
    async json() {
      if (body === undefined) throw new SyntaxError('no body');
      return body;
    },
  };
}

function fakeFetch(response) {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url, init });
    if (response instanceof Error) throw response;
    return response;
  };
  fn.calls = calls;
  return fn;
}

const CONFIG = { apiUrl: 'https://gx-10.example.ts.net', apiKey: 'admin-key' };
const FULL_JAR = {
  'https://substack.com|substack.sid': SID,
  'https://x.com|auth_token': AUTH,
  'https://x.com|ct0': CT0,
};

function assertNoSecret(message) {
  for (const secret of SECRETS) {
    assert.ok(!message.includes(secret), `message leaked a cookie value: ${message}`);
  }
}

describe('readSessionCookies', () => {
  it('reads substack.sid from https://substack.com', async () => {
    const cookies = fakeCookies(FULL_JAR);
    assert.deepEqual(await readSessionCookies('substack', cookies), { substack_sid: SID });
    assert.deepEqual(cookies.calls, [{ url: 'https://substack.com', name: 'substack.sid' }]);
  });

  it('reads the X pair from https://x.com only', async () => {
    const cookies = fakeCookies(FULL_JAR);
    assert.deepEqual(await readSessionCookies('x', cookies), { auth_token: AUTH, ct0: CT0 });
    assert.ok(cookies.calls.every((c) => c.url === 'https://x.com'));
  });

  it('returns null when one X cookie is missing (never a partial pair)', async () => {
    const cookies = fakeCookies({ 'https://x.com|auth_token': AUTH });
    assert.equal(await readSessionCookies('x', cookies), null);
  });

  it('does not fall back to twitter.com', async () => {
    const cookies = fakeCookies({
      'https://twitter.com|auth_token': AUTH,
      'https://twitter.com|ct0': CT0,
    });
    assert.equal(await readSessionCookies('x', cookies), null);
    assert.ok(cookies.calls.every((c) => c.url === 'https://x.com'));
  });

  it('treats an empty cookie value as missing', async () => {
    const cookies = fakeCookies({ 'https://substack.com|substack.sid': '' });
    assert.equal(await readSessionCookies('substack', cookies), null);
  });

  it('rejects an unknown site', async () => {
    await assert.rejects(readSessionCookies('twitter', fakeCookies({})), /Unknown site/);
  });
});

describe('apiPermissionOrigins', () => {
  it('grants the tailnet host, any port', () => {
    assert.deepEqual(apiPermissionOrigins('https://gx-10.example.ts.net'), [
      'https://gx-10.example.ts.net/*',
    ]);
    assert.deepEqual(apiPermissionOrigins('https://gx-10.example.ts.net:8443/'), [
      'https://gx-10.example.ts.net/*',
    ]);
  });

  it('requests nothing for other origins or bad URLs', () => {
    for (const url of [
      'http://gx-10.example.ts.net',
      'http://localhost:8000',
      'https://app.up.railway.app',
      'https://evil-ts.net',
      'https://ts.net.evil.com',
      'not a url',
      '',
    ]) {
      assert.deepEqual(apiPermissionOrigins(url), [], url);
    }
  });
});

describe('requestApiAccess', () => {
  it('calls chrome.permissions.request synchronously (user gesture)', async () => {
    const seen = [];
    const permissions = {
      request(details) {
        seen.push(details);
        return Promise.resolve(true);
      },
    };
    const pending = requestApiAccess(CONFIG.apiUrl, permissions);
    assert.deepEqual(seen, [{ origins: ['https://gx-10.example.ts.net/*'] }]);
    assert.equal(await pending, 'granted');
  });

  it('reports denied, error and not-needed', async () => {
    assert.equal(await requestApiAccess(CONFIG.apiUrl, { request: async () => false }), 'denied');
    assert.equal(
      await requestApiAccess(CONFIG.apiUrl, {
        request: async () => {
          throw new Error('not allowed');
        },
      }),
      'error',
    );
    let called = false;
    const permissions = {
      request: async () => {
        called = true;
        return true;
      },
    };
    assert.equal(await requestApiAccess('http://localhost:8000', permissions), 'not-needed');
    assert.equal(called, false);
  });
});

describe('describeSyncResult', () => {
  const cases = [
    [200, { site: 'x', keys_written: [], saved_at: '2026-09-24T10:00:00Z' }, null, true, /Synced X session/],
    [422, { code: 'session_invalid' }, null, false, /log in to X again in this browser/],
    [422, { code: 'validation_error' }, null, false, /rejected the X cookies \(validation_error\)/],
    [401, { code: 'unauthorized' }, null, false, /API key/],
    [403, {}, null, false, /API key rejected/],
    [429, {}, '120', false, /retry in 120s/],
    [429, {}, null, false, /retry in a few minutes/],
    [502, { code: 'session_validation_unavailable' }, null, false, /X could not be reached.*retry later/],
    [502, { code: 'openbao_write_failed' }, null, false, /OpenBao refused the write.*retry later/],
    [502, null, null, false, /retry later/],
    [503, { code: 'openbao_not_configured' }, null, false, /no OpenBao configured/],
    [503, null, null, false, /retry later/],
    [404, null, null, false, /endpoint not found/],
    [0, null, null, false, /redirected/],
    [500, { code: 'internal_error' }, null, false, /HTTP 500, internal_error/],
  ];
  for (const [status, body, retryAfter, ok, pattern] of cases) {
    it(`maps ${status} ${body?.code ?? ''}`, () => {
      const result = describeSyncResult('x', { status, body, retryAfter });
      assert.equal(result.ok, ok);
      assert.match(result.message, pattern);
    });
  }

  it('includes saved_at on success', () => {
    const result = describeSyncResult('substack', {
      status: 200,
      body: { saved_at: '2026-09-24T10:00:00Z' },
    });
    const expected = new Date('2026-09-24T10:00:00Z').toLocaleString();
    assert.ok(result.message.includes(expected), result.message);
  });

  it('never echoes server text: a non-code string is dropped', () => {
    const result = describeSyncResult('x', {
      status: 500,
      body: { code: `leak ${AUTH}`, detail: AUTH },
    });
    assertNoSecret(result.message);
    assert.equal(result.message, 'X sync failed (HTTP 500).');
  });

  it('ignores a non-numeric Retry-After', () => {
    const result = describeSyncResult('x', { status: 429, body: null, retryAfter: 'soon' });
    assert.match(result.message, /a few minutes/);
  });
});

describe('sessionSyncEndpoint', () => {
  it('builds the per-site PUT URL, tolerating a trailing slash', () => {
    assert.equal(
      sessionSyncEndpoint('https://gx-10.example.ts.net/', 'x'),
      'https://gx-10.example.ts.net/api/v1/browser-sessions/x',
    );
    assert.equal(
      sessionSyncEndpoint('https://gx-10.example.ts.net', 'substack'),
      'https://gx-10.example.ts.net/api/v1/browser-sessions/substack',
    );
  });
});

describe('syncSession', () => {
  it('PUTs the X pair with the admin key and exact fields', async () => {
    const fetch = fakeFetch(
      jsonResponse(200, { site: 'x', keys_written: ['X_AUTH_TOKEN'], saved_at: '2026-09-24T10:00:00Z' }),
    );
    const result = await syncSession('x', CONFIG, { cookies: fakeCookies(FULL_JAR), fetch });

    assert.equal(result.ok, true);
    assert.equal(fetch.calls.length, 1);
    const { url, init } = fetch.calls[0];
    assert.equal(url, 'https://gx-10.example.ts.net/api/v1/browser-sessions/x');
    assert.equal(init.method, 'PUT');
    assert.equal(init.headers['X-Admin-Key'], 'admin-key');
    assert.equal(init.headers['Content-Type'], 'application/json');
    assert.equal(init.credentials, 'omit');
    assert.equal(init.redirect, 'manual');
    assert.deepEqual(JSON.parse(init.body), { auth_token: AUTH, ct0: CT0 });
    assertNoSecret(result.message);
  });

  it('PUTs substack_sid only', async () => {
    const fetch = fakeFetch(jsonResponse(200, { saved_at: '2026-09-24T10:00:00Z' }));
    await syncSession('substack', CONFIG, { cookies: fakeCookies(FULL_JAR), fetch });
    assert.equal(fetch.calls[0].url, 'https://gx-10.example.ts.net/api/v1/browser-sessions/substack');
    assert.deepEqual(JSON.parse(fetch.calls[0].init.body), { substack_sid: SID });
  });

  it('does not call the API when not logged in', async () => {
    const fetch = fakeFetch(jsonResponse(200, {}));
    const result = await syncSession('x', CONFIG, {
      cookies: fakeCookies({ 'https://x.com|ct0': CT0 }),
      fetch,
    });
    assert.equal(result.ok, false);
    assert.equal(result.message, 'Not logged in to X in this browser. Log in, then sync again.');
    assert.equal(fetch.calls.length, 0);
  });

  it('reads no cookie and sends nothing without an API key', async () => {
    const cookies = fakeCookies(FULL_JAR);
    const fetch = fakeFetch(jsonResponse(200, {}));
    const result = await syncSession('substack', { apiUrl: CONFIG.apiUrl, apiKey: '' }, { cookies, fetch });
    assert.equal(result.ok, false);
    assert.match(result.message, /No API key configured/);
    assert.equal(cookies.calls.length, 0);
    assert.equal(fetch.calls.length, 0);
  });

  it('refuses to send cookies over plain http to a non-loopback host', async () => {
    const cookies = fakeCookies(FULL_JAR);
    const fetch = fakeFetch(jsonResponse(200, {}));
    const result = await syncSession('x', { apiUrl: 'http://gx-10.example.ts.net', apiKey: 'k' }, { cookies, fetch });
    assert.match(result.message, /needs an https:\/\/ API URL/);
    assert.equal(cookies.calls.length, 0);
    assert.equal(fetch.calls.length, 0);
  });

  it('allows http on loopback for local development', () => {
    assert.equal(isSecureApiUrl('http://localhost:8000'), true);
    assert.equal(isSecureApiUrl('http://127.0.0.1:8000'), true);
    assert.equal(isSecureApiUrl('https://app.up.railway.app'), true);
    assert.equal(isSecureApiUrl('http://192.168.1.10:8000'), false);
    assert.equal(isSecureApiUrl('http://localhost.evil.com'), false);
    assert.equal(isSecureApiUrl('not a url'), false);
  });

  it('requires an API URL', async () => {
    const fetch = fakeFetch(jsonResponse(200, {}));
    const result = await syncSession('x', { apiUrl: '', apiKey: 'k' }, { cookies: fakeCookies(FULL_JAR), fetch });
    assert.match(result.message, /No API URL configured/);
    assert.equal(fetch.calls.length, 0);
  });

  it('reports a cookie API failure without calling the API', async () => {
    const fetch = fakeFetch(jsonResponse(200, {}));
    const cookies = {
      get: async () => {
        throw new Error('No host permissions for cookies at url');
      },
    };
    const result = await syncSession('x', CONFIG, { cookies, fetch });
    assert.match(result.message, /Could not read X cookies/);
    assert.equal(fetch.calls.length, 0);
  });

  it('maps a network failure, naming a missing grant', async () => {
    const fetch = fakeFetch(new TypeError('Failed to fetch'));
    const plain = await syncSession('x', CONFIG, { cookies: fakeCookies(FULL_JAR), fetch });
    assert.match(plain.message, /Could not reach the API at https:\/\/gx-10\.example\.ts\.net/);
    assert.doesNotMatch(plain.message, /not granted/);

    const denied = await syncSession('x', CONFIG, {
      cookies: fakeCookies(FULL_JAR),
      fetch,
      access: 'denied',
    });
    assert.match(denied.message, /Access to gx-10\.example\.ts\.net was not granted/);
  });

  it('survives a non-JSON error body', async () => {
    const fetch = fakeFetch(jsonResponse(502, undefined));
    const result = await syncSession('substack', CONFIG, { cookies: fakeCookies(FULL_JAR), fetch });
    assert.equal(result.ok, false);
    assert.match(result.message, /retry later/);
  });

  it('never puts a cookie value in any message', async () => {
    const statuses = [200, 401, 403, 404, 413, 422, 429, 500, 502, 503];
    for (const site of Object.keys(SITES)) {
      for (const status of statuses) {
        const fetch = fakeFetch(
          jsonResponse(status, { code: 'session_invalid', detail: SECRETS.join(' '), saved_at: SID }, {
            'Retry-After': AUTH,
          }),
        );
        const result = await syncSession(site, CONFIG, { cookies: fakeCookies(FULL_JAR), fetch });
        assertNoSecret(result.message);
      }
    }
  });
});

describe('source hygiene', () => {
  const read = (name) => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');

  it('never logs or stores cookie values', () => {
    for (const name of ['session_sync.js', 'popup.js', 'options.js']) {
      const source = read(name);
      assert.doesNotMatch(source, /console\.(log|info|debug|warn|error)/, name);
      assert.doesNotMatch(source, /\beval\s*\(|new Function\s*\(/, name);
    }
    const sync = read('session_sync.js');
    assert.doesNotMatch(sync, /chrome\.storage\.(sync|local|session|managed)/);
  });
});

describe('manifest', () => {
  const read = (name) => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
  const manifest = JSON.parse(read('manifest.json'));

  it('is MV3 with cookie access for substack.com and x.com only', () => {
    assert.equal(manifest.manifest_version, 3);
    assert.ok(manifest.permissions.includes('cookies'));
    // The URL-save feature keeps its permissions.
    for (const permission of ['activeTab', 'scripting', 'storage']) {
      assert.ok(manifest.permissions.includes(permission), permission);
    }
    assert.deepEqual(manifest.host_permissions, ['https://substack.com/*', 'https://x.com/*']);
    assert.deepEqual(manifest.optional_host_permissions, ['https://*.ts.net/*']);
  });

  it('matches the origins the sync code reads', () => {
    for (const site of Object.values(SITES)) {
      assert.ok(manifest.host_permissions.includes(`${site.cookieUrl}/*`), site.cookieUrl);
    }
  });

  it('loads no remote code and relaxes no CSP', () => {
    assert.equal(manifest.content_security_policy, undefined);
    assert.equal(manifest.background, undefined);
    for (const page of ['popup.html', 'options.html']) {
      const scripts = [...read(page).matchAll(/<script\b[^>]*>/g)].map((m) => m[0]);
      assert.ok(scripts.length > 0, page);
      for (const tag of scripts) {
        assert.match(tag, /\ssrc="[a-z_]+\.js"/, `${page}: ${tag}`);
      }
    }
  });
});
