#!/usr/bin/env bash
# ==============================================================================
# macOS Spotlight for Linux - Universal 1-Command Installer
# Works on Arch/CachyOS/Manjaro, Ubuntu/Debian/Mint/Pop!_OS, Fedora, and openSUSE.
# ==============================================================================
set -euo pipefail

# Visual formatting
BOLD="$(tput bold 2>/dev/null || printf '')"
GREEN="$(tput setaf 2 2>/dev/null || printf '')"
BLUE="$(tput setaf 4 2>/dev/null || printf '')"
YELLOW="$(tput setaf 3 2>/dev/null || printf '')"
RED="$(tput setaf 1 2>/dev/null || printf '')"
RESET="$(tput sgr0 2>/dev/null || printf '')"

log_info()    { printf "${BLUE}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }
log_success() { printf "${GREEN}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }
log_warn()    { printf "${YELLOW}==> WARNING:${RESET} %s\n" "$*"; }
log_error()   { printf "${RED}==> ERROR:${RESET} %s\n" "$*" >&2; }

# Target installation directories
INSTALL_DIR="${HOME}/.local/share/macos-spotlight"
BIN_DIR="${HOME}/.local/bin"
AUTOSTART_DIR="${HOME}/.config/autostart"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

REPO_URL="https://github.com/BestFortune/macos-spotlight"
BRANCH="main"

printf "\n${BOLD}${BLUE}"
cat << "EOF"
  __  __         ___  ___   ____             _   _ _       _     _   
 |  \/  | __ _  / _ \/ ___| / ___| _ __   ___| |_| (_) __ _| |__ | |_ 
 | |\/| |/ _` | | | |\___ \| |  _| '_ \ / _ \ __| | |/ _` | '_ \| __|
 | |  | | (_| | |_| | ___) | |_| | |_) | (_) | |_| | | (_| | | | | |_ 
 |_|  |_|\__,_|  \___/|____/ \____| .__/ \___/ \__|_|_|\__, |_| |_|\__|
                                  |_|                  |___/           
EOF
printf "${RESET}\n"
log_info "Installing macOS Spotlight Search for Linux..."

# Ensure ~/.local/bin is in PATH for this script session
export PATH="${BIN_DIR}:${PATH}"

# 1. Detect Package Manager and Install Dependencies
detect_and_install_deps() {
    log_info "Checking and installing required system dependencies..."

    local MISSING_DEPS=()

    # Commands needed
    for cmd in python3 gcc curl git; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            MISSING_DEPS+=("$cmd")
        fi
    done

    # Check python gi and keybinder
    local NEED_GI=0
    local NEED_KEYBINDER=0
    if ! python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" >/dev/null 2>&1; then
        NEED_GI=1
    fi
    if ! python3 -c "import gi; gi.require_version('Keybinder', '3.0'); from gi.repository import Keybinder" >/dev/null 2>&1; then
        NEED_KEYBINDER=1
    fi

    if [ ${#MISSING_DEPS[@]} -eq 0 ] && [ "$NEED_GI" -eq 0 ] && [ "$NEED_KEYBINDER" -eq 0 ]; then
        log_success "All dependencies are already satisfied!"
        return 0
    fi

    log_info "Installing missing dependencies (sudo access may be requested)..."

    if command -v pacman >/dev/null 2>&1; then
        # Arch / CachyOS / Manjaro
        sudo pacman -Sy --noconfirm --needed python python-gobject gtk3 libkeybinder3 gcc git curl xdotool || true
    elif command -v apt-get >/dev/null 2>&1; then
        # Ubuntu / Debian / Mint / Pop!_OS
        sudo apt-get update -y
        sudo apt-get install -y python3 python3-gi gir1.2-gtk-3.0 gir1.2-keybinder-3.0 libkeybinder-3.0-0 gcc git curl xdotool
    elif command -v dnf >/dev/null 2>&1; then
        # Fedora / RHEL
        sudo dnf install -y python3 python3-gobject gtk3 keybinder3 gcc git curl xdotool
    elif command -v zypper >/dev/null 2>&1; then
        # openSUSE
        sudo zypper install -y python3 python3-gobject python3-gobject-Gdk typelib-1_0-Gtk-3_0 typelib-1_0-Keybinder-3_0 keybinder3 gcc git curl xdotool
    else
        log_warn "Unknown package manager. Please ensure python3, gobject-introspection, gtk3, and keybinder-3.0 are installed."
    fi
}

# 2. Setup Files and Directories
setup_files() {
    log_info "Setting up directories and files..."
    mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${AUTOSTART_DIR}" "${SYSTEMD_USER_DIR}"

    # Determine if running from existing cloned repo or downloaded via curl
    local SCRIPT_SOURCE_DIR
    SCRIPT_SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

    if [ -n "$SCRIPT_SOURCE_DIR" ] && [ -f "${SCRIPT_SOURCE_DIR}/daemon.py" ]; then
        log_info "Installing from local repository files: ${SCRIPT_SOURCE_DIR}"
        cp -r "${SCRIPT_SOURCE_DIR}"/* "${INSTALL_DIR}/"
    else
        log_info "Fetching latest release files from GitHub..."
        local TEMP_DIR
        TEMP_DIR="$(mktemp -d)"
        git clone --depth=1 "https://github.com/BestFortune/macos-spotlight.git" "${TEMP_DIR}"
        cp -r "${TEMP_DIR}"/* "${INSTALL_DIR}/"
        rm -rf "${TEMP_DIR}"
    fi

    # 3. Compile the ultra-fast C toggle binary
    log_info "Compiling ultra-fast C toggle binary (O3 optimized)..."
    gcc -O3 "${INSTALL_DIR}/spotlight-toggle.c" -o "${INSTALL_DIR}/spotlight-toggle"
    cp "${INSTALL_DIR}/spotlight-toggle" "${BIN_DIR}/spotlight-toggle"
    chmod +x "${BIN_DIR}/spotlight-toggle"

    # Also symlink / install rofi-spotlight alias for backward compatibility
    cp "${INSTALL_DIR}/spotlight-toggle" "${BIN_DIR}/rofi-spotlight" || true
    chmod +x "${BIN_DIR}/rofi-spotlight" || true

    # 4. Install spotlight-daemon launcher script
    cat << 'EOF' > "${BIN_DIR}/spotlight-daemon"
#!/usr/bin/env bash
# macOS Spotlight Search Daemon Launcher with dynamic display detection

if [ -z "$DISPLAY" ]; then
    for s in /tmp/.X11-unix/X*; do
        if [ -S "$s" ]; then
            DISPLAY=":${s##*/X}"
            break
        fi
    done
    export DISPLAY="${DISPLAY:-:1}"
fi

if [ -z "$XAUTHORITY" ]; then
    if [ -f "/run/user/${UID}/lyxauth" ]; then
        export XAUTHORITY="/run/user/${UID}/lyxauth"
    elif [ -f "${HOME}/.Xauthority" ]; then
        export XAUTHORITY="${HOME}/.Xauthority"
    fi
fi

exec /usr/bin/env python3 "${HOME}/.local/share/macos-spotlight/daemon.py" "$@"
EOF
    chmod +x "${BIN_DIR}/spotlight-daemon"
}

# 5. Configure Desktop Environment Keybindings
configure_keybindings() {
    log_info "Configuring Alt+Space global hotkey and unblocking window manager conflicts..."

    # A. Cinnamon Desktop
    if command -v gsettings >/dev/null 2>&1; then
        # 1. Unbind Alt+Space from Cinnamon activate-window-menu
        gsettings set org.cinnamon.desktop.keybindings.wm activate-window-menu "[]" 2>/dev/null || true
        # 2. Unbind from GNOME window menu
        gsettings set org.gnome.desktop.wm.keybindings activate-window-menu "[]" 2>/dev/null || true
        # 3. Unbind from MATE Marco window menu
        gsettings set org.mate.Marco.window-keybindings activate-window-menu "''" 2>/dev/null || true

        # 4. Add custom shortcut to Cinnamon
        if gsettings list-schemas | grep -q "org.cinnamon.desktop.keybindings"; then
            local EXISTING_LIST
            EXISTING_LIST="$(gsettings get org.cinnamon.desktop.keybindings custom-list 2>/dev/null || echo '[]')"
            if [[ "$EXISTING_LIST" != *"custom_spotlight"* ]] && [[ "$EXISTING_LIST" != *"custom0"* ]]; then
                gsettings set org.cinnamon.desktop.keybindings custom-list "['custom_spotlight']" 2>/dev/null || true
                gsettings set org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/custom_spotlight/ name "macOS Spotlight" 2>/dev/null || true
                gsettings set org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/custom_spotlight/ command "${BIN_DIR}/spotlight-toggle" 2>/dev/null || true
                gsettings set org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/custom_spotlight/ binding "['<Alt>space']" 2>/dev/null || true
            else
                # Update existing custom binding
                local TARGET_CUSTOM="custom0"
                if [[ "$EXISTING_LIST" == *"custom_spotlight"* ]]; then
                    TARGET_CUSTOM="custom_spotlight"
                fi
                gsettings set "org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/${TARGET_CUSTOM}/" name "macOS Spotlight" 2>/dev/null || true
                gsettings set "org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/${TARGET_CUSTOM}/" command "${BIN_DIR}/spotlight-toggle" 2>/dev/null || true
                gsettings set "org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/${TARGET_CUSTOM}/" binding "['<Alt>space']" 2>/dev/null || true
            fi
        fi

        # 5. GNOME Shell Custom Shortcut
        if gsettings list-schemas | grep -q "org.gnome.settings-daemon.plugins.media-keys"; then
            local GNOME_LIST
            GNOME_LIST="$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo '[]')"
            if [[ "$GNOME_LIST" != *"spotlight"* ]]; then
                gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/spotlight/']" 2>/dev/null || true
                gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/spotlight/ name "macOS Spotlight" 2>/dev/null || true
                gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/spotlight/ command "${BIN_DIR}/spotlight-toggle" 2>/dev/null || true
                gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/spotlight/ binding "<Alt>space" 2>/dev/null || true
            fi
        fi
    fi

    # XFCE shortcuts
    if command -v xfconf-query >/dev/null 2>&1; then
        xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Alt>space" -n -t string -s "${BIN_DIR}/spotlight-toggle" 2>/dev/null || true
    fi
}

# 6. Setup Autostart and Systemd Service
setup_services() {
    log_info "Setting up autostart across system restarts..."

    # A. XDG Autostart Desktop Entry
    cat << EOF > "${AUTOSTART_DIR}/spotlight.desktop"
[Desktop Entry]
Type=Application
Name=macOS Spotlight
Comment=Instant macOS Spotlight Search Daemon
Exec=${BIN_DIR}/spotlight-daemon
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-Cinnamon-Autostart-enabled=true
StartupNotify=false
Terminal=false
EOF
    chmod +x "${AUTOSTART_DIR}/spotlight.desktop"

    # B. Systemd User Service
    cat << EOF > "${SYSTEMD_USER_DIR}/spotlight.service"
[Unit]
Description=macOS Spotlight Search Daemon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=${BIN_DIR}/spotlight-daemon
Restart=always
RestartSec=1
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=graphical-session.target default.target
EOF

    # Enable and start service
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload 2>/dev/null || true
        systemctl --user enable spotlight.service 2>/dev/null || true
        systemctl --user restart spotlight.service 2>/dev/null || true
        log_success "Systemd user service enabled and started!"
    else
        # Fallback manual spawn
        "${BIN_DIR}/spotlight-daemon" >/dev/null 2>&1 &
    fi
}

# Ensure PATH is updated in shell rc files if ~/.local/bin is missing
ensure_path() {
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        for rc in "${HOME}/.bashrc" "${HOME}/.zshrc" "${HOME}/.config/fish/config.fish"; do
            if [ -f "$rc" ]; then
                if ! grep -q "\.local/bin" "$rc"; then
                    if [[ "$rc" == *.fish ]]; then
                        echo 'set -gx PATH "$HOME/.local/bin" $PATH' >> "$rc"
                    else
                        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
                    fi
                fi
            fi
        done
    fi
}

# Main Execution Flow
main() {
    detect_and_install_deps
    setup_files
    configure_keybindings
    setup_services
    ensure_path

    printf "\n"
    log_success "macOS Spotlight has been successfully installed and activated!"
    printf "\n"
    printf "  ${BOLD}Press ${BLUE}Alt + Space${RESET} ${BOLD}anytime to open Spotlight!${RESET}\n"
    printf "  ${BOLD}It will automatically launch and remain active after every restart.${RESET}\n\n"
}

main "$@"
