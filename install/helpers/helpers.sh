#!/usr/bin/env bash
# smrtr-os shared helper library
# Sourced by install.sh and all feature scripts

# Constants
REPO_DIR="${SMRTR_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CONFIG_DIR="$REPO_DIR/config/.config"
DEFAULT_DIR="$REPO_DIR/default"
USER_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
BACKUP_DIR="$USER_CONFIG/smrtr-backup/$(date +%Y%m%d_%H%M%S)"
PARU_BIN=""

# --- Logging ---

log_info() {
    printf '\033[1;34m[INFO]\033[0m %s\n' "$*"
}

log_warn() {
    printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2
}

log_error() {
    printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2
}

log_step() {
    printf '\033[1m[=>]\033[0m %s\n' "$*"
}

# --- Package Management ---

pkg_installed() {
    pacman -Qi "$1" &>/dev/null
}

pkg_install() {
    local to_install=()
    for pkg in "$@"; do
        if ! pkg_installed "$pkg"; then
            to_install+=("$pkg")
        fi
    done
    if [[ ${#to_install[@]} -gt 0 ]]; then
        log_info "Installing packages: ${to_install[*]}"
        sudo pacman -S --needed --noconfirm "${to_install[@]}"
    else
        log_info "All packages already installed: $*"
    fi
}

aur_install() {
    if ! ensure_paru; then
        return 1
    fi
    local to_install=()
    for pkg in "$@"; do
        if ! pkg_installed "$pkg"; then
            to_install+=("$pkg")
        fi
    done
    if [[ ${#to_install[@]} -gt 0 ]]; then
        log_info "Installing AUR packages: ${to_install[*]}"
        "$PARU_BIN" -S --needed --noconfirm "${to_install[@]}"
    else
        log_info "All AUR packages already installed: $*"
    fi
}

paru_works() {
    local bin="$1"
    [[ -x "$bin" ]] || return 1
    "$bin" -V &>/dev/null || "$bin" --version &>/dev/null || "$bin" --help &>/dev/null
}

resolve_paru_bin() {
    local candidate

    if paru_works /usr/bin/paru; then
        echo "/usr/bin/paru"
        return 0
    fi

    if command -v paru &>/dev/null; then
        candidate="$(command -v paru)"
        if paru_works "$candidate"; then
            echo "$candidate"
            return 0
        fi
    fi

    return 1
}

build_paru_from_source() {
    local resolved
    local tmpdir

    sudo pacman -S --needed --noconfirm base-devel git

    # On fresh systems, rustup may exist without a default toolchain.
    if command -v rustup &>/dev/null && ! rustup show active-toolchain &>/dev/null; then
        log_info "Configuring rustup default toolchain (stable)..."
        rustup default stable
    fi

    tmpdir="$(mktemp -d)"
    if git clone https://aur.archlinux.org/paru.git "$tmpdir/paru" && \
       (cd "$tmpdir/paru" && makepkg -si --syncdeps --needed --noconfirm); then
        if resolved="$(resolve_paru_bin)"; then
            PARU_BIN="$resolved"
            rm -rf "$tmpdir"
            return 0
        fi
    fi
    rm -rf "$tmpdir"
    return 1
}

ensure_paru() {
    local resolved
    local paru_err=""

    if resolved="$(resolve_paru_bin)"; then
        PARU_BIN="$resolved"
        return 0
    fi

    if command -v paru &>/dev/null; then
        log_warn "paru exists but is not runnable (often caused by a pacman/libalpm upgrade). Reinstalling paru..."
    else
        log_info "paru not found. Installing paru..."
    fi

    if pacman -Si paru &>/dev/null; then
        log_info "Trying repo package: paru"
        sudo pacman -R --noconfirm paru-bin paru-bin-debug &>/dev/null || true
        if sudo pacman -S --noconfirm paru; then
            if resolved="$(resolve_paru_bin)"; then
                PARU_BIN="$resolved"
                return 0
            fi
        fi
        log_warn "Repo paru install did not produce a working binary."
    fi

    if [[ -x /usr/bin/paru ]]; then
        paru_err="$(/usr/bin/paru -V 2>&1 || true)"
        if [[ -z "$paru_err" ]]; then
            paru_err="$(/usr/bin/paru --version 2>&1 || true)"
        fi
        log_warn "Detected /usr/bin/paru, but it is not runnable."
        if [[ -n "$paru_err" ]]; then
            log_warn "paru runtime error: $paru_err"
        fi

        # paru-bin can briefly lag behind pacman SONAME bumps (libalpm).
        # If that happens, rebuild paru from source against local libraries.
        if grep -q "libalpm\\.so\\." <<<"$paru_err"; then
            log_warn "Detected libalpm ABI mismatch. Rebuilding paru from source..."
            sudo pacman -R --noconfirm paru-bin paru-bin-debug paru &>/dev/null || true
        fi
    fi

    log_info "Installing paru from AUR source..."
    if build_paru_from_source; then
        return 0
    fi

    log_error "paru install/repair failed."
    return 1
}

# --- Config Management ---

ensure_dir() {
    [[ -d "$1" ]] || mkdir -p "$1"
}

backup_config() {
    local target="$1"
    local source="${2:-}"
    [[ -e "$target" ]] || return 0

    if [[ -n "$source" && -e "$source" ]] && cmp -s "$source" "$target"; then
        return 0
    fi

    local rel_path="${target#$HOME/}"
    local backup_path="$BACKUP_DIR/$rel_path"

    ensure_dir "$(dirname "$backup_path")"
    cp -a "$target" "$backup_path"
    log_info "Backed up $target → $backup_path"
}

install_config() {
    local source_rel="$1"
    local target="$2"
    local base="${3:-$CONFIG_DIR}"
    local source="$base/$source_rel"

    if [[ ! -e "$source" ]]; then
        log_error "Config source not found: $source"
        return 1
    fi

    backup_config "$target" "$source"
    ensure_dir "$(dirname "$target")"
    cp -a "$source" "$target"
    if [[ -d "$target" ]]; then
        find "$target" -type d -exec chmod 755 {} +
        find "$target" -type f -exec chmod 644 {} +
    else
        chmod 644 "$target"
    fi
    log_info "Installed config: $source_rel → $target"
}

# --- User Prompts ---

ask_yes_no() {
    local question="$1"
    local default="${2:-y}"
    local prompt

    if [[ "$default" == "y" ]]; then
        prompt="$question [Y/n] "
    else
        prompt="$question [y/N] "
    fi

    local answer
    read -rp "$prompt" answer </>/dev/tty
    answer="${answer:-$default}"

    [[ "${answer,,}" == "y" ]]
}

ask_choice() {
    local question="$1"
    shift
    local options=("$@")
    local i

    echo "$question" >&2
    for i in "${!options[@]}"; do
        echo "  $((i + 1))) ${options[$i]}" >&2
    done

    local choice
    while true; do
        read -rp "Enter choice [1-${#options[@]}]: " choice <>/dev/tty
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
            echo "${options[$((choice - 1))]}"
            return 0
        fi
        echo "Invalid choice. Try again." >&2
    done
}

# --- Service Management ---

enable_service() {
    log_info "Enabling service: $1"
    sudo systemctl enable --now "$1"
}

enable_user_service() {
    log_info "Enabling user service: $1"
    systemctl --user enable --now "$1"
}
