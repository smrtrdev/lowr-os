echo "Add minimal starship prompt to terminal"

if smrtr-cmd-missing starship; then
  smrtr-pkg-add starship
  cp $SMRTR_PATH/config/starship.toml ~/.config/starship.toml
fi
