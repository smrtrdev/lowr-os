# Copy over the keyboard layout that's been set in Arch during install to Niri
conf="/etc/vconsole.conf"
niri_conf="$HOME/.config/niri/config.kdl"

if grep -q '^XKBLAYOUT=' "$conf"; then
  layout=$(grep '^XKBLAYOUT=' "$conf" | cut -d= -f2 | tr -d '"')
  sed -i "/^[[:space:]]*options /i\      layout \"$layout\"" "$niri_conf"
fi

if grep -q '^XKBVARIANT=' "$conf"; then
  variant=$(grep '^XKBVARIANT=' "$conf" | cut -d= -f2 | tr -d '"')
  sed -i "/^[[:space:]]*options /i\      variant \"$variant\"" "$niri_conf"
fi
