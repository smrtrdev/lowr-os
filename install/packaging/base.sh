#!/usr/bin/env bash
set -euo pipefail
source "$SMRTR_INSTALL/helpers/helpers.sh"

# --- AUR Helper (paru) ---

log_step "Setting up paru..."
ensure_paru
log_info "paru is ready."

# --- Packages ---

mapfile -t packages < <(grep -v '^#' "$SMRTR_INSTALL/smrtr-base.packages" | grep -v '^$')
smrtr-pkg-add "${packages[@]}"

# --- Services ---

enable_user_service pipewire.service
enable_user_service pipewire-pulse.service
enable_user_service wireplumber.service

# Configure NetworkManager to use iwd as backend
sudo mkdir -p /etc/NetworkManager/conf.d
if [[ ! -f /etc/NetworkManager/conf.d/iwd.conf ]]; then
    sudo tee /etc/NetworkManager/conf.d/iwd.conf >/dev/null <<'EOF'
[device]
wifi.backend=iwd
EOF
fi

enable_service NetworkManager.service
enable_service iwd.service
enable_service bluetooth.service

# --- Printing (optional) ---

if ask_yes_no "Install printing support (CUPS)?" "n"; then
    log_step "Installing CUPS..."
    smrtr-pkg-add cups cups-pdf
    enable_service cups.service
fi

# --- Firewall ---

enable_service ufw.service
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw --force enable

# --- GPU Drivers ---

log_step "Detecting GPU..."
gpu_info=$(lspci | grep -iE "vga|3d|display")
log_info "Detected: $gpu_info"

if echo "$gpu_info" | grep -qi "intel"; then
    log_step "Installing Intel GPU drivers..."
    smrtr-pkg-add mesa vulkan-intel intel-media-driver
fi

if echo "$gpu_info" | grep -qi "amd\|radeon"; then
    log_step "Installing AMD GPU drivers..."
    smrtr-pkg-add mesa vulkan-radeon libva-mesa-driver
fi

if echo "$gpu_info" | grep -qi "nvidia"; then
    log_step "Installing NVIDIA GPU drivers..."
    smrtr-pkg-add nvidia nvidia-utils nvidia-settings
fi

log_info "Base packages setup complete."
