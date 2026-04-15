#!/usr/bin/env python3
"""
Voice Memo Watcher Service

Monitors macOS Voice Memos folder and copies new recordings
to Dropbox with reformatted filenames.

Runs as a LaunchDaemon with continuous polling.
"""

import os
import sys
import time
import re
import shutil
import json
import signal
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Set

# Configuration via environment variables (set in LaunchDaemon plist)
SOURCE_DIR = Path(os.environ.get(
    "VMW_SOURCE_DIR",
    Path.home() / "Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings",
))
DEST_DIR_ENV = os.environ.get("VMW_DEST_DIR")
if not DEST_DIR_ENV:
    print("ERROR: VMW_DEST_DIR environment variable is required", file=sys.stderr)
    sys.exit(1)
DEST_DIR = Path(DEST_DIR_ENV)
STATE_FILE = Path(os.environ.get(
    "VMW_STATE_FILE",
    Path.home() / ".voice_memo_watcher_state.json",
))
POLL_INTERVAL = int(os.environ.get("VMW_POLL_INTERVAL", "30"))
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Global state
shutdown_requested = False
logger = None


def setup_logging() -> logging.Logger:
    """Configure logging to stdout (captured by LaunchDaemon log paths)."""
    log = logging.getLogger('voice-memo-watcher')
    log.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    log.addHandler(handler)

    return log


def handle_shutdown(signum, frame):
    """Handle graceful shutdown signals."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def load_processed_files() -> Set[str]:
    """Load set of already processed source filenames."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get('processed', []))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load state file: {e}")
    return set()


def save_processed_files(processed: Set[str]) -> None:
    """Save processed filenames to state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'processed': list(processed),
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save state file: {e}")


def parse_voice_memo_filename(filename: str) -> Optional[datetime]:
    """
    Parse Voice Memo filename to extract datetime.

    Expected format: YYYYMMDD HHMMSS-HEXID.m4a
    Example: 20250423 142214-A710AEFE.m4a
    """
    # Pattern: 8 digits (date), space, 6 digits (time), dash, hex ID
    pattern = r'^(\d{8})\s+(\d{6})-[A-F0-9]+\.m4a$'
    match = re.match(pattern, filename, re.IGNORECASE)

    if not match:
        return None

    date_str, time_str = match.groups()

    try:
        return datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
    except ValueError:
        return None


def generate_dest_filename(dt: datetime) -> str:
    """
    Generate destination filename in YYMMDD_HHMMSS.m4a format.

    Example: 250213_143022.m4a
    """
    return dt.strftime("%y%m%d_%H%M%S.m4a")


def check_permissions() -> bool:
    """Verify read access to Voice Memos folder."""
    if not SOURCE_DIR.exists():
        logger.error(f"Source directory does not exist: {SOURCE_DIR}")
        return False

    try:
        list(SOURCE_DIR.iterdir())
        return True
    except PermissionError:
        logger.error(
            f"Permission denied accessing {SOURCE_DIR}. "
            "Grant Full Disk Access to Python in System Settings > "
            "Privacy & Security > Full Disk Access"
        )
        return False


def check_destination() -> bool:
    """Verify destination directory is accessible and writable."""
    if not DEST_DIR.exists():
        logger.error(f"Destination directory does not exist: {DEST_DIR}")
        logger.info("Is the network volume mounted?")
        return False

    # Check write permission
    test_file = DEST_DIR / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
        return True
    except (PermissionError, OSError) as e:
        logger.error(f"Cannot write to destination: {e}")
        return False


def process_new_files(processed: Set[str]) -> Set[str]:
    """
    Scan for new Voice Memos and copy to destination.
    Returns updated set of processed files.
    """
    if not check_permissions() or not check_destination():
        return processed

    new_processed = set()

    for file_path in SOURCE_DIR.glob("*.m4a"):
        filename = file_path.name

        # Skip already processed
        if filename in processed:
            continue

        # Parse filename
        dt = parse_voice_memo_filename(filename)
        if dt is None:
            logger.warning(f"Skipping unparseable filename: {filename}")
            new_processed.add(filename)  # Mark as processed to avoid repeated warnings
            continue

        # Generate destination filename
        dest_filename = generate_dest_filename(dt)
        dest_path = DEST_DIR / dest_filename

        # Handle collision (same timestamp)
        if dest_path.exists():
            # Check if same file (by size)
            if file_path.stat().st_size == dest_path.stat().st_size:
                logger.info(f"Already exists (same size), skipping: {dest_filename}")
                new_processed.add(filename)
                continue

            # Different file, add suffix
            counter = 1
            while dest_path.exists():
                base = dt.strftime("%y%m%d_%H%M%S")
                dest_filename = f"{base}_{counter}.m4a"
                dest_path = DEST_DIR / dest_filename
                counter += 1

        # Copy file
        try:
            logger.info(f"Copying: {filename} -> {dest_filename}")
            shutil.copy2(file_path, dest_path)
            new_processed.add(filename)
            logger.info(f"Successfully copied: {dest_filename}")
        except (IOError, OSError) as e:
            logger.error(f"Failed to copy {filename}: {e}")

    return processed | new_processed


def initialize_existing_files() -> Set[str]:
    """
    Initialize state with existing files to avoid copying old files.
    Called on first run to "catch up" with existing state.
    """
    existing = set()

    if not SOURCE_DIR.exists():
        return existing

    try:
        for file_path in SOURCE_DIR.glob("*.m4a"):
            existing.add(file_path.name)
        logger.info(f"Initialized with {len(existing)} existing voice memos")
    except PermissionError:
        logger.error("Permission denied during initialization")

    return existing


def main():
    """Main service loop."""
    global logger, shutdown_requested
    logger = setup_logging()

    # Setup signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    logger.info("Voice Memo Watcher starting...")
    logger.info(f"Source: {SOURCE_DIR}")
    logger.info(f"Destination: {DEST_DIR}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")

    # Load or initialize state
    processed = load_processed_files()

    if not processed:
        # First run - initialize with existing files
        # This prevents copying all historical files
        logger.info("First run detected, initializing state...")
        processed = initialize_existing_files()
        save_processed_files(processed)

    logger.info(f"Tracking {len(processed)} processed files")

    # Main loop
    while not shutdown_requested:
        try:
            processed = process_new_files(processed)
            save_processed_files(processed)
        except Exception as e:
            logger.error(f"Error in processing loop: {e}")

        # Sleep with interrupt checking
        for _ in range(POLL_INTERVAL):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Voice Memo Watcher stopped")


if __name__ == "__main__":
    main()
