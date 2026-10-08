import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tether"
SUBPACKAGES = ("providers", "features", "evaluation")

PATH_PATTERN = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./\\-]*\.py)`")
SOURCES = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").glob("*.md"))

missing_prefixed = []
needs_prefix = []
unknown = []

for md in SOURCES:
    for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
        for match in PATH_PATTERN.finditer(line):
            raw = match.group(1).replace("\\", "/")
            where = f"{md.relative_to(ROOT)}:{lineno}"
            if raw.startswith("tether/") or raw.startswith("tests/"):
                if not (ROOT / raw).exists():
                    missing_prefixed.append((where, raw))
                continue
            if "/" in raw:
                continue
            if (PKG / raw).exists() or (ROOT / raw).exists():
                continue
            subpackages = [name for name in SUBPACKAGES if (PKG / name / raw).exists()]
            if subpackages:
                needs_prefix.append((where, raw, [f"tether/{name}/{raw}" for name in subpackages]))
            elif not (ROOT / "scripts" / raw).exists() and not (ROOT / "tests" / raw).exists():
                unknown.append((where, raw))

print("### 带 tether/ 或 tests/ 前缀，但文件不存在")
for where, raw in missing_prefixed:
    print(f"{where}  {raw}")
if not missing_prefixed:
    print("（无）")

print()
print("### 裸文件名，实际在子包下，路径应当补全")
for where, raw, candidates in needs_prefix:
    print(f"{where}  {raw}  ->  {', '.join(candidates)}")
if not needs_prefix:
    print("（无）")

print()
print("### 裸文件名，在包、仓库根、子包、scripts、tests 下都找不到")
for where, raw in unknown:
    print(f"{where}  {raw}")
if not unknown:
    print("（无）")

print()
print(f"合计：前缀错误 {len(missing_prefixed)} 处，需要补前缀 {len(needs_prefix)} 处，无法定位 {len(unknown)} 处")
