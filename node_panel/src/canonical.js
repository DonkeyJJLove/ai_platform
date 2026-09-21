'use strict';
const crypto = require('node:crypto');
function canonicalize(value) {
  if (value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(canonicalize);
  const out = {};
  for (const key of Object.keys(value).sort()) out[key] = canonicalize(value[key]);
  return out;
}
function canonicalJson(value) { return JSON.stringify(canonicalize(value)); }
function sha256(value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(typeof value === 'string' ? value : canonicalJson(value), 'utf8');
  return crypto.createHash('sha256').update(bytes).digest('hex');
}
function id(prefix = '') { return prefix + crypto.randomUUID().replaceAll('-', ''); }
function nowIso() { return new Date().toISOString(); }
module.exports = { canonicalize, canonicalJson, sha256, id, nowIso };
