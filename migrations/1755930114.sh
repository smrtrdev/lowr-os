echo "Add new Smrtr Menu icon to Waybar"

mkdir -p ~/.local/share/fonts
cp ~/.local/share/smrtr/config/smrtr.ttf ~/.local/share/fonts/
fc-cache
