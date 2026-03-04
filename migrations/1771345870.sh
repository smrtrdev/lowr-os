echo "Switch lmstudio -> lmstudio-bin"

if pacman -Q lmstudio &>/dev/null; then
  smrtr-pkg-drop lmstudio
  smrtr-pkg-add lmstudio-bin
fi
