$env.config = {
  show_banner: false
  edit_mode: emacs
  cursor_shape: {
    emacs: line
    vi_insert: line
    vi_normal: block
  }
  completions: {
    quick: true
    partial: true
    external: {
      enable: true
      max_results: 100
      completer: null
    }
  }
  show_hints: true
  history: {
    max_size: 100000
    sync_on_enter: true
  }
  hooks: {
    pre_prompt: []
    env_change: {}
  }
  render_right_prompt_on_last_line: false
}

source ~/.local/share/lowr/default/nushell/config.nu
use aliases.nu *



# Add user-specific Nushell configuration below.
