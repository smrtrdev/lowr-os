# Copy over Smrtr configs
mkdir -p ~/.config
cp -R ~/.local/share/smrtr/config/* ~/.config/

# Use default bashrc from Smrtr
cp ~/.local/share/smrtr/default/bashrc ~/.bashrc
