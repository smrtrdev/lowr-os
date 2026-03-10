# Overwrite parts of the lowr-menu with user-specific submenus.
# See $LOWR_PATH/bin/lowr-menu for functions that can be overwritten.
#
# WARNING: Overwritten functions will obviously not be updated when Lowr changes.
#
# Example of minimal system menu:
#
# show_system_menu() {
#   case $(menu "System" "  Lock\n󰐥  Shutdown") in
#   *Lock*) lowr-lock-screen ;;
#   *Shutdown*) lowr-system-shutdown ;;
#   *) back_to show_main_menu ;;
#   esac
# }
#
# Example of overriding just the about menu action: (Using zsh instead of bash (default))
#
# show_about() {
#   exec lowr-launch-or-focus-tui "zsh -c 'fastfetch; read -k 1'"
# }
