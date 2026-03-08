# Install a niri-uwsm wayland session that starts niri via uwsm,
# so that ~/.config/uwsm/env is processed and the session environment
# (e.g. PATH) is correctly set up before niri starts.

sudo mkdir -p /usr/local/share/wayland-sessions
cat <<EOF | sudo tee /usr/local/share/wayland-sessions/niri-uwsm.desktop
[Desktop Entry]
Name=Niri (uwsm-managed)
Comment=A scrollable-tiling Wayland compositor
Exec=uwsm start -e -D niri niri.desktop
TryExec=uwsm
DesktopNames=niri
Type=Application
EOF
