echo "Replace wofi with walker as the default launcher"

if smrtr-cmd-missing walker; then
  smrtr-pkg-add walker-bin libqalculate

  smrtr-pkg-drop wofi
  rm -rf ~/.config/wofi

  mkdir -p ~/.config/walker
  cp -r ~/.local/share/smrtr/config/walker/* ~/.config/walker/
fi
