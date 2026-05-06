import re, os

path = r'F:\Projects\WINDSURF_BDJOBS_INTEGRATION_PROMPT.md'
out_path = r'F:\Projects\resume_ranking\resume_app\_bdjobs_registry.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_line = None
end_line = None
for i, line in enumerate(lines):
    if 'BDJOBS_JOB_REGISTRY = {' in line:
        start_line = i
    if start_line is not None and '```' in line and i > start_line and end_line is None:
        stripped = line.lstrip()
        if stripped.startswith('```'):
            end_line = i
            break

print(f'Start: {start_line}, End: {end_line}')
if start_line is not None and end_line is not None:
    content = ''.join(lines[start_line:end_line])
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('"""\n')
        f.write('_bdjobs_registry.py - BDJobs Job Registry for Olympic Industries PLC.\n')
        f.write('"""\n\n')
        f.write(content)
        f.write('\n')
    print(f'Wrote {end_line - start_line} lines to {out_path}')
else:
    print('Could not find boundaries')
