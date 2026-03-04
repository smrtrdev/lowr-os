# Place in ~/.claude/skills since all tools populate from there as well as their own sources
mkdir -p ~/.claude/skills
ln -s $SMRTR_PATH/default/smrtr-skill ~/.claude/skills/smrtr
