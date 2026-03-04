#!/usr/bin/env bash
set -euo pipefail
source "$SMRTR_INSTALL/helpers/helpers.sh"

if ! command -v mise &>/dev/null; then
    log_warn "mise is not on PATH. Shell configs reference 'mise activate' which will fail until mise is installed (see packaging/development.sh)."
fi

log_step "Installing shell tools..."
pkg_install nushell starship fzf fd ripgrep eza bat zoxide tldr zellij htop btop tree

log_step "Installing AUR shell packages..."
aur_install carapace-bin

# --- Shell Selection ---

log_step "Shell selection..."
default_shell=$(ask_choice "Select default shell:" "bash" "nushell")
case "$default_shell" in
    bash)
        chsh -s /usr/bin/bash
        log_info "Default shell set to bash."
        ;;
    nushell)
        chsh -s /usr/bin/nu
        log_info "Default shell set to nushell."
        ;;
esac

# --- Install Config Files ---

log_step "Installing shell configs..."

# Nushell configs
install_config "nushell/config.nu" "$USER_CONFIG/nushell/config.nu"
install_config "nushell/env.nu" "$USER_CONFIG/nushell/env.nu"
install_config "nushell/aliases.nu" "$USER_CONFIG/nushell/aliases.nu"

# Starship
install_config "starship.toml" "$USER_CONFIG/starship.toml"

# Zellij
install_config "zellij/config.kdl" "$USER_CONFIG/zellij/config.kdl"
install_config "zellij/layouts/default.kdl" "$USER_CONFIG/zellij/layouts/default.kdl"

# --- Bashrc Integration ---

log_step "Configuring .bashrc..."
install_config ".bashrc" "$HOME/.bashrc" "$REPO_DIR/config"

# --- Create cache dirs for nushell integrations ---

log_step "Creating nushell cache directories..."
ensure_dir "$HOME/.cache/starship"
ensure_dir "$HOME/.cache/zoxide"
ensure_dir "$HOME/.cache/carapace"
ensure_dir "$HOME/.cache/mise"

log_info "Shell configuration complete."
