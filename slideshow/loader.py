import os
from pathlib import Path
from typing import List

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}


def scan_folders(folders: List[str]):
    paths = []
    for folder in folders:
        p = Path(folder)
        if not p.exists():
            continue
        for root, dirs, files in os.walk(p):
            for f in files:
                if Path(f).suffix.lower() in IMAGE_EXTS:
                    paths.append(str(Path(root) / f))
    return paths
