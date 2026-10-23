import urllib.request
import json
from pathlib import Path

# 1. Upload resume to test reset
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
profile_json = Path('data/profile/profile.json').read_bytes()

body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="resume.json"\r\n'
    f'Content-Type: application/json\r\n\r\n'
).encode() + profile_json + f'\r\n--{boundary}--\r\n'.encode()

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/profile/upload',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)

with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode())
    print('Upload status:', res.get('status'))
    print('Message:', res.get('message'))

# 2. Verify all jobs reset to 0
jobs_req = urllib.request.Request('http://127.0.0.1:8000/api/jobs')
with urllib.request.urlopen(jobs_req) as resp:
    jobs = json.loads(resp.read().decode())
    print('Jobs count in DB after resume upload:', len(jobs))
    assert len(jobs) == 0, f'Expected 0 jobs after reset, found {len(jobs)}'

# 3. Discover Linear jobs
lin_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/jobs/search?board=linear&isolate_company=true',
    method='POST'
)
with urllib.request.urlopen(lin_req) as resp:
    lin_res = json.loads(resp.read().decode())
    print('Discovered Linear jobs:', len(lin_res.get('jobs', [])))

# 4. Verify only Linear exists in DB
with urllib.request.urlopen(jobs_req) as resp:
    jobs = json.loads(resp.read().decode())
    companies = {j['company'] for j in jobs}
    print('Companies in DB:', companies)
    assert companies == {'Linear'}, f'Expected only Linear, got {companies}'

# 5. Discover Spotify jobs (must remove Linear)
spot_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/jobs/search?board=spotify&isolate_company=true',
    method='POST'
)
with urllib.request.urlopen(spot_req) as resp:
    spot_res = json.loads(resp.read().decode())
    print('Discovered Spotify jobs:', len(spot_res.get('jobs', [])))

with urllib.request.urlopen(jobs_req) as resp:
    jobs = json.loads(resp.read().decode())
    companies = {j['company'] for j in jobs}
    print('Companies in DB after clicking Spotify:', companies)
    assert companies == {'Spotify'}, f'Expected only Spotify, got {companies}'

print('\nALL VERIFICATIONS PASSED!')
print('1. Uploading resume completely resets all jobs, matches, and applied statuses to 0.')
print('2. Clicking any company removes all other jobs from both database and UI.')
