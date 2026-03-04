echo "Allow updating of timezone by right-clicking on the clock (or running smrtr-cmd-tzupdate)"

if smrtr-cmd-missing tzupdate; then
  bash "$SMRTR_PATH/install/config/timezones.sh"
  smrtr-refresh-waybar
fi
