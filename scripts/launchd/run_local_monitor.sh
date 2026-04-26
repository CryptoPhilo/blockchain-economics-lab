#!/bin/bash
# Local launchd entrypoint for the BCE Gmail Inbox Monitor.
# Sources operator-provided secrets, then executes the canonical wrapper.
#
# Required env file (default: ~/.bce/gmail-monitor.env), shell-source format:
#   PAPERCLIP_API_URL="http://127.0.0.1:3100"
#   PAPERCLIP_API_KEY="..."
#   PAPERCLIP_COMPANY_ID="..."
#   PAPERCLIP_AGENT_ID="..."
#   GMAIL_CLIENT_ID="..."
#   GMAIL_CLIENT_SECRET="..."
#   GMAIL_REFRESH_TOKEN="..."
# Optional overrides match GMAIL_MONITORING.md.

set -euo pipefail

REPO_ROOT="${BCE_REPO_ROOT:-/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab}"
ENV_FILE="${BCE_GMAIL_MONITOR_ENV:-${HOME}/.bce/gmail-monitor.env}"
LOG_DIR="${BCE_GMAIL_MONITOR_LOG_DIR:-${HOME}/Library/Logs/bce-gmail-monitor}"

mkdir -p "${LOG_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: env file not found: ${ENV_FILE}" >&2
    echo "Create it with the secrets listed in GMAIL_MONITORING.md → 'launchd 설치'." >&2
    exit 78
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

export PAPERCLIP_RUN_ID="${PAPERCLIP_RUN_ID:-launchd-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
export GMAIL_SINCE_HOURS="${GMAIL_SINCE_HOURS:-0.5}"

cd "${REPO_ROOT}"

./run_gmail_inbox_monitor.sh --preflight --since-hours "${GMAIL_SINCE_HOURS}"
./run_gmail_inbox_monitor.sh --since-hours "${GMAIL_SINCE_HOURS}"
