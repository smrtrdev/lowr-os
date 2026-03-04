#!/usr/bin/env bash
# Refactor: replace all occurrences of 'omarchy' (and case variants) with 'smrtr'
# in file contents and file/directory names within this repository.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF="$(basename "${BASH_SOURCE[0]}")"

echo "==> Repo: $REPO_DIR"
echo ""

# ---------------------------------------------------------------------------
# 1. Replace in file contents (text files only, skip binary and self)
# ---------------------------------------------------------------------------
echo "--- Step 1: Replacing content in text files ---"

while IFS= read -r -d '' file; do
  # Skip this script itself
  [[ "$(basename "$file")" == "$SELF" ]] && continue

  # Skip binary files
  if ! file --mime "$file" | grep -q "text/"; then
    continue
  fi

  if grep -qiP "omarchy" "$file" 2>/dev/null; then
    # Order matters: do capitalised variants before lowercase
    sed -i \
      -e 's/Omarchy/Smrtr/g' \
      -e 's/OMARCHY/SMRTR/g' \
      -e 's/omarchy/smrtr/g' \
      "$file"
    echo "  content: $file"
  fi
done < <(find "$REPO_DIR" -type f -print0)

echo ""

# ---------------------------------------------------------------------------
# 2. Rename files and directories (deepest first to avoid path conflicts)
# ---------------------------------------------------------------------------
echo "--- Step 2: Renaming files and directories ---"

# Process deepest paths first so parent renames don't break child paths
while IFS= read -r path; do
  base="$(basename "$path")"
  dir="$(dirname "$path")"
  newbase="${base//omarchy/smrtr}"
  newbase="${newbase//Omarchy/Smrtr}"
  newbase="${newbase//OMARCHY/SMRTR}"

  if [[ "$newbase" != "$base" ]]; then
    mv -- "$path" "$dir/$newbase"
    echo "  rename: $path  ->  $dir/$newbase"
  fi
done < <(find "$REPO_DIR" \( -type f -o -type d \) -iname "*omarchy*" | sort -r)

echo ""
echo "==> Done."
