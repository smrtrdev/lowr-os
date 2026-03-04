source $SMRTR_INSTALL/preflight/guard.sh
source $SMRTR_INSTALL/preflight/begin.sh
run_logged $SMRTR_INSTALL/preflight/show-env.sh
run_logged $SMRTR_INSTALL/preflight/pacman.sh
run_logged $SMRTR_INSTALL/preflight/migrations.sh
run_logged $SMRTR_INSTALL/preflight/first-run-mode.sh
run_logged $SMRTR_INSTALL/preflight/disable-mkinitcpio.sh
