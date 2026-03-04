echo "Install swayOSD to show volume status"

if smrtr-cmd-missing swayosd-server; then
  smrtr-pkg-add swayosd
  setsid uwsm-app -- swayosd-server &>/dev/null &
fi
