echo "Link new theme picker config"

mkdir -p ~/.config/elephant/menus
ln -snf $SMRTR_PATH/default/elephant/smrtr_themes.lua ~/.config/elephant/menus/smrtr_themes.lua
sed -i '/"menus",/d' ~/.config/walker/config.toml
smrtr-restart-walker
