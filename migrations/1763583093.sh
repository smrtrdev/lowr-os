echo "Make ethereal available as new theme"

if [[ ! -L ~/.config/smrtr/themes/ethereal ]]; then
  rm -rf ~/.config/smrtr/themes/ethereal
  ln -nfs ~/.local/share/smrtr/themes/ethereal ~/.config/smrtr/themes/
fi
