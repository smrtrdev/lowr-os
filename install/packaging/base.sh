# Install all base packages
mapfile -t packages < <(grep -v '^#' "$SMRTR_INSTALL/smrtr-base.packages" | grep -v '^$')
smrtr-pkg-add "${packages[@]}"
