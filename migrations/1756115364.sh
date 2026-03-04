echo "Replace buggy native Zoom client with webapp"

if smrtr-pkg-present zoom; then
  smrtr-pkg-drop zoom
  smrtr-webapp-install "Zoom" https://app.zoom.us/wc/home https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/zoom.png
fi
