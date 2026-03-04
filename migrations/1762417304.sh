echo "Replace bluetooth GUI with TUI"

smrtr-pkg-add bluetui
smrtr-pkg-drop blueberry

if ! grep -q "smrtr-launch-bluetooth" ~/.config/waybar/config.jsonc; then
  sed -i 's/blueberry/smrtr-launch-bluetooth/' ~/.config/waybar/config.jsonc
fi
