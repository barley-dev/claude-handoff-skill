#!/usr/bin/env bash
# Install the handoff skills into ~/.claude/skills/ as symlinks,
# so that `git pull` in this repo keeps them current.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

mkdir -p "$SKILLS_DIR"

install_one() {
    local name="$1"
    local src="$REPO_DIR/skills/$name"
    local dest="$SKILLS_DIR/$name"

    if [ ! -d "$src" ]; then
        echo "  ✗ $name — source not found at $src" >&2
        return 1
    fi

    if [ -L "$dest" ]; then
        local current
        current="$(readlink "$dest")"
        if [ "$current" = "$src" ]; then
            echo "  = $name — already linked, nothing to do"
            return 0
        fi
        echo "  ! $name — a different symlink exists:"
        echo "      $dest -> $current"
        read -r -p "    Replace it? [y/N] " reply
        case "$reply" in
            [yY]*) rm "$dest" ;;
            *) echo "    skipped"; return 0 ;;
        esac
    elif [ -e "$dest" ]; then
        echo "  ! $name — a real directory/file already exists at:"
        echo "      $dest"
        echo "    Not touching it. Move or remove it first, then re-run."
        return 0
    fi

    ln -s "$src" "$dest"
    echo "  ✓ $name -> $dest"
}

echo "Installing handoff skills into $SKILLS_DIR"
install_one handoff
install_one handoff-zh

echo
echo "Done. Restart Claude Code (or run /skills) to pick them up."
echo "Trigger with:  handoff   (English)   /   交接   (Chinese)"
