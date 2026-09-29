"""Download source originals for the selected moments from B2 (read-only GETs).

Credentials are read from env injected by `infisical run`; nothing is printed or stored.
Files land in the configured Lab data root under sources/<moment>_<pos>.<ext>.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import lab_path

WORK = lab_path('2026-09-28-junyoung-intro')
OUT = WORK / 'sources'
OUT.mkdir(parents=True, exist_ok=True)
EXT = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/heic': 'heic', 'image/webp': 'webp',
       'video/mp4': 'mp4', 'video/quicktime': 'mov'}

s3 = boto3.client('s3', endpoint_url=os.environ['B2_S3_ENDPOINT'], region_name=os.environ['B2_REGION'],
                  aws_access_key_id=os.environ['B2_KEY_ID'], aws_secret_access_key=os.environ['B2_APPLICATION_KEY'],
                  config=Config(signature_version='s3v4', retries={'max_attempts': 4}))
bucket = os.environ['B2_BUCKET']

rows = json.load(open(WORK / 'data' / 'moments.json', encoding='utf-8'))
jobs = []
for r in rows:
    for a in r['assets'] or []:
        if a['kind'] != 'source' or a['provider'] != 'b2':
            continue
        ext = EXT.get(a['type'], a['type'].split('/')[-1])
        dest = OUT / f"{r['id'][:8]}_{a['pos'] or 0:02d}.{ext}"
        jobs.append((a['path'], dest, a['bytes']))


def fetch(job):
    key, dest, size = job
    if dest.exists() and dest.stat().st_size == size:
        return 'skip'
    s3.download_file(bucket, key, str(dest))
    return 'ok' if dest.stat().st_size == size else 'size-mismatch'


with ThreadPoolExecutor(6) as pool:
    results = list(pool.map(fetch, jobs))
total = sum(j[2] for j in jobs)
print('files', len(jobs), 'MB', round(total / 1e6, 1), {k: results.count(k) for k in set(results)})
