"""Read-only Supabase Management API query. Credentials come from env only; never printed.

Usage (inside `infisical run`):
    python query_db.py projects
    python query_db.py sql "select ..." [out.json]   # wrapped in a read-only transaction
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = 'https://api.supabase.com/v1'


def call(method, path, body=None):
    token = os.environ['SUPABASE_ACCESS_TOKEN']
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                                          'User-Agent': 'modal-gui-lab'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise SystemExit(f'HTTP {e.code}: {e.read().decode("utf-8", "replace")[:600]}')


def project_ref():
    ref = os.environ.get('EOSEOWA_PROJECT_REF')
    if ref:
        return ref
    projects = call('GET', '/projects')
    if len(projects) != 1:
        raise SystemExit('multiple projects; set EOSEOWA_PROJECT_REF: ' + ', '.join(p['name'] for p in projects))
    return projects[0]['id']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1] == 'projects':
        for p in call('GET', '/projects'):
            print(p['id'], p['name'], p.get('region'), p.get('status'))
        return
    sql = sys.argv[2]
    if sql.startswith('@'):
        with open(sql[1:], encoding='utf-8') as f:
            sql = f.read()
    sql = sql.strip().rstrip(';')
    guarded = f'begin transaction read only; {sql}; commit;'
    rows = call('POST', f'/projects/{project_ref()}/database/query', {'query': guarded})
    out = sys.argv[3] if len(sys.argv) > 3 else None
    if out:
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1, default=str)
        print('rows', len(rows), '->', out)
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    main()
