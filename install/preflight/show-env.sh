# Show installation environment variables
gum log --level info "Installation Environment:"

env | grep -E "^(LOWR_CHROOT_INSTALL|LOWR_ONLINE_INSTALL|LOWR_USER_NAME|LOWR_USER_EMAIL|USER|HOME|LOWR_REPO|LOWR_REF|LOWR_PATH)=" | sort | while IFS= read -r var; do
  gum log --level info "  $var"
done
