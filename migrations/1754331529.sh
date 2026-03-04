echo "Update Waybar for new Smrtr menu"

if ! grep -q "" ~/.config/waybar/config.jsonc; then
  smrtr-refresh-waybar
fi
