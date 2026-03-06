# Install all base packages
mapfile -t packages < <(grep -v '^#' "$LOWR_INSTALL/lowr-base.packages" | grep -v '^$')
lowr-pkg-add "${packages[@]}"
