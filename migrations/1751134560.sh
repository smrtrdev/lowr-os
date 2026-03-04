echo "Add UWSM env"

export SMRTR_PATH="$HOME/.local/share/smrtr"
export PATH="$SMRTR_PATH/bin:$PATH"

mkdir -p "$HOME/.config/uwsm/"
cat <<EOF | tee "$HOME/.config/uwsm/env"
export SMRTR_PATH=$HOME/.local/share/smrtr
export PATH=$SMRTR_PATH/bin/:$PATH
EOF

# Ensure we have the latest repos and are ready to pull
smrtr-update-keyring
smrtr-refresh-pacman
sudo systemctl restart systemd-timesyncd
sudo pacman -Sy # Normally not advisable, but we'll do a full -Syu before finishing

mkdir -p ~/.local/state/smrtr/migrations
touch ~/.local/state/smrtr/migrations/1751134560.sh

# Remove old AUR packages to prevent a super lengthy build on old Smrtr installs
smrtr-pkg-drop zoom qt5-remoteobjects wf-recorder wl-screenrec

# Get rid of old AUR packages
bash $SMRTR_PATH/migrations/1756060611.sh
touch ~/.local/state/smrtr/migrations/1756060611.sh

bash smrtr-update-perform
