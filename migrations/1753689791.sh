echo "Add the new ristretto theme as an option"

if [[ ! -L ~/.config/smrtr/themes/ristretto ]]; then
  ln -nfs ~/.local/share/smrtr/themes/ristretto ~/.config/smrtr/themes/
fi
