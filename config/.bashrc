# smrtr-os shell integration
SMRTR_DEFAULT="${SMRTR_PATH:-$HOME/.local/share/smrtr-os}/default"
source "$SMRTR_DEFAULT/bash/aliases.sh"
source "$SMRTR_DEFAULT/bash/functions.sh"
export PATH="$HOME/.local/share/smrtr-os/bin:$PATH"
eval "$(starship init bash)"
eval "$(zoxide init bash)"
eval "$(fzf --bash)"
eval "$(mise activate bash)"
export EDITOR="${EDITOR:-nvim}"
export VISUAL="${VISUAL:-nvim}"
export HISTSIZE=10000
export HISTFILESIZE=20000
export HISTCONTROL=ignoreboth:erasedups
