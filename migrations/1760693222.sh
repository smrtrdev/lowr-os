echo "Use explicit timezone selector when right-clicking on clock"

sed -i 's/smrtr-cmd-tzupdate/smrtr-launch-floating-terminal-with-presentation smrtr-tz-select/g' ~/.config/waybar/config.jsonc
