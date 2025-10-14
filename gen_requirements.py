# gen_requirements.py
import sys, os, ast, re
from pathlib import Path
from importlib import metadata

IGNORE_DIRS = {'.venv', 'venv', '__pycache__', 'node_modules', '.git', 'data', 'assets', 'images'}
PY_EXT = ('.py',)

def scan_imports(root: Path):
    mods = set()
    for p in root.rglob("*.py"):
        if any(part in IGNORE_DIRS for part in p.parts): 
            continue
        try:
            node = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for n in ast.walk(node):
            if isinstance(n, ast.Import):
                for a in n.names:
                    mods.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split('.')[0])
    # filter stdlib / relative / dunder
    stdlike = {'os','sys','re','json','pathlib','typing','math','itertools','collections','datetime','time','subprocess','statistics','functools','enum','dataclasses','logging','argparse','tempfile','shutil','csv','zipfile','io','uuid','base64','hashlib','random'}
    mods = {m for m in mods if re.match(r"^[a-zA-Z_][\w\-]*$", m) and m not in stdlike}
    return sorted(mods)

def to_requirements(mods):
    # map import->distribution
    mapping = metadata.packages_distributions()  # {top_level_pkg: [dist_names]}
    reqs, missing = [], []
    for m in mods:
        dists = mapping.get(m)
        if not dists:
            # common mismatches
            alias = {'cv2':'opencv-python','sklearn':'scikit-learn','yaml':'PyYAML','PIL':'Pillow','bs4':'beautifulsoup4'}
            pkg = alias.get(m)
            if pkg:
                dists = [pkg]
        if dists:
            pkg = dists[0]
            try:
                ver = metadata.version(pkg)
                reqs.append(f"{pkg}=={ver}")
            except Exception:
                reqs.append(pkg)
        else:
            missing.append(m)
    return sorted(set(reqs)), sorted(missing)

def main():
    if len(sys.argv) != 2:
        print("Usage: python gen_requirements.py <folder>")
        sys.exit(1)
    root = Path(sys.argv[1]).resolve()
    mods = scan_imports(root)
    reqs, missing = to_requirements(mods)
    out = root / "requirements.txt"
    out.write_text("\n".join(reqs) + ("\n" if reqs else ""))
    if missing:
        with open(out, "a", encoding="utf-8") as f:
            f.write("\n# Unmapped imports (add manually):\n")
            for m in missing: f.write(f"# {m}\n")
    print(f"Wrote {out} with {len(reqs)} packages.")
    if missing:
        print("Unmapped imports:", ", ".join(missing))

if __name__ == "__main__":
    main()
