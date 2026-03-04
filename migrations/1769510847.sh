echo "Switch back to mainline chromium now that it supports full live themeing"

if smrtr-pkg-present smrtr-chromium; then
  if gum confirm "Ready to switch to mainstream chromium? (Will close Chromium + reset settings)"; then
    pkill -x chromium
    smrtr-pkg-drop smrtr-chromium
    smrtr-pkg-add chromium
    smrtr-theme-set-browser
  fi
fi
