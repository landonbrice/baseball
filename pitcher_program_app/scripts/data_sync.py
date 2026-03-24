"""Auto-sync pitcher data to GitHub from Railway via the GitHub REST API.

No git CLI needed — uses HTTP PUT to update files directly via the
GitHub Contents API. Each dirty file is pushed individually.

Requires GITHUB_TOKEN env var with Contents read/write on the repo.
No-ops gracefully if not configured (local dev, missing token, etc).
"""

import base64
import json
import logging
import os
import threading
import time
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

_dirty_files: set[str] = set()
_lock = threading.Lock()
_started = False

SYNC_INTERVAL = 60  # seconds between sync checks
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_SLUG = os.environ.get("GITHUB_REPO", "landonbrice/baseball")
BRANCH = "main"

# Base path on Railway — files are at /app/pitcher_program_app/...
# We need to convert absolute paths to repo-relative paths
_APP_ROOT = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/app")


def mark_dirty(filepath: str) -> None:
    """Mark a file as needing sync to GitHub."""
    with _lock:
        _dirty_files.add(filepath)


def _is_railway() -> bool:
    """Check if we're running on Railway."""
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME"))


def _abs_to_repo_path(filepath: str) -> str | None:
    """Convert an absolute filesystem path to a repo-relative path.

    /app/pitcher_program_app/data/pitchers/landon_brice/profile.json
    → pitcher_program_app/data/pitchers/landon_brice/profile.json
    """
    # Try stripping /app/ prefix (Railway default)
    for prefix in ["/app/", _APP_ROOT.rstrip("/") + "/"]:
        if filepath.startswith(prefix):
            return filepath[len(prefix):]

    # Try finding pitcher_program_app in the path
    marker = "pitcher_program_app/"
    idx = filepath.find(marker)
    if idx >= 0:
        return filepath[idx:]

    return None


def _get_file_sha(repo_path: str) -> str | None:
    """Get the current SHA of a file in the repo (needed for updates)."""
    url = f"https://api.github.com/repos/{REPO_SLUG}/contents/{repo_path}?ref={BRANCH}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # File doesn't exist yet — will be created
        logger.warning(f"data_sync: failed to get SHA for {repo_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"data_sync: failed to get SHA for {repo_path}: {e}")
        return None


def _push_file(filepath: str, repo_path: str) -> bool:
    """Push a single file to GitHub via the Contents API."""
    try:
        with open(filepath, "rb") as f:
            content = f.read()
    except FileNotFoundError:
        return False

    encoded = base64.b64encode(content).decode("ascii")

    # Get current SHA (required for updates, not for creates)
    sha = _get_file_sha(repo_path)

    body = {
        "message": f"auto-sync: {os.path.basename(filepath)} from Railway",
        "content": encoded,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha

    url = f"https://api.github.com/repos/{REPO_SLUG}/contents/{repo_path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                return True
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")[:200]
        logger.warning(f"data_sync: push failed for {repo_path}: {e.code} {body_text}")
    except Exception as e:
        logger.warning(f"data_sync: push failed for {repo_path}: {e}")

    return False


def _sync_once() -> None:
    """Push any dirty files to GitHub."""
    with _lock:
        if not _dirty_files:
            return
        files = list(_dirty_files)
        _dirty_files.clear()

    existing = [f for f in files if os.path.exists(f)]
    if not existing:
        return

    pushed = 0
    failed = []
    for filepath in existing:
        repo_path = _abs_to_repo_path(filepath)
        if not repo_path:
            logger.warning(f"data_sync: can't resolve repo path for {filepath}")
            continue

        if _push_file(filepath, repo_path):
            pushed += 1
        else:
            failed.append(filepath)

    if pushed:
        logger.info(f"data_sync: pushed {pushed} file(s) to GitHub")
    if failed:
        logger.warning(f"data_sync: {len(failed)} file(s) failed, will retry")
        with _lock:
            _dirty_files.update(failed)


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

    if not GITHUB_TOKEN:
        logger.info("data_sync: No GITHUB_TOKEN set — sync disabled")
        _started = True
        return

    thread = threading.Thread(target=_sync_loop, daemon=True, name="data-sync")
    thread.start()
    _started = True
    logger.info(f"data_sync: background sync started (every {SYNC_INTERVAL}s, using GitHub API)")
