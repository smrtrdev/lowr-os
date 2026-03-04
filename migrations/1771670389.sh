echo "Add Logout option to system menu"

smrtr-refresh-sddm

if [[ -f /etc/sddm.conf.d/autologin.conf ]]; then
  sudo sed -i 's/^Current=.*/Current=smrtr/' /etc/sddm.conf.d/autologin.conf
fi
