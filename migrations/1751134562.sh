echo "Ensure all indexes and packages are up to date"

smrtr-update-keyring
smrtr-refresh-pacman
sudo pacman -Syu --noconfirm
