import json
with open(r'f:\Projects\resume_ranking\bdjobs_session.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

for entry in har['log']['entries']:
    url = entry['request']['url']
    if any(k in url.lower() for k in ['cv', 'download', 'getcv', 'viewcv', 'pdf', 'resume']):
        print(f"{entry['request']['method']} {url}")
