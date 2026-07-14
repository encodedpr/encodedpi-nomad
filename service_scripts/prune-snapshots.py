#!/usr/bin/env python3
from pathlib import Path

MAX_IMAGES = 5000
root = Path("/spool/media/Media/RemoteDVR")
files = sorted(
    (
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg"}
    ),
    key=lambda path: (path.stat().st_mtime_ns, path.name),
)
removed = 0
for path in files[:-MAX_IMAGES] if len(files) > MAX_IMAGES else []:
    try:
        path.unlink()
        removed += 1
    except FileNotFoundError:
        pass

print(f"skynet snapshots={min(len(files), MAX_IMAGES)} removed={removed}")
