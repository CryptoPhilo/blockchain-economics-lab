#!/bin/bash
# Remove the BCE Gmail Inbox Monitor launchd job for the current user.

set -euo pipefail

LABEL="com.bce.gmail-monitor"
TARGET="${HOME}/Library/LaunchAgents/${LABEL}.plist"

if launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)" "${TARGET}" || true
fi

if [[ -f "${TARGET}" ]]; then
    rm -f "${TARGET}"
    echo "[uninstall] removed ${TARGET}"
else
    echo "[uninstall] no plist at ${TARGET}; nothing to remove"
fi
