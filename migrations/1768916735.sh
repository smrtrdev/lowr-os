echo "Fix microphone gain and audio mixing on Asus ROG laptops"

source "$SMRTR_PATH/install/config/hardware/fix-asus-rog-mic.sh"
source "$SMRTR_PATH/install/config/hardware/fix-asus-rog-audio-mixer.sh"

if smrtr-hw-asus-rog; then
  smrtr-restart-pipewire
fi
