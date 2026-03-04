echo "Uniquely identify terminal apps with custom app-ids using smrtr-launch-tui"

# Replace terminal -e calls with smrtr-launch-tui in bindings
sed -i 's/\$terminal -e \([^ ]*\)/smrtr-launch-tui \1/g' ~/.config/hypr/bindings.conf

# Update waybar to use smrtr-launch-or-focus with smrtr-launch-tui for TUI apps
sed -i 's|xdg-terminal-exec btop|smrtr-launch-or-focus-tui btop|' ~/.config/waybar/config.jsonc
sed -i 's|xdg-terminal-exec --app-id=com\.smrtr\.Wiremix -e wiremix|smrtr-launch-or-focus-tui wiremix|' ~/.config/waybar/config.jsonc
