from pathlib import Path

p = Path('packaging/requirements-pinned.txt')
if not p.exists():
    print('requirements-pinned.txt not found; skipping normalization')
    raise SystemExit(0)

b = p.read_bytes()
for enc in ('utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin1'):
    try:
        s = b.decode(enc)
        p.write_text(s, encoding='utf-8')
        print('Converted requirements from', enc)
        break
    except Exception:
        continue
else:
    print('Could not decode requirements-pinned.txt with known encodings')
    raise SystemExit(1)
