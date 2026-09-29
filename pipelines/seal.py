"""Fill `files` hashes in each manifest / prompt meta and rebuild pipelines/registry.json.

Run after editing a draft or candidate. Refuses to touch a released version whose hashes changed
(제3조: released files are immutable — bump the version instead).

Usage: python pipelines/seal.py [--check]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT.parent / 'prompts'


def sha(path: Path) -> str:
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def seal_manifest(path: Path, shared_root: Path, check: bool) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    folder = path.parent
    files = {p.name: sha(p) for p in sorted(folder.iterdir())
             if p.is_file() and p.name not in {'manifest.json', 'meta.json'} and p.suffix in {'.py', '.json', '.md'}}
    for rel in data.get('runtime', {}).get('shared', []):
        p = shared_root / rel
        files[rel] = sha(p)
    changed = files != data.get('files')
    if changed and data.get('status') == 'released':
        raise SystemExit(f'{path}: released version changed; create a new version instead')
    if changed and not check:
        data['files'] = files
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'data': data, 'changed': changed}


def main(check=False):
    registry = {'pipelines': {}, 'prompts': {}}
    stale = []
    for manifest in sorted(ROOT.glob('*/*/manifest.json')):
        r = seal_manifest(manifest, ROOT, check)
        d = r['data']
        stale += [str(manifest)] if r['changed'] else []
        registry['pipelines'].setdefault(d['id'], {})[d['version']] = {
            'status': d['status'], 'label': d.get('label'), 'engine': d['engine'], 'kind': d['kind'],
            'summary': d.get('summary'), 'tone': d.get('tone'), 'path': manifest.parent.relative_to(ROOT).as_posix()}
    for meta in sorted(PROMPTS.glob('*/*/meta.json')):
        r = seal_manifest(meta, PROMPTS, check)
        d = r['data']
        stale += [str(meta)] if r['changed'] else []
        registry['prompts'].setdefault(d['id'], {})[d['version']] = {
            'status': d['status'], 'path': meta.parent.relative_to(PROMPTS).as_posix()}
    reg_path = ROOT / 'registry.json'
    text = json.dumps(registry, ensure_ascii=False, indent=2) + '\n'
    if check:
        if stale or not reg_path.exists() or reg_path.read_text(encoding='utf-8') != text:
            print('stale:', stale or ['registry.json'])
            return 1
        print('ok')
        return 0
    reg_path.write_text(text, encoding='utf-8')
    print('sealed', len(registry['pipelines']), 'pipelines,', len(registry['prompts']), 'prompts;', 'updated:', stale)
    return 0


if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv))
