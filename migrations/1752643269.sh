echo "Add new matte black theme"

if [[ ! -L $HOME/.config/smrtr/themes/matte-black ]]; then
  ln -snf ~/.local/share/smrtr/themes/matte-black ~/.config/smrtr/themes/
fi
