echo "Change to smrtr-nvim package"
smrtr-pkg-drop smrtr-lazyvim
smrtr-pkg-add smrtr-nvim

# Will trigger to overwrite configs or not to pickup new hot-reload themes
smrtr-nvim-setup
