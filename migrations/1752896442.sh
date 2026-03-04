echo "Replace volume control GUI with a TUI"

if smrtr-cmd-missing wiremix; then
  smrtr-pkg-add wiremix
  smrtr-pkg-drop pavucontrol
  smrtr-refresh-applications
  smrtr-refresh-waybar
fi
