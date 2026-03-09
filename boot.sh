#!/bin/bash

# Set install mode to online since boot.sh is used for curl installations
export LOWR_ONLINE_INSTALL=true

ansi_art='
 ▄▄   ▄▄▄▄   ▄▄      ▄▄ ▄▄▄▄▄▄▄
 ██ ▄██▀▀██▄ ██  ▄▄  ██ ██▀▀▀▀██
 ██ ██    ██ ▀█▄ ██ ▄█▀ ██    ██
 ██ ██▄  ▄██  ████████  ██████▀
 ██  ▀████▀   ▀██  ██▀  ██  ▀██
 ██▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄██    ██
 ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    ▀▀
'

clear
echo -e "\n$ansi_art\n"

# Use custom branch if instructed, otherwise default to main
LOWR_REF="${LOWR_REF:-dev}"

# Set mirror based on branch
if [[ $LOWR_REF == "dev" ]]; then
  export LOWR_MIRROR=edge
  echo 'Server = https://mirror.omarchy.org/$repo/os/$arch' | sudo tee /etc/pacman.d/mirrorlist >/dev/null
elif [[ $LOWR_REF == "rc" ]]; then
  export LOWR_MIRROR=rc
  echo 'Server = https://rc-mirror.omarchy.org/$repo/os/$arch' | sudo tee /etc/pacman.d/mirrorlist >/dev/null
else
  export LOWR_MIRROR=stable
  echo 'Server = https://stable-mirror.omarchy.org/$repo/os/$arch' | sudo tee /etc/pacman.d/mirrorlist >/dev/null
fi

sudo pacman -Syu --noconfirm --needed git

# Use custom repo if specified, otherwise default to smrtr/lowr-os
LOWR_REPO="${LOWR_REPO:-smrtr/lowr-os}"

echo -e "\nCloning Lowr from: https://codeberg.org/${LOWR_REPO}.git"
rm -rf ~/.local/share/lowr/
git clone "https://codeberg.org/${LOWR_REPO}.git" ~/.local/share/lowr >/dev/null

echo -e "\e[32mUsing branch: $LOWR_REF\e[0m"
cd ~/.local/share/lowr
git fetch origin "${LOWR_REF}" && git checkout "${LOWR_REF}"
cd -

echo -e "\nInstallation starting..."
source ~/.local/share/lowr/install.sh
