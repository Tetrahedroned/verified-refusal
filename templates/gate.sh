#!/usr/bin/env bash
# Drop-in bash verified-refusal gate.
#
# Source this file and call vr_gate inside any function that performs an
# irreversible action.
#
# Env: VERIFIED_REFUSAL_MODE=1 activates; VERIFIED_REFUSAL_OVERRIDE=1 bypasses.
# Log path: VR_LOG_PATH (canonical) > OPENCLAW_VR_LOG (deprecated alias)
#         > ${VR_DATA_DIR:-$HOME/.vr}/vr_log.jsonl

_vr_log_path() {
  if [ -n "${VR_LOG_PATH:-}" ]; then
    printf '%s' "$VR_LOG_PATH"
  elif [ -n "${OPENCLAW_VR_LOG:-}" ]; then
    printf '%s' "$OPENCLAW_VR_LOG"
  else
    printf '%s' "${VR_DATA_DIR:-$HOME/.vr}/vr_log.jsonl"
  fi
}

_vr_append_log() {
  local path
  path="$(_vr_log_path)"
  mkdir -p "$(dirname "$path")" 2>/dev/null || return 0
  printf '%s\n' "$1" >> "$path" 2>/dev/null || true
}

_vr_now() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat())'
  else
    date -u +"%Y-%m-%dT%H:%M:%SZ"
  fi
}

# vr_gate "function_name" "category" "consequence"
# Exit 0 = proceed. Exit 10 = blocked (caller should return/exit).
vr_gate() {
  local fn="${1:-$FUNCNAME}" category="${2:-external_api_side_effect}" consequence="${3:-irreversible action}"
  local ts
  ts="$(_vr_now)"
  local override="false" blocked="false"

  if [ "${VERIFIED_REFUSAL_OVERRIDE:-0}" = "1" ]; then
    override="true"
  elif [ "${VERIFIED_REFUSAL_MODE:-0}" = "1" ]; then
    blocked="true"
  fi

  if [ "$override" = "true" ] || [ "$blocked" = "true" ]; then
    local payload
    payload=$(printf '{"mode":"verified_refusal","timestamp":"%s","function":"%s","file":"%s","classification":"irreversible","confidence":0.9,"category":"%s","gates_passed":[],"gates_failed":[],"would_have_executed":true,"consequence":"%s","override_used":%s,"confirmed":false,"report_path":"%s"}' \
      "$ts" "$fn" "${BASH_SOURCE[1]:-<stdin>}" "$category" "$consequence" "$override" "$(_vr_log_path)")
    _vr_append_log "$payload"
    if [ "$blocked" = "true" ]; then
      printf '%s\n' "$payload"
      return 10
    else
      printf '%s\n' "$payload" >&2
      return 0
    fi
  fi
  return 0
}

export -f vr_gate _vr_append_log _vr_log_path _vr_now 2>/dev/null || true
