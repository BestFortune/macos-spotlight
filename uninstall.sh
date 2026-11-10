#!/usr/bin/env bash
# ==============================================================================
# macOS Spotlight for Linux - Clean Uninstaller
# ==============================================================================
set -euo pipefail

BOLD="$(tput bold 2>/dev/null || printf '')"
GREEN="$(tput setaf 2 2>/dev/null || printf '')"
BLUE="$(tput setaf 4 2>/dev/null || printf '')"
RESET="$(tput sgr0 2>/dev/null || printf '')"

log_info()    { printf "${BLUE}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }
log_success() { printf "${GREEN}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }

log_info "Stopping and removing macOS Spotlight..."

# 1. Stop and disable systemd service
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop spotlight.service 2>/dev/null || true
    systemctl --user disable spotlight.service 2>/dev/null || true
    rm -f "${HOME}/.config/systemd/user/spotlight.service"
    systemctl --user daemon-reload 2>/dev/null || true
fi

# 2. Kill any running daemon
pkill -f "daemon.py" 2>/dev/null || true

# 3. Remove autostart entry
rm -f "${HOME}/.config/autostart/spotlight.desktop"

# 4. Remove installed files and binaries
rm -rf "${HOME}/.local/share/macos-spotlight"
rm -f "${HOME}/.local/bin/spotlight-daemon"
rm -f "${HOME}/.local/bin/spotlight-toggle"
rm -f "${HOME}/.cache/spotlight.sock"

# 5. Restore window menu shortcut in Cinnamon if desired
if command -v gsettings >/dev/null 2>&1; then
    gsettings set org.cinnamon.desktop.keybindings.wm activate-window-menu "['<Alt>space']" 2>/dev/null || true
fi

log_success "macOS Spotlight has been cleanly uninstalled."
