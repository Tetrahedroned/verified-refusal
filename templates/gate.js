// Drop-in JavaScript/TypeScript verified-refusal gate.
//
// Works in Node.js (18+) and browser.
// Exposes both a decorator-like wrapper and an inline gate.
//
// Env (Node): VERIFIED_REFUSAL_MODE=1 activates, VERIFIED_REFUSAL_OVERRIDE=1 bypasses.
// In browser: set globalThis.VERIFIED_REFUSAL_MODE / OVERRIDE instead.

const _isNode = typeof process !== 'undefined' && !!process.versions && !!process.versions.node;

function _envFlag(name) {
  if (_isNode) return process.env[name] === '1';
  if (typeof globalThis !== 'undefined' && globalThis[name] !== undefined) {
    return String(globalThis[name]) === '1';
  }
  return false;
}

function _active() { return _envFlag('VERIFIED_REFUSAL_MODE'); }
function _overridden() { return _envFlag('VERIFIED_REFUSAL_OVERRIDE'); }

function _logPath() {
  if (!_isNode) return null;
  const os = require('os');
  const path = require('path');
  return process.env.OPENCLAW_VR_LOG || path.join(os.homedir(), '.openclaw', 'vr_log.jsonl');
}

function _appendLog(entry) {
  if (!_isNode) return;
  try {
    const fs = require('fs');
    const path = require('path');
    const p = _logPath();
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.appendFileSync(p, JSON.stringify(entry) + '\n', 'utf8');
  } catch (_err) { /* never crash the host */ }
}

function _now() { return new Date().toISOString(); }

function _report(opts) {
  return {
    mode: 'verified_refusal',
    timestamp: _now(),
    function: opts.function || '<anon>',
    file: opts.file || null,
    classification: opts.category ? 'irreversible' : 'uncertain',
    confidence: opts.confidence ?? 0.9,
    category: opts.category || null,
    gates_passed: opts.gates_passed || [],
    gates_failed: opts.gates_failed || [],
    would_have_executed: !!opts.would_have_executed,
    consequence: opts.consequence || null,
    override_used: !!opts.override_used,
    confirmed: !!opts.confirmed,
    report_path: _logPath(),
  };
}

async function _runChecks(checks) {
  const passed = [], failed = [];
  if (!checks) return { passed, failed };
  for (let i = 0; i < checks.length; i++) {
    const c = checks[i];
    try {
      const r = await c();
      if (Array.isArray(r)) {
        (r[0] ? passed : failed).push(r[1] || `check_${i}`);
      } else {
        (r ? passed : failed).push(`check_${i}`);
      }
    } catch (e) {
      failed.push(`check_${i}:error:${e && e.message || e}`);
    }
  }
  return { passed, failed };
}

/**
 * Inline gate. Returns a report if execution should be blocked, else null.
 * Always returns a Promise so async checks are supported uniformly.
 */
async function vrGate(opts = {}) {
  const { passed, failed } = await _runChecks(opts.checks);
  const base = {
    function: opts.function,
    file: opts.file,
    category: opts.category || 'external_api_side_effect',
    confidence: opts.confidence ?? 0.9,
    consequence: opts.consequence || 'irreversible action',
    gates_passed: passed,
    gates_failed: failed,
  };
  if (_overridden()) {
    const r = _report({ ...base, would_have_executed: true, override_used: true });
    _appendLog(r);
    if (opts.emit !== false && _isNode) process.stderr.write(JSON.stringify(r) + '\n');
    return null;
  }
  if (!_active()) return null;
  const r = _report({ ...base, would_have_executed: failed.length === 0, override_used: false });
  _appendLog(r);
  if (opts.emit !== false) (_isNode ? process.stdout : console).write?.(JSON.stringify(r) + '\n') ?? console.log(JSON.stringify(r));
  return r;
}

/**
 * Wrapper. vrProtect({...opts})(fn) returns a function that gates before calling fn.
 * Works for sync and async target functions.
 */
function vrProtect(opts = {}) {
  return function wrap(fn) {
    const name = opts.function || fn.name || '<anon>';
    return async function gated(...args) {
      const report = await vrGate({ ...opts, function: name });
      if (report !== null) return report;
      return fn.apply(this, args);
    };
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { vrGate, vrProtect };
}
if (typeof globalThis !== 'undefined') {
  globalThis.vrGate = vrGate;
  globalThis.vrProtect = vrProtect;
}
