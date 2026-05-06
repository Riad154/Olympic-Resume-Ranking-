parts = []

parts.append(r'''
# ═══════════════════════════════════════════════════════════════════════════════
# MODE DISPATCH
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state["jr_mode"] == "landing":
    render_landing()
else:
    render_detail()
''')

with open(r'F:\Projects\resume_ranking\_new_2jr_part4.py', 'w', encoding='utf-8') as f:
    f.write(''.join(parts))

print("Part 4 written")
