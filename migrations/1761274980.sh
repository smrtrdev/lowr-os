echo "Migrate to proper packages for localsend and asdcontrol"

if smrtr-pkg-present localsend-bin; then
  smrtr-pkg-drop localsend-bin
  smrtr-pkg-add localsend
fi

if smrtr-pkg-present asdcontrol-git; then
  smrtr-pkg-drop asdcontrol-git
  smrtr-pkg-add asdcontrol
fi
