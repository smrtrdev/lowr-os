if [[ $(plymouth-set-default-theme) != "smrtr" ]]; then
  sudo cp -r "$HOME/.local/share/smrtr/default/plymouth" /usr/share/plymouth/themes/smrtr/
  sudo plymouth-set-default-theme smrtr
fi
