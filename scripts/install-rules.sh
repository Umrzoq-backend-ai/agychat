#!/bin/bash
# Standalone installer for Antigravity AI rules from AgyChat

RULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../agychat/rules" && pwd)"
TARGET_DIR="$HOME/.gemini/config/rules"

mkdir -p "$TARGET_DIR"

for file in "$RULES_DIR"/*.md; do
    [ -e "$file" ] || continue
    filename=$(basename "$file")
    ln -sf "$file" "$TARGET_DIR/$filename"
    echo "Symlinked $filename -> $TARGET_DIR/$filename"
done

echo "Done! Restart your Antigravity / Gemini AI agent to apply the new rules."
