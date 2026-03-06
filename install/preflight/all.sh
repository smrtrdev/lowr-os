source $LOWR_INSTALL/preflight/guard.sh
source $LOWR_INSTALL/preflight/begin.sh
run_logged $LOWR_INSTALL/preflight/show-env.sh
run_logged $LOWR_INSTALL/preflight/pacman.sh
run_logged $LOWR_INSTALL/preflight/migrations.sh
run_logged $LOWR_INSTALL/preflight/first-run-mode.sh
run_logged $LOWR_INSTALL/preflight/disable-mkinitcpio.sh
