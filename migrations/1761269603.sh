echo "Add right-click terminal action to waybar smrtr menu icon"

WAYBAR_CONFIG="$HOME/.config/waybar/config.jsonc"

if [[ -f $WAYBAR_CONFIG ]] && ! grep -A5 '"custom/smrtr"' "$WAYBAR_CONFIG" | grep -q '"on-click-right"'; then
  sed -i '/"on-click": "smrtr-menu",/a\    "on-click-right": "smrtr-launch-terminal",' "$WAYBAR_CONFIG"
fi
