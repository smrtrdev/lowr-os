let lowr_path = ($env.HOME | path join ".local" "share" "lowr")
let lowr_bin = ($lowr_path | path join "bin")
let local_bin = ($env.HOME | path join ".local" "bin")

$env.SHELL = "/usr/bin/nu"

$env.LOWR_PATH = $lowr_path
$env.BAT_THEME = "ansi"

$env.SSH_AUTH_SOCK = $"($env.XDG_RUNTIME_DIR)/ssh-agent.socket"

if "EDITOR" in $env {
  $env.SUDO_EDITOR = $env.EDITOR
}

$env.VISUAL = $env.EDITOR

# Generate cached shell integrations
def --env ensure-cache [name: string, cmd: string] {
    let cache_dir = ($env.HOME | path join ".cache" $name)
    let cache_file = ($cache_dir | path join "init.nu")
    if not ($cache_dir | path exists) { mkdir $cache_dir }
    if not ($cache_file | path exists) {
        ^bash -c $cmd | save -f $cache_file
    }
}

let extra_paths_prepend = [
  $lowr_bin,
  $local_bin
]

let extra_paths_append = [
  "/usr/bin"
]

$env.PATH = ($extra_paths_prepend | append $env.PATH | append $extra_paths_append)


def lowr-command-present [command: string] {
  (which $command | is-not-empty)
}

# if (lowr-command-present "mise") {
#   ensure-cache "mise" "mise activate nu"
# }

# if (lowr-command-present "starship") {
#   ensure-cache "starship" "starship init nu"
# }

# if (lowr-command-present "zoxide") {
#   ensure-cache "zoxide" "zoxide init nushell"
# }

# if (lowr-command-present "carapace") {
#   ensure-cache "carapace" "carapace _carapace nushell"
# }

if (lowr-command-present "carapace") {
  $env.CARAPACE_BRIDGES = 'zsh,fish,bash,inshellisense' # optional


  let cache_dir = $nu.cache-dir

  if not ($cache_dir | path exists) { mkdir $cache_dir }
  let cache_file = ($cache_dir | path join "carapace.nu")
  if not ($cache_file | path exists) {
    ^carapace _carapace nushell | save -f $cache_file
  }
}
