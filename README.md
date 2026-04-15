# voice-memo-watcher

**Capture thoughts anywhere with your Apple Watch or iPhone, and have them automatically collected, renamed, and ready for transcription on your Mac.**

Voice Memos is the fastest way to capture an idea — tap your wrist, speak, done. But the recordings land in a sandboxed folder with ugly hex filenames and no easy way to process them further. This tool bridges that gap: it watches for new Voice Memos as they sync via iCloud, renames them to clean sortable timestamps (`250423_142214.m4a`), and copies them to a destination of your choice — a local folder, a network share, or a Dropbox directory where an external transcription service can pick them up.

Use it as a building block for a voice-first workflow:
- **Capture** on Apple Watch / iPhone via the built-in Voice Memos app
- **Sync** automatically to your Mac via iCloud
- **Collect** with this daemon — renamed, deduplicated, copied to your target folder
- **Transcribe** with any service that watches a folder or accepts uploads (Whisper, Deepgram, AssemblyAI, or your own pipeline)

Zero dependencies. Single Python file. Runs as a macOS LaunchDaemon.

---

## What it does

- Watches `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings` for new `.m4a` files
- Renames from `20250423 142214-A710AEFE.m4a` to `250423_142214.m4a` (YYMMDD_HHMMSS)
- Copies to a configurable destination (network share, Dropbox folder, local directory)
- Tracks processed files in a JSON state file to avoid duplicates
- Handles filename collisions (same-second recordings get a `_1`, `_2` suffix)
- Runs as a LaunchDaemon (root) to bypass Full Disk Access restrictions

## Requirements

- macOS (tested on Sonoma/Sequoia)
- Python 3.9+
- Write access to the destination directory
- `sudo` for LaunchDaemon installation

## Install

```bash
git clone https://github.com/youruser/voice-memo-watcher.git
cd voice-memo-watcher
./install.sh
```

The installer will prompt for:
- Python path (default: system `python3`)
- Destination directory (required — where recordings are copied to)
- State file location (default: `~/.voice_memo_watcher_state.json`)

## Configuration

All configuration is via environment variables, set in the LaunchDaemon plist:

| Variable | Required | Default | Description |
|---|---|---|---|
| `VMW_SOURCE_DIR` | No | `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings` | Voice Memos folder |
| `VMW_DEST_DIR` | **Yes** | — | Where to copy recordings |
| `VMW_STATE_FILE` | No | `~/.voice_memo_watcher_state.json` | Tracks processed files |
| `VMW_POLL_INTERVAL` | No | `30` | Seconds between scans |

## How it works

1. On first run, the watcher indexes all existing Voice Memos into the state file without copying them (prevents a flood of old recordings)
2. Every `VMW_POLL_INTERVAL` seconds, it scans the source folder for new `.m4a` files
3. New files are parsed for their embedded timestamp, renamed to `YYMMDD_HHMMSS.m4a`, and copied to `VMW_DEST_DIR`
4. The state file is updated after each scan cycle

## Service management

```bash
# Check if running
sudo launchctl list | grep voice-memo

# View logs
tail -f /path/to/voice-memo-watcher/logs/out.log

# Stop
sudo launchctl unload /Library/LaunchDaemons/com.voice-memo-watcher.plist

# Start
sudo launchctl load /Library/LaunchDaemons/com.voice-memo-watcher.plist
```

## Why root?

macOS Voice Memos are stored in a sandboxed container. Granting Full Disk Access to Python works but is fragile across updates. Running as a LaunchDaemon (root) bypasses this restriction reliably.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied` on source | Verify the daemon is running as root (`sudo launchctl list`) |
| `Destination directory does not exist` | Check your network mount is available; the watcher will retry on the next poll |
| Old memos getting re-copied | State file was lost or reset — stop the daemon, delete the state file, restart (it will re-index without copying) |
| No new files appearing | Check `logs/out.log` for errors; verify `VMW_DEST_DIR` is writable |

## License

MIT
