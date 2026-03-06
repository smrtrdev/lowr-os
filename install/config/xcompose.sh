# Set default XCompose that is triggered with CapsLock
tee ~/.XCompose >/dev/null <<EOF
# Run lowr-restart-xcompose to apply changes

# Include fast emoji access
include "%H/.local/share/lowr/default/xcompose"

# Identification
<Multi_key> <space> <n> : "$LOWR_USER_NAME"
<Multi_key> <space> <e> : "$LOWR_USER_EMAIL"
EOF
