echo "Move Smrtr Package Repository after Arch core/extra/multilib and remove AUR"

smrtr-refresh-pacman
sudo pacman -Syu --noconfirm
