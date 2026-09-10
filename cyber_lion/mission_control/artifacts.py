from pathlib import Path
ALLOWED_PREFIXES=('/var/lib/sentinelx/uploads/vkt-r3-lpcl-v2-final/','/var/lib/sentinelx/uploads/vkt-r3-validation/','/var/lib/sentinelx/uploads/oss-repository-tests/')
def allowed(path):
 p=str(Path(path).resolve())
 return any(p.startswith(x) for x in ALLOWED_PREFIXES) and not Path(p).is_symlink()
