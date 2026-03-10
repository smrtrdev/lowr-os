LOWR_MIGRATIONS_STATE_PATH=~/.local/state/lowr/migrations
mkdir -p $LOWR_MIGRATIONS_STATE_PATH

for file in ~/.local/share/lowr/migrations/*.sh; do
  touch "$LOWR_MIGRATIONS_STATE_PATH/$(basename "$file")"
done
