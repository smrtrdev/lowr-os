echo "Make hackerman available as new theme"

if [[ ! -L ~/.config/smrtr/themes/hackerman ]]; then
  rm -rf ~/.config/smrtr/themes/hackerman
  ln -nfs ~/.local/share/smrtr/themes/hackerman ~/.config/smrtr/themes/
fi
