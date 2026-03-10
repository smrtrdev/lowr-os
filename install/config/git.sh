# Set identification from install inputs
if [[ -n ${LOWR_USER_NAME//[[:space:]]/} ]]; then
  git config --global user.name "$LOWR_USER_NAME"
fi

if [[ -n ${LOWR_USER_EMAIL//[[:space:]]/} ]]; then
  git config --global user.email "$LOWR_USER_EMAIL"
fi
