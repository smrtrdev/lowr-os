# smrtr-os nushell configuration

$env.config = {
    show_banner: false
    edit_mode: emacs
    cursor_shape: {
        emacs: line
        vi_insert: line
        vi_normal: block
    }
    keybindings: [
        {
            name: fuzzy_history
            modifier: control
            keycode: char_r
            mode: [emacs vi_insert]
            event: {
                send: executehostcommand
                cmd: "commandline edit --replace (history | each { |it| $it.command } | uniq | reverse | str join (char newline) | fzf --height=40% | str trim)"
            }
        }
        {
            name: fuzzy_file
            modifier: control
            keycode: char_t
            mode: [emacs vi_insert]
            event: {
                send: executehostcommand
                cmd: "commandline edit --insert (fd --type f --hidden --follow --exclude .git | fzf --height=40% | str trim)"
            }
        }
    ]
}

# Source aliases
source ~/.config/nushell/aliases.nu

# Source cached integrations
use ~/.cache/starship/init.nu
source ~/.cache/zoxide/init.nu
source ~/.cache/carapace/init.nu
source ~/.cache/mise/init.nu

# Carapace bridge
$env.CARAPACE_BRIDGES = 'zsh,fish,bash,inshellisense'
