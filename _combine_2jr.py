import os

parts = []

# Part 1: imports, page config, CSS, session state, sidebar
with open(r'F:\Projects\resume_ranking\_new_2jr_part1.py', 'r', encoding='utf-8') as f:
    parts.append(f.read())

# Part 2: landing mode
with open(r'F:\Projects\resume_ranking\_new_2jr_part2.py', 'r', encoding='utf-8') as f:
    parts.append(f.read())

# Part 3: detail mode
with open(r'F:\Projects\resume_ranking\_new_2jr_part3.py', 'r', encoding='utf-8') as f:
    parts.append(f.read())

# Part 4: mode dispatch
with open(r'F:\Projects\resume_ranking\_new_2jr_part4.py', 'r', encoding='utf-8') as f:
    parts.append(f.read())

# Combine and write
final_content = ''.join(parts)
output_path = r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(final_content)

print(f"Written {output_path}")
print(f"Total lines: {final_content.count(chr(10))}")
