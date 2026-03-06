# Place in ~/.claude/skills since all tools populate from there as well as their own sources
mkdir -p ~/.claude/skills
ln -s $LOWR_PATH/default/lowr-skill ~/.claude/skills/lowr
