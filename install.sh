#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -eEo pipefail

# Define Lowr locations
export LOWR_PATH="$HOME/.local/share/lowr"
export LOWR_INSTALL="$LOWR_PATH/install"
export LOWR_INSTALL_LOG_FILE="/var/log/lowr-install.log"
export PATH="$LOWR_PATH/bin:$PATH"

# Install
source "$LOWR_INSTALL/helpers/all.sh"
source "$LOWR_INSTALL/preflight/all.sh"
source "$LOWR_INSTALL/packaging/all.sh"
source "$LOWR_INSTALL/config/all.sh"
source "$LOWR_INSTALL/login/all.sh"
source "$LOWR_INSTALL/post-install/all.sh"
