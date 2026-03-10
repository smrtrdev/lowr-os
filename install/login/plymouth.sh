if [[ $(plymouth-set-default-theme) != "lowr" ]]; then
  sudo cp -r "$HOME/.local/share/lowr/default/plymouth" /usr/share/plymouth/themes/lowr/
  sudo plymouth-set-default-theme lowr
fi
