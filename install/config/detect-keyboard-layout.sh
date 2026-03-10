# Copy over the keyboard layout that's been set in Arch during install to Niri
conf="/etc/vconsole.conf"
niri_conf="$HOME/.config/niri/config.kdl"

update_niri_xkb_setting() {
  local key=$1
  local value=$2
  local tmp_file

  tmp_file=$(mktemp)

  awk -v key="$key" -v value="$value" '
    /^[[:space:]]*xkb[[:space:]]*\{/ {
      in_xkb = 1
    }

    in_xkb && $1 == key {
      if (!updated) {
        print "      " key " \"" value "\""
        updated = 1
      }
      next
    }

    in_xkb && /^[[:space:]]*\}/ {
      if (!updated) {
        print "      " key " \"" value "\""
      }
      in_xkb = 0
      updated = 0
    }

    {
      print
    }
  ' "$niri_conf" > "$tmp_file"

  mv "$tmp_file" "$niri_conf"
}

if [[ -f $conf && -f $niri_conf ]]; then
  if grep -q '^XKBLAYOUT=' "$conf"; then
    layout=$(grep '^XKBLAYOUT=' "$conf" | cut -d= -f2 | tr -d '"')
    update_niri_xkb_setting layout "$layout"
  fi

  if grep -q '^XKBVARIANT=' "$conf"; then
    variant=$(grep '^XKBVARIANT=' "$conf" | cut -d= -f2 | tr -d '"')
    update_niri_xkb_setting variant "$variant"
  fi
fi
