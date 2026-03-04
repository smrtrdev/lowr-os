echo "Add opencode with system themeing"

smrtr-pkg-add opencode

# Add config using smrtr theme by default
if [[ ! -f ~/.config/opencode/opencode.json ]]; then
  mkdir -p ~/.config/opencode
  cp $SMRTR_PATH/config/opencode/opencode.json ~/.config/opencode/opencode.json
fi
