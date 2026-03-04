echo "Update fastfetch config with new Smrtr logo"

smrtr-refresh-config fastfetch/config.jsonc

mkdir -p ~/.config/smrtr/branding
cp $SMRTR_PATH/icon.txt ~/.config/smrtr/branding/about.txt
