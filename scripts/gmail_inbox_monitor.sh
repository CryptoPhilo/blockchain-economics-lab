#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[DEPRECATED] scripts/gmail_inbox_monitor.sh is a compatibility shim. Use ./run_gmail_inbox_monitor.sh for all new automation and operator runbooks." >&2
exec "${ROOT_DIR}/run_gmail_inbox_monitor.sh" "$@"
