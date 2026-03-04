#!/usr/bin/env bash

desired_repo="$HOME/.local/share/smrtr-os"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
probe="$script_dir"
current_repo=""

# Find the repo root by walking up from this script location.
while [[ "$probe" != "/" ]]; do
    if [[ -d "$probe/.git" ]]; then
        current_repo="$probe"
        break
    fi
    probe="$(dirname "$probe")"
done

if [[ -z "$current_repo" ]]; then
    log_info "Could not locate smrtr-os repository from: $script_dir"
    log_info "Cloning smrtr-os repo to: $desired_repo"
    mkdir -p "$(dirname "$desired_repo")"

    if [[ -e "$desired_repo" ]]; then
        log_error "Destination already exists: $desired_repo"
        log_error "Please remove or move it, then rerun the installer."
        exit 1
    fi

    git clone "https://codeberg.org/smrtr/smrtr-os.git" "$desired_repo"
    log_info "Restarting installer from cloned path: $desired_repo/install.sh"
    exec bash -lc "cd \"$desired_repo\" && ./install.sh"
fi

if [[ "$current_repo" == "$desired_repo" ]]; then
    export SMRTR_PATH="$desired_repo"
    export SMRTR_INSTALL="$desired_repo/install"
    REPO_DIR="$desired_repo"
    CONFIG_DIR="$desired_repo/config"
    return 0
fi

log_info "Relocating smrtr-os repo to: $desired_repo"
mkdir -p "$(dirname "$desired_repo")"

if [[ -e "$desired_repo" ]]; then
    log_error "Destination already exists: $desired_repo"
    log_error "Please remove or move it, then rerun the installer."
    exit 1
fi

mv "$current_repo" "$desired_repo"

log_info "Restarting installer from new path: $desired_repo/install.sh"
exec bash -lc "cd \"$desired_repo\" && ./install.sh"
