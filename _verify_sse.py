import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'http://localhost:8080/api/orchestrator/stream?title=t&theme=t&chapter_count=1'
req = urllib.request.Request(url)
r = urllib.request.urlopen(req, context=ctx, timeout=60)

lines = []
for raw in r:
    line = raw.decode('utf-8').strip()
    if line.startswith('event:') or line.startswith('data:'):
        lines.append(line)
    if len(lines) >= 6:
        break

print('First 6 SSE lines:')
for l in lines:
    print(f'  {l[:120]}')
if any(l.startswith('event:') for l in lines):
    print('OK: event: field exists')
else:
    print('FAIL: No event: field')
r.close()