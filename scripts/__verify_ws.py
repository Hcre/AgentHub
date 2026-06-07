import re
for f in ['src/backend/app/api/ws/chat.py', 'src/backend/app/api/ws/runner.py']:
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
    events = re.findall(r'type["\']?\s*[=:]\s*["\']?([a-z_]+:[a-z_]+)["\']?', content)
    print(f'{f}: {sorted(set(events))}')
