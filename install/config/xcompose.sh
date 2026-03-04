# Set default XCompose that is triggered with CapsLock
tee ~/.XCompose >/dev/null <<EOF
# Run smrtr-restart-xcompose to apply changes

# Include fast emoji access
include "%H/.local/share/smrtr/default/xcompose"

# Identification
<Multi_key> <space> <n> : "$SMRTR_USER_NAME"
<Multi_key> <space> <e> : "$SMRTR_USER_EMAIL"
EOF
