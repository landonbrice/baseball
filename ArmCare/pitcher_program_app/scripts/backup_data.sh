#!/usr/bin/env bash
# backup_data.sh — Download pitcher data from Railway and commit to repo.
# Run after each day of real usage to prevent data loss on redeploy.
#
# Prerequisites: railway CLI installed + authenticated
# Usage: bash scripts/backup_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data/pitchers"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)

echo "=== Pitcher Data Backup: $TIMESTAMP ==="

# Download pitcher data from the running Railway container
echo "Downloading pitcher data from Railway..."
cd "$PROJECT_DIR"

# Use railway run to cat each pitcher's files and overwrite local copies
for pitcher_dir in $(railway run -- ls data/pitchers/ 2>/dev/null); do
    # Skip example files
    if [[ "$pitcher_dir" == example_* ]]; then
        continue
    fi

    echo "  Backing up: $pitcher_dir"
    mkdir -p "$DATA_DIR/$pitcher_dir"

    for file in profile.json context.md daily_log.json saved_plans.json; do
        railway run -- cat "data/pitchers/$pitcher_dir/$file" 2>/dev/null \
            > "$DATA_DIR/$pitcher_dir/$file" || true
    done
done

# Show what changed
echo ""
echo "=== Changes ==="
git diff --stat -- data/pitchers/

# Prompt to commit
echo ""
read -rp "Commit and push? [y/N] " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    git add data/pitchers/
    git commit -m "backup: pitcher data $TIMESTAMP"
    git push
    echo "Pushed to remote."
else
    echo "Changes staged but not committed. Run 'git add data/pitchers/' when ready."
fi
