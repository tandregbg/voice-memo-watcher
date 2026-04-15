#!/bin/bash
# install.sh — Install voice-memo-watcher as a macOS LaunchDaemon
#
# Requires: macOS, Python 3.9+, sudo (LaunchDaemon runs as root)
# The daemon runs as root to bypass Full Disk Access restrictions
# on the Voice Memos folder.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/com.voice-memo-watcher.plist.template"
PLIST_NAME="com.voice-memo-watcher.plist"
DAEMON_DIR="/Library/LaunchDaemons"

# --- Gather configuration ---

echo "voice-memo-watcher installer"
echo "============================"
echo

# Python path
DEFAULT_PYTHON="$(command -v python3 || echo "/usr/bin/python3")"
read -rp "Python 3 path [$DEFAULT_PYTHON]: " PYTHON
PYTHON="${PYTHON:-$DEFAULT_PYTHON}"

if ! "$PYTHON" -c "import sys; assert sys.version_info >= (3,9)" 2>/dev/null; then
    echo "ERROR: Python 3.9+ required"
    exit 1
fi

# Install directory (where voice_memo_watcher.py lives)
read -rp "Install directory [$SCRIPT_DIR]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$SCRIPT_DIR}"

# Source directory (Voice Memos)
DEFAULT_SOURCE="$HOME/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
read -rp "Voice Memos source [$DEFAULT_SOURCE]: " SOURCE_DIR
SOURCE_DIR="${SOURCE_DIR:-$DEFAULT_SOURCE}"

# Destination directory (required)
read -rp "Destination directory (where to copy recordings): " DEST_DIR
if [ -z "$DEST_DIR" ]; then
    echo "ERROR: Destination directory is required"
    exit 1
fi

# State file
DEFAULT_STATE="$HOME/.voice_memo_watcher_state.json"
read -rp "State file path [$DEFAULT_STATE]: " STATE_FILE
STATE_FILE="${STATE_FILE:-$DEFAULT_STATE}"

# --- Generate plist ---

echo
echo "Generating LaunchDaemon plist..."

mkdir -p "$INSTALL_DIR/logs"

PLIST_CONTENT=$(sed \
    -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
    -e "s|__SOURCE_DIR__|$SOURCE_DIR|g" \
    -e "s|__DEST_DIR__|$DEST_DIR|g" \
    -e "s|__STATE_FILE__|$STATE_FILE|g" \
    "$TEMPLATE")

PLIST_PATH="$DAEMON_DIR/$PLIST_NAME"

echo
echo "Configuration:"
echo "  Python:      $PYTHON"
echo "  Install dir: $INSTALL_DIR"
echo "  Source:      $SOURCE_DIR"
echo "  Destination: $DEST_DIR"
echo "  State file:  $STATE_FILE"
echo "  Plist:       $PLIST_PATH"
echo

read -rp "Install and start the daemon? [y/N]: " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
    echo "Aborted."
    exit 0
fi

# --- Install ---

echo "Installing (requires sudo)..."

# Unload if already loaded
sudo launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Write plist
echo "$PLIST_CONTENT" | sudo tee "$PLIST_PATH" > /dev/null
sudo chmod 644 "$PLIST_PATH"
sudo chown root:wheel "$PLIST_PATH"

# Load
sudo launchctl load "$PLIST_PATH"

echo
echo "Installed and started. Verify with:"
echo "  sudo launchctl list | grep voice-memo"
echo "  tail -f $INSTALL_DIR/logs/out.log"
