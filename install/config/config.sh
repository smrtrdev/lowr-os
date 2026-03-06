# Copy over Lowr configs
mkdir -p ~/.config
cp -R ~/.local/share/lowr/config/* ~/.config/

# Use default bashrc from Lowr
cp ~/.local/share/lowr/default/bashrc ~/.bashrc
