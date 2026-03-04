echo "Make new Osaka Jade theme available as new default"

if [[ ! -L ~/.config/smrtr/themes/osaka-jade ]]; then
  rm -rf ~/.config/smrtr/themes/osaka-jade
  git -C ~/.local/share/smrtr checkout -f themes/osaka-jade
  ln -nfs ~/.local/share/smrtr/themes/osaka-jade ~/.config/smrtr/themes/osaka-jade
fi
