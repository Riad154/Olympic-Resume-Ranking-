import json
from urllib.parse import urlparse

with open('bdjobs_applicants.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

seen = set()
for e in har['log']['entries']:
    u = urlparse(e['request']['url'])
    method = e['request']['method']
    skip = ('google', 'clarity.ms', 'facebook', 'linkedin', 'youtube', 'cdnjs', 'fonts')
    if any(s in u.netloc for s in skip):
        continue
    if u.path.endswith(('.js', '.css', '.png', '.jpg', '.svg', '.woff', '.ttf', '.ico', '.gif', '.webp')):
        continue
    key = method + ' ' + u.netloc + u.path
    if key in seen:
        continue
    seen.add(key)
    status = e['response']['status']
    print(f'  [{status}] {method} {u.netloc}{u.path}')
    if u.query:
        print(f'         ?{u.query[:180]}')

print(f'\nTotal unique requests: {len(seen)}')
