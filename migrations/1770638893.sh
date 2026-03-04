echo "Add Tmux as an option with themed styling"

smrtr-pkg-add tmux

if [[ ! -f ~/.config/tmux/tmux.conf ]]; then
  mkdir -p ~/.config/tmux
  cp $SMRTR_PATH/config/tmux/tmux.conf ~/.config/tmux/tmux.conf
  smrtr-theme-refresh
fi
