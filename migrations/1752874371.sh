echo "Add Catppuccin Latte light theme"

if [[ ! -L $HOME/.config/smrtr/themes/catppuccin-latte ]]; then
  ln -snf ~/.local/share/smrtr/themes/catppuccin-latte ~/.config/smrtr/themes/
fi
