"""Auto-sync pitcher data to GitHub from Railway.

Whenever pitcher data is written (profile, log, context, plans), the
file is marked dirty. A background thread checks every 60 seconds and
pushes any changes to the GitHub repo via git commit + push.

This means Railway redeploys always start with the latest data because
it's been pushed back to the repo between deploys.

Requires GITHUB_TOKEN env var with Contents read/write on the repo.
No-ops gracefully if not configured (local dev, missing token, etc).
"""

import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

_dirty_files: set[str] = set()
_lock = threading.Lock()
_started = False

SYNC_INTERVAL = 60  # seconds between sync checks
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_SLUG = os.environ.get("GITHUB_REPO", "landonbrice/baseball")


def mark_dirty(filepath: str) -> None:
    """Mark a file as needing sync to GitHub."""
    with _lock:
        _dirty_files.add(filepath)


def _is_railway() -> bool:
    """Check if we're running on Railway."""
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME"))


def _find_repo_root() -> str | None:
    """Find the git repo root, or None if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _configure_git() -> bool:
    """Configure git for pushing. Returns True if successful."""
    if not GITHUB_TOKEN:
        logger.info("data_sync: No GITHUB_TOKEN set — sync disabled")
        return False

    try:
        # Check if we're in a git repo; if not, init one
        repo_root = _find_repo_root()
        if not repo_root:
            # Railway nixpacks may strip .git — init a fresh repo
            subprocess.run(["git", "init"], capture_output=True, check=True)
            subprocess.run(["git", "add", "."], capture_output=True, check=True, timeout=30)
            subprocess.run(
                ["git", "commit", "-m", "init: Railway baseline"],
                capture_output=True, check=True, timeout=15,
            )
            logger.info("data_sync: initialized fresh git repo")

        # Set git identity for commits
        subprocess.run(
            ["git", "config", "user.email", "bot@uchi-pitcher.railway.app"],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Pitcher Bot (Railway)"],
            capture_output=True, check=True,
        )

        # Set remote URL with token auth
        remote_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{REPO_SLUG}.git"

        # Add or update remote
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
        )
        if result.returncode == 0:
            subprocess.run(
                ["git", "remote", "set-url", "origin", remote_url],
                capture_output=True, check=True,
            )
        else:
            subprocess.run(
                ["git", "remote", "add", "origin", remote_url],
                capture_output=True, check=True,
            )

        # Fetch so we can push (need common history)
        subprocess.run(
            ["git", "fetch", "origin", "main"],
            capture_output=True, timeout=30,
        )

        # Try to set upstream tracking
        subprocess.run(
            ["git", "branch", "--set-upstream-to=origin/main", "main"],
            capture_output=True,
        )

        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"data_sync: git config failed: {e}")
        return False


def _sync_once() -> None:
    """Commit and push any dirty files."""
    with _lock:
        if not _dirty_files:
            return
        files = list(_dirty_files)
        _dirty_files.clear()

    # Filter to files that actually exist and are within the repo
    existing = [f for f in files if os.path.exists(f)]
    if not existing:
        return

    try:
        # Pull first to avoid conflicts (fast-forward only, ignore errors)
        subprocess.run(
            ["git", "pull", "--ff-only", "--no-rebase", "origin", "main"],
            capture_output=True, timeout=30,
        )  # OK if this fails (no tracking, diverged, etc)

        # Stage only pitcher data files
        subprocess.run(
            ["git", "add"] + existing,
            capture_output=True, check=True, timeout=15,
        )

        # Check if there's actually anything to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True,
        )
        if result.returncode == 0:
            # No changes staged
            return

        # Commit
        file_count = len(existing)
        subprocess.run(
            ["git", "commit", "-m", f"auto-sync: {file_count} data file(s) from Railway"],
            capture_output=True, check=True, timeout=15,
        )

        # Push
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"data_sync: pushed {file_count} file(s) to GitHub")
        else:
            stderr = result.stderr.decode(errors="replace")
            logger.warning(f"data_sync: push failed: {stderr}")
            # Re-mark files as dirty so they get retried
            with _lock:
                _dirty_files.update(existing)

    except subprocess.TimeoutExpired:
        logger.warning("data_sync: git operation timed out")
        with _lock:
            _dirty_files.update(existing)
    except Exception as e:
        logger.warning(f"data_sync: sync failed: {e}")
        with _lock:
            _dirty_files.update(existing)


def _sync_loop() -> None:
    """Background loop that syncs dirty files periodically."""
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            _sync_once()
        except Exception as e:
            logger.error(f"data_sync: unexpected error in sync loop: {e}")


def start_sync() -> None:
    """Start the background sync thread. Call once at app startup."""
    global _started
    if _started:
        return

    if not _is_railway():
        logger.info("data_sync: Not on Railway — sync disabled")
        _started = True
        return

    if not _configure_git():
        _started = True
        return

    thread = threading.Thread(target=_sync_loop, daemon=True, name="data-sync")
    thread.start()
    _started = True
    logger.info(f"data_sync: background sync started (every {SYNC_INTERVAL}s)")
