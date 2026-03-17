def lowr-command-present [command: string] {
  (which $command | is-not-empty)
}

export def --env --wrapped zd [...rest: string] {
  match $rest {
    [] => { cd ~ }
    [ "-" ] => { cd - }
    [ $path ] if (($path | path expand | path type) == "dir") => { cd $path }
    _ => {
      if not (lowr-command-present "zoxide") {
        error make {
          msg: "zoxide is not installed"
        }
      }

      let target = (^zoxide query --exclude $env.PWD -- ...$rest | str trim)
      if ($target | is-empty) {
        error make {
          msg: "Error: Directory not found"
        }
      }

      cd $target
      print $env.PWD
    }
  }
}

export alias cd = zd
export alias z = zd
export alias y = yazi

export def --env --wrapped zi [...rest: string] {
  if not (lowr-command-present "zoxide") {
    error make {
      msg: "zoxide is not installed"
    }
  }

  let target = (^zoxide query --interactive -- ...$rest | str trim)
  if ($target | is-empty) {
    return
  }

  cd $target
}

# export def --wrapped ls [...rest: string] {
#   if (lowr-command-present "eza") {
#     ^eza -lh --group-directories-first --icons=auto ...$rest
#   } else {
#     ^ls ...$rest
#   }
# }

export def --wrapped lsa [...rest: string] {
  let args = if ($rest | is-empty) { ["." ] } else { $rest }
  ls --all ...$args
}

export def --wrapped lt [...rest: string] {
  if (lowr-command-present "eza") {
    ^eza --tree --level=2 --long --icons --git ...$rest
  } else {
    ^ls ...$rest
  }
}

export def --wrapped lta [...rest: string] {
  lt -a ...$rest
}

export def ff [] {
  if not (lowr-command-present "fzf") {
    error make {
      msg: "fzf is not installed"
    }
  }

  if (lowr-command-present "bat") {
    ^fzf --preview "bat --style=numbers --color=always {}"
  } else {
    ^fzf
  }
}

export def eff [] {
  let editor = ($env.EDITOR? | default "nvim")
  let target = (ff | str trim)

  if ($target | is-empty) {
    return
  }

  run-external $editor $target
}

export def --wrapped open [...rest: string] {
  ^xdg-open ...$rest
}

export alias .. = cd ..
export alias ... = cd ../..
export alias .... = cd ../../..

export alias c = opencode
export def --wrapped cx [...rest: string] {
  print "\u{001b}[2J\u{001b}[3J\u{001b}[H}"
  ^claude --allow-dangerously-skip-permissions ...$rest
}
export alias d = docker
export alias r = rails

export def --wrapped t [...rest: string] {
  if ($rest | is-not-empty) {
    ^tmux ...$rest
    return
  }

  try {
    ^tmux attach
  } catch {
    ^tmux new -s Work
  }
}

export def --wrapped n [...rest: string] {
  if ($rest | is-empty) {
    ^nvim .
  } else {
    ^nvim ...$rest
  }
}

export alias g = git
export alias gcm = git commit -m
export alias gcam = git commit -a -m
export alias gcad = git commit -a --amend

export alias zed = zeditor
