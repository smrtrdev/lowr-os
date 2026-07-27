def load-config-paths [] {
    let config_file = ($env.HOME | path join ".config" "lowr" "env" "path")
    if not ($config_file | path exists) { return [] }

    open $config_file
    | lines
    | each { |line|
        $line
        | str replace --regex '#.*$' ''  # strip comments
        | str trim
    }
    | where { |line| ($line | str length) > 0 }
    | each { |line| $line | str replace --all '$HOME' $env.HOME }
}

def --env set-path [extra_prepend: list<string>, extra_append: list<string>] {
    let config_paths = (load-config-paths)
    $env.PATH = ($extra_prepend | append $config_paths | append $env.PATH | append $extra_append)
}
