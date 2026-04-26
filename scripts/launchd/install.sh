#!/bin/bash
# Install/refresh the BCE Gmail Inbox Monitor launchd job for the current user.
# Renders the template plist with absolute paths, copies it into ~/Library/LaunchAgents,
# and (re)loads it via launchctl.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

LABEL="com.bce.gmail-monitor"
TEMPLATE="${SCRIPT_DIR}/${LABEL}.plist"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET="${TARGET_DIR}/${LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs/bce-gmail-monitor"
ENV_FILE="${HOME}/.bce/gmail-monitor.env"

mkdir -p "${TARGET_DIR}" "${LOG_DIR}" "$(dirname "${ENV_FILE}")"

if [[ ! -f "${ENV_FILE}" ]]; then
    cat <<EOF >&2
[install] WARNING: env file ${ENV_FILE} not found.
Create it before the first scheduled run, e.g.:

  install -m 0600 /dev/null ${ENV_FILE}
  cat >> ${ENV_FILE} <<'ENV'
PAPERCLIP_API_URL="http://127.0.0.1:3100"
PAPERCLIP_API_KEY="<board key>"
PAPERCLIP_COMPANY_ID="<bce company id>"
PAPERCLIP_AGENT_ID="<gmail monitor agent id>"
GMAIL_CLIENT_ID="<oauth client id>"
GMAIL_CLIENT_SECRET="<oauth client secret>"
GMAIL_REFRESH_TOKEN="<refresh token>"
ENV

EOF
fi

ESCAPED_REPO_ROOT="$(printf '%s' "${REPO_ROOT}" | sed -e 's/[\\/&]/\\&/g')"
ESCAPED_LOG_DIR="$(printf '%s' "${LOG_DIR}" | sed -e 's/[\\/&]/\\&/g')"

sed \
    -e "s|__REPO_ROOT__|${ESCAPED_REPO_ROOT}|g" \
    -e "s|__LOG_DIR__|${ESCAPED_LOG_DIR}|g" \
    "${TEMPLATE}" > "${TARGET}.tmp"
mv "${TARGET}.tmp" "${TARGET}"
chmod 0644 "${TARGET}"

if launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)" "${TARGET}" || true
fi
launchctl bootstrap "gui/$(id -u)" "${TARGET}"
launchctl enable "gui/$(id -u)/${LABEL}"

echo "[install] loaded ${LABEL} → ${TARGET}"
echo "[install] logs: ${LOG_DIR}"
echo "[install] manual fire: launchctl kickstart -k gui/$(id -u)/${LABEL}"
