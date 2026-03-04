echo "Add the new Flexoki Light theme"

if [[ ! -L ~/.config/smrtr/themes/flexoki-light ]]; then
  ln -nfs ~/.local/share/smrtr/themes/flexoki-light ~/.config/smrtr/themes/
fi
