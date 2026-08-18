export def --env --wrapped lowr-try [...rest: string] {
  let tries_path = ($env.HOME | path join "Work" "tries")
  let marker = "__LOWR_PWD__"
  let command = "out=$(/usr/bin/try exec --path \"$LOWR_TRY_PATH\" \"$@\" 2>/dev/tty)\nif [[ $? == 0 ]]; then\n  eval \"$out\"\n  printf '%s%s\\n' \"$LOWR_TRY_MARKER\" \"$PWD\"\nelse\n  echo \"$out\"\n  exit 1\nfi"
  let result = (
    with-env {
      LOWR_TRY_PATH: $tries_path,
      LOWR_TRY_MARKER: $marker
    } {
      do { ^/bin/bash -lc $command bash ...$rest } | complete
    }
  )

  let stdout_lines = ($result.stdout | lines)
  let pwd_line = ($stdout_lines | where {|line| $line | str starts-with $marker } | last)
  let output_lines = ($stdout_lines | where {|line| not ($line | str starts-with $marker) })

  if ($output_lines | is-not-empty) {
    print ($output_lines | str join (char nl))
  }

  if ($result.exit_code != 0) {
    return
  }

  if ($pwd_line | is-not-empty) {
    cd ($pwd_line | str replace $marker "")
  }
}
