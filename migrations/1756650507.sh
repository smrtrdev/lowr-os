echo "Fix JetBrains font setting"

if [[ $(smrtr-font-current) == JetBrains* ]]; then
  smrtr-font-set "JetBrainsMono Nerd Font"
fi
