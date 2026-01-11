from PIL import Image, ExifTags
from pathlib import Path
import pyexiv2
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple

_TAG_MAP = {v: k for k, v in ExifTags.TAGS.items()}

@dataclass
class Person:
    name: str
    rect: Optional[Tuple[float, float, float, float]]


@dataclass
class SimpleImageMetadata:
    description: Optional[str]
    date_created: Optional[str]
    date_created_simple: Optional[str]
    persons: List[Person]

def __get_people(img) -> List[Person]:
    """
    Extract people from a `pyexiv2.Image` instance and return a list of `Person`.
    - `img`: pyexiv2.Image (already opened)
    - returns: List[Person] with optional rect tuples (x,y,w,h)
    """
    candidates = []

    xmp = img.read_xmp() or {}

    mp_regions = {}
    mwg_regions = {}

    for key, rawval in xmp.items():
        val = getattr(rawval, "value", rawval)
        if val is None:
            continue
        # skip structural markers like 'type="Struct"'
        if isinstance(val, str) and val.startswith("type="):
            continue

        # MP (Adobe) style: .../MPRI:Regions[1]/MPReg:PersonDisplayName
        m = re.search(r'MPRI:Regions\[(\d+)\]/MPReg:PersonDisplayName', key)
        if m:
            idx = int(m.group(1))
            mp_regions.setdefault(idx, {})["name"] = str(val)
            continue
        m = re.search(r'MPRI:Regions\[(\d+)\]/MPReg:Rectangle', key)
        if m:
            idx = int(m.group(1))
            parts = [x.strip() for x in str(val).split(',')]
            try:
                rect = tuple(float(x) for x in parts)
                if len(rect) == 4:
                    mp_regions.setdefault(idx, {})["rect"] = rect
            except Exception:
                pass
            continue

        # mwg-rs style: .../mwg-rs:RegionList[1]/mwg-rs:Name
        m = re.search(r'mwg-rs:RegionList\[(\d+)\]/mwg-rs:Name', key, flags=re.I)
        if m:
            idx = int(m.group(1))
            mwg_regions.setdefault(idx, {})["name"] = str(val)
            continue
        # mwg stArea parts: .../mwg-rs:Area/stArea:x
        m = re.search(r'mwg-rs:RegionList\[(\d+)\]/mwg-rs:Area/stArea:(x|y|w|h)', key, flags=re.I)
        if m:
            idx = int(m.group(1))
            part = m.group(2).lower()
            try:
                v = float(val)
            except Exception:
                continue
            mwg_regions.setdefault(idx, {}).setdefault("area", {})[part] = v
            continue

    # build list from mp_regions
    for idx in sorted(mp_regions.keys()):
        entry = mp_regions[idx]
        name = entry.get("name")
        rect = entry.get("rect")
        if name:
            candidates.append((name, rect))

    # build list from mwg_regions (convert area dict to rect tuple)
    for idx in sorted(mwg_regions.keys()):
        entry = mwg_regions[idx]
        name = entry.get("name")
        area = entry.get("area", {})
        rect = None
        if all(k in area for k in ("x", "y", "w", "h")):
            rect = (area["x"], area["y"], area["w"], area["h"])
        if name:
            candidates.append((name, rect))

    # fallback: try to find generic person keys (PersonInImage, RegionPersonDisplayName, etc.)
    generic = []
    for key, rawval in xmp.items():
        val = getattr(rawval, "value", rawval)
        if val is None:
            continue
        if isinstance(val, str) and val.startswith("type="):
            continue
        kl = key.lower()
        if "persondisplayname" in kl or "personinimage" in kl or "regionpersondisplayname" in kl or "regionname" in kl:
            if isinstance(val, (list, tuple)):
                for v in val:
                    if v:
                        generic.append((str(v), None))
            else:
                generic.append((str(val), None))

    # merge, preserving order and dedupe by name (keep first rect seen)
    seen = set()
    people: List[Person] = []
    for name, rect in candidates + generic:
        if name not in seen:
            seen.add(name)
            people.append(Person(name=name, rect=rect))
    return people

def get_image_metadata(path: str) -> SimpleImageMetadata:
    """Return a SimpleImageMetadata for the image at `path`.

    - `description`: tries XMP dc:description, IPTC caption, EXIF ImageDescription
    - `date_created`: common created/date tags
    - `ferons`: list of detected people with optional rect (x,y,w,h)
    """
    p = Path(path)

    # read textual fields from metadata using pyexiv2.Image
    xmp_map = {}
    iptc_map = {}
    exif_map = {}
    try:
        img = pyexiv2.Image(str(p))
        xmp_map = img.read_xmp() or {}
        iptc_map = img.read_iptc() or {}
        exif_map = img.read_exif() or {}
        people_list = __get_people(img)
        img.close()
    except Exception:
        xmp_map = {}
        iptc_map = {}
        exif_map = {}
        people_list = []

    def _norm_vals(rawval):
        val = getattr(rawval, "value", rawval)
        if val is None:
            return []
        if isinstance(val, dict):
            return [v for v in val.values() if v]
        if isinstance(val, (list, tuple)):
            return [v for v in val if v and not (isinstance(v, str) and v.startswith("type="))]
        if isinstance(val, str) and val.startswith("type="):
            return []
        return [val]

    def _find_value(mappings, keys_substrings):
        for mapping in mappings:
            for k, rawval in mapping.items():
                kl = k.lower()
                for sub in keys_substrings:
                    if sub in kl:
                        vals = _norm_vals(rawval)
                        if vals:
                            return str(vals[0])
        return None

    description = _find_value([xmp_map, iptc_map, exif_map], ["Exif.Image.ImageDescription", "caption", "captionwriter", "dc:description"]) 
    date_created = _find_value([xmp_map, iptc_map, exif_map], ["datecreated", "created", "datetimeoriginal", "create"]) 
    date_created_simple = p.parent.name

    if date_created:
        from datetime import datetime
        s = str(date_created)
        # accept trailing Z by converting to +00:00 for fromisoformat
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(s)
            date_created_simple = f"{dt.month:02d}-{dt.year}"
        except Exception:
            date_created_simple = p.parent.name

    return SimpleImageMetadata(description=description, date_created=date_created, date_created_simple=date_created_simple, persons=people_list)