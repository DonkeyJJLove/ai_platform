"""Read-only inventory and hold classification of LION desktop staging root.

No delete, move, rename, archive, shortcut edit, launcher execution or raw
conversation SQLite operations. The operator provides ACTIVE exact names; all
other material remains protected until source-bound owner adjudication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import stat

SCHEMA="lion.desktop.staging-owner-census/v1"
_NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_. -]{0,250}$')
HISTORICAL_EXTS={".ps1",".vbs",".lpcl",".json",".py",".cjs",".png",".log"}

class InventoryError(RuntimeError):
    pass

def snapshot(root: Path, active: tuple[str,...]=()) -> dict:
    root=Path(root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise InventoryError("staging root must be direct existing absolute directory")
    if any(not isinstance(x,str) or not _NAME.fullmatch(x) for x in active):
        raise InventoryError("active names must be top-level names only")
    selected=set(active)
    observed={}
    for entry in sorted(root.iterdir(),key=lambda p:p.name.casefold()):
        stats=entry.lstat()
        if stat.S_ISLNK(stats.st_mode):
            kind="SYMLINK_HOLD"
        elif stat.S_ISDIR(stats.st_mode):
            kind="DIRECTORY"
        elif stat.S_ISREG(stats.st_mode):
            kind="FILE"
        else:
            kind="OTHER_HOLD"
        digest=None
        if kind=="FILE" and stats.st_size <= 4*1024*1024:
            digest=sha256(entry.read_bytes()).hexdigest()
        if entry.name in selected:
            classification="REFERENCED_ACTIVE_PRESERVE"
        elif kind in ("SYMLINK_HOLD","OTHER_HOLD"):
            classification="UNTRUSTED_ITEM_HOLD"
        elif entry.suffix.lower() in HISTORICAL_EXTS or kind=="DIRECTORY":
            classification="HISTORICAL_OR_DEPENDENT_PRESERVE_REVIEW"
        else:
            classification="UNCLASSIFIED_PRESERVE_REVIEW"
        observed[entry.name]={
            "kind":kind,"size_bytes":stats.st_size if kind=="FILE" else None,
            "sha256":digest,"classification":classification,
            "deletion_authorized":False,
        }
    missing=sorted(selected-set(observed))
    # A missing current launcher blocks any migration decision.
    if missing: raise InventoryError("declared active staging entries missing: "+", ".join(missing))
    counts={}
    for value in observed.values():
        counts[value["classification"]]=counts.get(value["classification"],0)+1
    return {
        "schema":SCHEMA,
        "staging_root":str(root),
        "captured_at_utc":datetime.now(timezone.utc).isoformat(),
        "recursion":"TOP_LEVEL_ONLY",
        "operation":"READ_ONLY_NO_RETIREMENT",
        "declared_active_exact_names":sorted(selected),
        "items":observed,"top_level_count":len(observed),
        "file_count":sum(v["kind"]=="FILE" for v in observed.values()),
        "directory_count":sum(v["kind"]=="DIRECTORY" for v in observed.values()),
        "classification_counts":counts,
        "unknown_owner_migration":"BLOCKED_UNTIL_ORIGINAL_REFERENCES_AND_BACKUPS_VERIFIED",
        "file_delete_count":0,
    }

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--staging-root",type=Path,required=True)
    p.add_argument("--active",action="append",default=[])
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    result=snapshot(args.staging_root,tuple(args.active))
    payload=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if args.output:
        # Refuse to write into the staging directory being inventoried.
        dest=args.output.resolve(strict=False)
        root=args.staging_root.resolve(strict=True)
        if dest==root or root in dest.parents:
            raise InventoryError("report output must be outside inventoried staging")
        dest.write_text(payload,encoding="utf-8")
    else:print(payload,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
