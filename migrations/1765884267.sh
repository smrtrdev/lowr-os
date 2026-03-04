echo "Change to openai-codex instead of openai-codex-bin"

if smrtr-pkg-present openai-codex-bin; then
    smrtr-pkg-drop openai-codex-bin
    smrtr-pkg-add openai-codex
fi
