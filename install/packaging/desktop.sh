#!/usr/bin/env bash
set -euo pipefail
source "$SMRTR_INSTALL/helpers/helpers.sh"

log_step "Installing Niri and Wayland packages..."
pkg_install niri uwsm xwayland-satellite \
    xdg-desktop-portal xdg-desktop-portal-gnome xdg-utils \
    qt6-wayland qt5-wayland \
    polkit-gnome \
    wl-clipboard \
    swaybg swaylock swayidle \
    brightnessctl playerctl \
    grim slurp pulsemixer \
    imagemagick

log_step "Installing AUR packages for Niri..."
aur_install cliphist wlsunset

# --- Install configs ---

log_step "Installing Niri config..."
WALLPAPER_PATH="$USER_CONFIG/smrtr/wallpapers/default.jpg"
install_config "niri/config.kdl" "$USER_CONFIG/niri/config.kdl"

# Substitute wallpaper placeholder
sed -i "s|SMRTR_WALLPAPER_PLACEHOLDER|$WALLPAPER_PATH|g" "$USER_CONFIG/niri/config.kdl"

install_config "swaylock/config" "$USER_CONFIG/swaylock/config"
install_config "xdg-desktop-portal/portals.conf" "$USER_CONFIG/xdg-desktop-portal/portals.conf"

# --- Logind configuration ---

log_step "Configuring logind..."
sudo mkdir -p /etc/systemd/logind.conf.d
sudo tee /etc/systemd/logind.conf.d/smrtr.conf >/dev/null <<'EOF'
[Login]
HandleLidSwitch=suspend
HandleLidSwitchExternalPower=ignore
HandlePowerKey=poweroff
IdleAction=suspend
IdleActionSec=30min
EOF

# --- Create required directories ---

log_step "Creating directories..."
ensure_dir "$HOME/Pictures/Screenshots"
ensure_dir "$USER_CONFIG/smrtr/wallpapers"

# --- Default wallpaper (solid color fallback) ---

if [[ ! -f "$WALLPAPER_PATH" ]]; then
    log_info "Generating default wallpaper (solid dark background)..."
    if command -v magick &>/dev/null; then
        magick -size 3840x2160 xc:'#1e1e2e' "$WALLPAPER_PATH"
    elif command -v convert &>/dev/null; then
        convert -size 3840x2160 xc:'#1e1e2e' "$WALLPAPER_PATH"
    else
        log_warn "ImageMagick not found. Install a wallpaper manually at: $WALLPAPER_PATH"
    fi
fi

log_info "Niri compositor setup complete."
