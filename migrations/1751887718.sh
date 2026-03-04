echo "Install Impala as new wifi selection TUI"

if smrtr-cmd-missing impala; then
  smrtr-pkg-add impala
  smrtr-refresh-waybar
fi
