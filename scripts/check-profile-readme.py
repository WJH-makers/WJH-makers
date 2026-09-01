from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
readme = root / 'README.md'
if not readme.exists():
    raise SystemExit('README.md is missing')
text = readme.read_text(encoding='utf-8')
required = ['WJH-makers/.github', 'readme-template', 'GitHub 工程化工具包']
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit('README missing required GitHub toolkit references: ' + ', '.join(missing))

local_refs = set()
for match in re.finditer(r'(?:src|href)="([^"#]+)"', text):
    value = match.group(1)
    if value.startswith(('http://', 'https://', 'mailto:')):
        continue
    local_refs.add(value.split('?')[0])
missing_paths = [ref for ref in sorted(local_refs) if not (root / ref).exists()]
if missing_paths:
    raise SystemExit('README references missing local files: ' + ', '.join(missing_paths))
print('Profile README health check passed.')
