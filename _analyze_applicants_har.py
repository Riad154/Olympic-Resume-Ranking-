import json
from urllib.parse import urlparse

with open('bdjobs_applicants.har', 'r', encoding='utf-8') as f:
    har = json.load(f)
entries = har['log']['entries']

# Skip noise domains/extensions
SKIP_DOMAINS = {'storage.googleapis.com', 'www.google-analytics.com', 'analytics.google.com',
                'www.googletagmanager.com', 'k.clarity.ms', 'c.clarity.ms', 'c.bing.com',
                'www.facebook.com', 'connect.facebook.net', 'www.youtube.com',
                'd.clarity.ms', 'o.clarity.ms', 'snap.licdn.com', 'px.ads.linkedin.com',
                'www.google.com.bd', 'www.google.com', 'fonts.googleapis.com',
                'fonts.gstatic.com', 'cdnjs.cloudflare.com'}
SKIP_EXTS = ('.js', '.css', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ttf', '.ico',
             '.gif', '.webp', '.map', '.html')

print('=== ALL UNIQUE API REQUESTS ===\n')
seen = set()
for e in entries:
    url = e['request']['url']
    method = e['request']['method']
    u = urlparse(url)
    if u.netloc in SKIP_DOMAINS:
        continue
    if u.path.endswith(SKIP_EXTS):
        continue
    key = method + ' ' + u.netloc + u.path
    if key in seen:
        continue
    seen.add(key)
    status = e['response']['status']
    print(f'  [{status}] {method} {u.netloc}{u.path}')
    if u.query:
        print(f'         ?{u.query[:200]}')
