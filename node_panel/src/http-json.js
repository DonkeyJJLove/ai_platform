'use strict';
async function jsonRequest(base, path, {method='GET', body, headers={}, timeoutMs=8000} = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(base.replace(/\/$/, '') + path, {
      method,
      headers: {'accept':'application/json', ...(body === undefined ? {} : {'content-type':'application/json'}), ...headers},
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await response.text();
    let value = {};
    if (text) {
      try { value = JSON.parse(text); }
      catch { throw new Error(`NON_JSON_RESPONSE:${response.status}`); }
    }
    if (!response.ok) {
      const detail = value && (value.error || value.message);
      const error = new Error(`HTTP_${response.status}:${String(detail || 'request rejected').slice(0,400)}`);
      error.status = response.status;
      error.payload = value;
      throw error;
    }
    return value;
  } finally { clearTimeout(timer); }
}
async function health(base, path='/health', headers={}) {
  try { const v = await jsonRequest(base, path, {headers, timeoutMs:1500}); return v.ok === true || v.status === 'ok' || v.status === 'PASS' || v.status === 'LISTENING'; }
  catch { return false; }
}
module.exports = { jsonRequest, health };
