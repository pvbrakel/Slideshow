from PIL import Image, ExifTags
from pathlib import Path

_TAG_MAP = {v: k for k, v in ExifTags.TAGS.items()}


def get_month_year_or_folder(path: str):
    p = Path(path)
    try:
        with Image.open(p) as img:
            exif = img._getexif() or {}
            dt_tag = _TAG_MAP.get('DateTimeOriginal') or _TAG_MAP.get('DateTime')
            if dt_tag and dt_tag in exif:
                dt = exif[dt_tag]
                # format: YYYY:MM:DD HH:MM:SS
                parts = dt.split()
                if parts:
                    date = parts[0]
                    y, m, _ = date.split(':')
                    return f"{m}/{y}"
    except Exception:
        pass
    # fallback to parent folder name
    return p.parent.name
