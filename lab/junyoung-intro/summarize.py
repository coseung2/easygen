import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')
rows = json.load(open('F:/modal-gui/lab/2026-09-28-junyoung-intro/data/moments.json', encoding='utf-8'))
kinds = Counter()
for r in rows:
    assets = r['assets'] or []
    src = [a for a in assets if a['kind'] == 'source']
    types = Counter(a['type'].split('/')[0] for a in src)
    kinds.update(a['kind'] for a in assets)
    prov = ','.join(sorted({a['provider'] for a in src}))
    cap = (r['caption'] or '').replace('\n', ' / ')
    print(f"{r['captured_kst'][:16]} | img{types.get('image', 0)} vid{types.get('video', 0)} {prov} | "
          f"♥{r['hearts']} 💬{r['comments']} | {r['place_label'] or ''} | {cap}")
print(kinds)
