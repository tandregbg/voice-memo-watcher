# Changelog

## 1.0.0 — 2026-04-15

- Open-sourced and published to GitHub
- Parameterised configuration via environment variables (`VMW_SOURCE_DIR`, `VMW_DEST_DIR`, `VMW_STATE_FILE`, `VMW_POLL_INTERVAL`)
- Added interactive `install.sh` installer
- Added plist template for clean LaunchDaemon setup
- Removed all hardcoded paths from published code

## 0.2.0 — 2026-03-30

- Verified stable operation — 748 recordings tracked in state file
- Confirmed reliable iCloud sync pickup and rename pipeline

## 0.1.0 — 2026-02-13

- Initial implementation as a Python LaunchDaemon (replaces deep-thought-trillian bash script)
- Polls Voice Memos folder every 30 seconds
- Renames recordings from `YYYYMMDD HHMMSS-HEXID.m4a` to `YYMMDD_HHMMSS.m4a`
- Copies to configurable destination directory
- JSON state file tracks processed recordings to avoid duplicates
- Collision handling for same-second recordings
- First-run initialization indexes existing files without copying
- Runs as root via LaunchDaemon to bypass Full Disk Access restrictions
