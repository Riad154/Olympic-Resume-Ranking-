import re

with open(r'F:\Projects\resume_ranking\resume_app\pages\1_Department_Rankings.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the navigation block
old_pattern = '''st.session_state["selected_job"] = label
                    st.switch_page("pages/2_Job_Rankings.py")'''

new_pattern = '''st.session_state["selected_job"]     = label
                    st.session_state["jr_active_job"]    = label
                    st.session_state["jr_mode"]          = "detail"
                    st.session_state["jr_incoming_via"] = "dept"
                    st.switch_page("pages/2_Job_Rankings.py")'''

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)
    print('[OK] Updated 1_Department_Rankings.py navigation')
else:
    print('[WARN] 1_Department_Rankings.py pattern not found')
    # Try to find the pattern
    idx = content.find('st.session_state["selected_job"] = label')
    if idx != -1:
        print('Found at index:', idx)
        print(repr(content[idx:idx+150]))
    else:
        print('Could not find selected_job at all')

with open(r'F:\Projects\resume_ranking\resume_app\pages\1_Department_Rankings.py', 'w', encoding='utf-8') as f:
    f.write(content)
