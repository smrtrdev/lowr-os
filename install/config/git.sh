# Set identification from install inputs
if [[ -n ${SMRTR_USER_NAME//[[:space:]]/} ]]; then
  git config --global user.name "$SMRTR_USER_NAME"
fi

if [[ -n ${SMRTR_USER_EMAIL//[[:space:]]/} ]]; then
  git config --global user.email "$SMRTR_USER_EMAIL"
fi
