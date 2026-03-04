echo "Change smrtr-screenrecord to use gpu-screen-recorder"
smrtr-pkg-drop wf-recorder wl-screenrec

# Add slurp in case it hadn't been picked up from an old migration
smrtr-pkg-add slurp gpu-screen-recorder
