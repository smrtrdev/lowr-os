# Show installation environment variables
gum log --level info "Installation Environment:"

env | grep -E "^(SMRTR_CHROOT_INSTALL|SMRTR_ONLINE_INSTALL|SMRTR_USER_NAME|SMRTR_USER_EMAIL|USER|HOME|SMRTR_REPO|SMRTR_REF|SMRTR_PATH)=" | sort | while IFS= read -r var; do
  gum log --level info "  $var"
done
