echo "Add icon theme coloring"

if ! pacman -Q yaru-icon-theme &>/dev/null; then
  sudo pacman -S --noconfirm yaru-icon-theme

  if [[ -f ~/.config/smrtr/current/theme/icons.theme ]]; then
    gsettings set org.gnome.desktop.interface icon-theme "$(<~/.config/smrtr/current/theme/icons.theme)"
  fi
fi
