import json, sys

with open('bdjobs_session.har', 'r', encoding='utf-8') as f:
    har = json.load(f)
entries = har['log']['entries']

# Find the Login POST
for e in entries:
    url = e['request']['url']
    method = e['request']['method']
    if method == 'POST' and 'Login/Login' in url:
        print('=== LOGIN REQUEST ===')
        print('URL:', url)
        print()
        print('--- Request Headers ---')
        for h in e['request']['headers']:
            n = h['name'].lower()
            if n in ('content-type', 'origin', 'referer', 'user-agent', 'accept',
                     'x-api-key', 'authorization', 'app-version', 'x-client', 'host'):
                print('  ' + h['name'] + ': ' + h['value'][:200])
        print()
        print('--- Request Body ---')
        post = e['request'].get('postData', {})
        text = post.get('text', '')
        print(text[:1500])
        print()
        print('--- Response Headers ---')
        for h in e['response']['headers']:
            n = h['name'].lower()
            if n in ('content-type', 'set-cookie', 'authorization'):
                print('  ' + h['name'] + ': ' + h['value'][:300])
        print()
        print('--- Response Body (first 3000 chars) ---')
        body = e['response']['content'].get('text', '')
        print(body[:3000])
        print()
        break

# Also dump SupportingInfo (often returns auth tokens)
print('\n=== SUPPORTING INFO REQUEST ===')
for e in entries:
    url = e['request']['url']
    method = e['request']['method']
    if method == 'GET' and 'GetSupportingInfo' in url:
        print('URL:', url)
        print('--- Request Headers (auth-relevant) ---')
        for h in e['request']['headers']:
            n = h['name'].lower()
            if n in ('content-type', 'authorization', 'x-api-key', 'cookie', 'origin', 'referer'):
                v = h['value']
                print('  ' + h['name'] + ': ' + v[:200])
        print('--- Response Body (first 2000 chars) ---')
        body = e['response']['content'].get('text', '')
        print(body[:2000])
        break
