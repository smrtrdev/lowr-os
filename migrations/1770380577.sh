echo "Use interactive background selector menu"

mkdir -p ~/.config/elephant/menus
ln -snf $SMRTR_PATH/default/elephant/smrtr_background_selector.lua ~/.config/elephant/menus/smrtr_background_selector.lua
smrtr-restart-walker
