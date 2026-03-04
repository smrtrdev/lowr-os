# Overwrite parts of the smrtr-menu with user-specific submenus.
# See $SMRTR_PATH/bin/smrtr-menu for functions that can be overwritten.
#
# WARNING: Overwritten functions will obviously not be updated when Smrtr changes.
#
# Example of minimal system menu:
#
# show_system_menu() {
#   case $(menu "System" "  Lock\n󰐥  Shutdown") in
#   *Lock*) smrtr-lock-screen ;;
#   *Shutdown*) smrtr-system-shutdown ;;
#   *) back_to show_main_menu ;;
#   esac
# }
#
# Example of overriding just the about menu action: (Using zsh instead of bash (default))
#
# show_about() {
#   exec smrtr-launch-or-focus-tui "zsh -c 'fastfetch; read -k 1'"
# }
