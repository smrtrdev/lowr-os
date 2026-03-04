#!/usr/bin/env bash
set -euo pipefail
source "$SMRTR_INSTALL/helpers/helpers.sh"

USER_BIN_DIR="$HOME/.local/bin"
SMRTR_BIN_DIR="$HOME/.local/share/smrtr-os/bin"

install_waybar_launchers() {
    local scripts=(
        smrtr-launch-or-focus-tui
        smrtr-launch-bluetooth
        smrtr-launch-wifi
        smrtr-launch-audio
    )
    local script

    ensure_dir "$USER_BIN_DIR"
    ensure_dir "$SMRTR_BIN_DIR"

    log_step "Installing Waybar launcher scripts..."
    for script in "${scripts[@]}"; do
        install -m 755 "$REPO_DIR/bin/$script" "$SMRTR_BIN_DIR/$script"
        install -m 755 "$REPO_DIR/bin/$script" "$USER_BIN_DIR/$script"
    done
}

log_step "Installing Waybar config..."
install_config "waybar/config.jsonc" "$USER_CONFIG/waybar/config.jsonc"
install_config "waybar/style.css" "$USER_CONFIG/waybar/style.css"
install_waybar_launchers

# Conditionally include battery module
log_step "Detecting battery..."
if ls /sys/class/power_supply/BAT* &>/dev/null; then
    log_info "Battery detected — enabling battery module."
    sed -i 's/SMRTR_BATTERY_PLACEHOLDER/"battery",/' "$USER_CONFIG/waybar/config.jsonc"
else
    log_info "No battery detected — removing battery module."
    sed -i '/SMRTR_BATTERY_PLACEHOLDER/d' "$USER_CONFIG/waybar/config.jsonc"
fi

log_info "Waybar setup complete."
