source vendor/autoload/wt.nu

use aliases.nu *

def lowr-command-present [command: string] {
  (which $command | is-not-empty)
}

def get-cache-path [name: string] {
  let cache_dir = ($env.HOME | path join ".cache" $name)
  $cache_dir
}

def --env lowr-init-zoxide [] {
  $env.config = (
    $env.config?
    | default {}
    | upsert hooks { default {} }
    | upsert hooks.env_change { default {} }
    | upsert hooks.env_change.PWD { default [] }
  )

  let zoxide_hooked = (
    $env.config.hooks.env_change.PWD
    | any {|hook| try { $hook.__zoxide_hook? | default false } catch { false }}
  )

  if not $zoxide_hooked {
    $env.config.hooks.env_change.PWD = (
      $env.config.hooks.env_change.PWD
      | append {
        __zoxide_hook: true,
        code: {|_, dir| ^zoxide add -- $dir}
      }
    )
  }
}

def "lowr-parse-vars" [] {
  $in | from csv --noheaders --no-infer | rename op name value
}

def --env "lowr-update-env" [] {
  for $var in $in {
    if $var.op == "set" {
      if ($var.name | str uppercase) == "PATH" {
        $env.PATH = ($var.value | split row (char esep))
      } else {
        load-env {($var.name): $var.value}
      }
    } else if $var.op == "hide" and ($var.name in $env) {
      hide-env $var.name
    }
  }
}

def --env lowr-add-hook [field: cell-path new_hook: any] {
  let target = ($field | split cell-path | update optional true | into cell-path)
  let config = ($env.config? | default {})
  let hooks = ($config | get $target | default [])

  $env.config = ($config | upsert $target ($hooks ++ [$new_hook]))
}

def --env lowr-mise-hook [] {
  ^mise hook-env -s nu | lowr-parse-vars | lowr-update-env
}

def --env lowr-init-mise [] {
  $env.MISE_SHELL = "nu"
  lowr-mise-hook

  let mise_hook = {
    condition: { "MISE_SHELL" in $env }
    code: { lowr-mise-hook }
  }

  lowr-add-hook hooks.pre_prompt $mise_hook
  lowr-add-hook hooks.env_change.PWD $mise_hook
}

def --env lowr-init-starship [] {
  let starship_path = (which starship | get 0.path)

  $env.STARSHIP_SHELL = "nu"
  load-env {
    STARSHIP_SESSION_KEY: (random chars -l 16)
    PROMPT_MULTILINE_INDICATOR: (run-external $starship_path prompt "--continuation")
    PROMPT_INDICATOR: ""
    PROMPT_COMMAND: {||
      let cmd_duration = if $env.CMD_DURATION_MS == "0823" { 0 } else { $env.CMD_DURATION_MS }
      let args = (
        [
          "prompt"
          "--cmd-duration"
          ($cmd_duration | into string)
          $"--status=($env.LAST_EXIT_CODE)"
          "--terminal-width"
          ((term size).columns | into string)
        ]
        | append (
          if (which "job list" | where type == "built-in" | is-not-empty) {
            ["--jobs", ((job list | length) | into string)]
          } else {
            []
          }
        )
      )

      run-external $starship_path ...$args
    }
    PROMPT_COMMAND_RIGHT: {||
      let cmd_duration = if $env.CMD_DURATION_MS == "0823" { 0 } else { $env.CMD_DURATION_MS }
      let args = (
        [
          "prompt"
          "--right"
          "--cmd-duration"
          ($cmd_duration | into string)
          $"--status=($env.LAST_EXIT_CODE)"
          "--terminal-width"
          ((term size).columns | into string)
        ]
        | append (
          if (which "job list" | where type == "built-in" | is-not-empty) {
            ["--jobs", ((job list | length) | into string)]
          } else {
            []
          }
        )
      )

      run-external $starship_path ...$args
    }
  }

  $env.config = (
    $env.config?
    | default {}
    | merge {
      render_right_prompt_on_last_line: true
    }
  )
}

if (lowr-command-present "mise") {
  lowr-init-mise
}

if (lowr-command-present "starship") {
  lowr-init-starship
}

if (lowr-command-present "zoxide") {
  lowr-init-zoxide
}

if (lowr-command-present "carapace") {
  source $"($nu.cache-dir)/carapace.nu"
}

def --env lowr-init-activitywatch [] {
  lowr-add-hook hooks.pre_prompt {||
    try { ^lowr-aw-terminal-heartbeat } catch { }
  }
}

if (lowr-command-present "aw-qt") { lowr-init-activitywatch }

use try_wrapper.nu *
