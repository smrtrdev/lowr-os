# smrtr-os bash aliases

# Modern replacements
alias ls='eza --icons'
alias ll='eza -la --icons'
alias lt='eza --tree --icons'
alias cat='bat --paging=never'
alias grep='rg'
alias cd='z'

# Navigation
alias ..='cd ..'
alias ...='cd ../..'

# Git
alias gs='git status'
alias gl='git log --oneline --graph'
alias gd='git diff'
alias gc='git commit'
alias gp='git push'
