"""Fix extra 4-space indentation in 2_Job_Rankings.py detail panel."""
with open(r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the else: block for candidate detail panel
# It starts at line 525 (0-indexed 524)
# We need to remove 4 spaces from lines that are part of the detail panel
# The detail panel goes from line 536 until the "# ── Errors" section

start_fix = None
for i, line in enumerate(lines):
    if 'else:' in line and 'selected_rows' not in line and i > 520:
        # Found the else block
        start_fix = i + 1  # Start fixing from next line
        break

if start_fix is None:
    print("Could not find else block")
    exit(1)

# Find the end of the detail panel (look for "# ── Errors" or "if not errors_df.empty:")
end_fix = len(lines)
for i in range(start_fix, len(lines)):
    if '# ── Errors' in lines[i] or 'if not errors_df.empty:' in lines[i]:
        end_fix = i
        break

# Remove 4 spaces from lines that have >= 12 spaces of indentation
# (they should have 8 less, i.e., remove 4)
fixed_count = 0
for i in range(start_fix, end_fix):
    line = lines[i]
    stripped = line.lstrip(' ')
    if stripped and not stripped.startswith('#'):
        spaces = len(line) - len(line.lstrip(' '))
        if spaces >= 12:
            lines[i] = line[4:]  # Remove first 4 spaces
            fixed_count += 1

with open(r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Fixed {fixed_count} lines")
