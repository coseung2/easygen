"""CPU-only, resumable model download with exact revision/size/SHA-256 checks."""
import hashlib
import json
import os
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def provision(group, root, verify_only=False):
    from huggingface_hub import hf_hub_download
    entries = json.loads(Path(__file__).with_name('models.json').read_text())[group]
    root = Path(root)
    reports = []
    for item in entries:
        target = root / item['target']
        if not target.is_file():
            if verify_only:
                raise FileNotFoundError(item['target'])
            # HF cache resumes interrupted transfers; do not print or store access tokens.
            downloaded = Path(hf_hub_download(item['repo'], item['file'], revision=item['revision'],
                                             cache_dir=str(root / '.download-cache'), token=os.environ.get('HF_TOKEN')))
            if downloaded.stat().st_size != item['bytes'] or digest(downloaded) != item['sha256']:
                raise ValueError('Downloaded model checksum mismatch: ' + item['target'])
            target.parent.mkdir(parents=True, exist_ok=True)
            # Rename actual blob on this volume, not a cache symlink; avoids a second full copy.
            downloaded.resolve().replace(target)
        if target.stat().st_size != item['bytes'] or digest(target) != item['sha256']:
            raise ValueError('Existing model differs; preserved without overwriting: ' + item['target'])
        reports.append({'file': item['target'], 'bytes': item['bytes'], 'sha256': item['sha256']})
    (root / 'easygen-models.json').write_text(json.dumps(reports, indent=2) + '\n')
    return reports
