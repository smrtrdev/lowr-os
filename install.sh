#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -eEo pipefail

# Define Smrtr locations
export SMRTR_PATH="$HOME/.local/share/smrtr"
export SMRTR_INSTALL="$SMRTR_PATH/install"
export SMRTR_INSTALL_LOG_FILE="/var/log/smrtr-install.log"
export PATH="$SMRTR_PATH/bin:$PATH"

# Install
source "$SMRTR_INSTALL/helpers/all.sh"
source "$SMRTR_INSTALL/preflight/all.sh"
source "$SMRTR_INSTALL/packaging/all.sh"
source "$SMRTR_INSTALL/config/all.sh"
source "$SMRTR_INSTALL/login/all.sh"
source "$SMRTR_INSTALL/post-install/all.sh"
