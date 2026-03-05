#!/bin/bash

# Set install mode to online since boot.sh is used for curl installations
export SMRTR_ONLINE_INSTALL=true

ansi_art='                 ▄▄▄
 ▄█████▄    ▄███████████▄    ▄███████   ▄███████   ▄███████   ▄█   █▄    ▄█   █▄
███   ███  ███   ███   ███  ███   ███  ███   ███  ███   ███  ███   ███  ███   ███
███   ███  ███   ███   ███  ███   ███  ███   ███  ███   █▀   ███   ███  ███   ███
███   ███  ███   ███   ███ ▄███▄▄▄███ ▄███▄▄▄██▀  ███       ▄███▄▄▄███▄ ███▄▄▄███
███   ███  ███   ███   ███ ▀███▀▀▀███ ▀███▀▀▀▀    ███      ▀▀███▀▀▀███  ▀▀▀▀▀▀███
███   ███  ███   ███   ███  ███   ███ ██████████  ███   █▄   ███   ███  ▄██   ███
███   ███  ███   ███   ███  ███   ███  ███   ███  ███   ███  ███   ███  ███   ███
 ▀█████▀    ▀█   ███   █▀   ███   █▀   ███   ███  ███████▀   ███   █▀    ▀█████▀
                                       ███   █▀                                  '

clear
echo -e "\n$ansi_art\n"

# Use custom branch if instructed, otherwise default to main
SMRTR_REF="${SMRTR_REF:-main}"

# Set mirror based on branch
if [[ $SMRTR_REF == "dev" ]]; then
  export SMRTR_MIRROR=edge
  echo 'Server = https://mirror.omarchy.org/$repo/os/$arch' | sudo tee /etc/pacman.d/mirrorlist >/dev/null
elif [[ $SMRTR_REF == "rc" ]]; then
  export SMRTR_MIRROR=rc
  echo 'Server = https://rc-mirror.omarchy.org/$repo/os/$arch' | sudo tee /etc/pacman.d/mirrorlist >/dev/null
else
  export SMRTR_MIRROR=stable
  echo 'Server = https://stable-mirror.omarchy.org/$repo/os/$arch' | sudo tee /etc/pacman.d/mirrorlist >/dev/null
fi

sudo pacman -Syu --noconfirm --needed git

# Use custom repo if specified, otherwise default to smrtr/smrtr-os
SMRTR_REPO="${SMRTR_REPO:-smrtr/smrtr-os}"

echo -e "\nCloning Smrtr from: https://codeberg.org/${SMRTR_REPO}.git"
rm -rf ~/.local/share/smrtr/
git clone "https://codeberg.org/${SMRTR_REPO}.git" ~/.local/share/smrtr >/dev/null

echo -e "\e[32mUsing branch: $SMRTR_REF\e[0m"
cd ~/.local/share/smrtr
git fetch origin "${SMRTR_REF}" && git checkout "${SMRTR_REF}"
cd -

echo -e "\nInstallation starting..."
source ~/.local/share/smrtr/install.sh
