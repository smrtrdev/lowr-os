SMRTR_MIGRATIONS_STATE_PATH=~/.local/state/smrtr/migrations
mkdir -p $SMRTR_MIGRATIONS_STATE_PATH

for file in ~/.local/share/smrtr/migrations/*.sh; do
  touch "$SMRTR_MIGRATIONS_STATE_PATH/$(basename "$file")"
done
