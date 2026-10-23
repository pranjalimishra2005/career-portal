import urllib.request
import json
from pathlib import Path

def req(url, data=None, method='GET'):
    r = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={'Content-Type': 'application/json'} if data else {},
        method=method
    )
    with urllib.request.urlopen(r) as res:
        return json.loads(res.read().decode())

# 1. Fetch GitLab jobs
res = req('http://127.0.0.1:8000/api/jobs/search?board=gitlab&isolate_company=true', method='POST')
job_id = res['jobs'][0]['id']
print('Discovered job:', job_id, 'Initial status:', res['jobs'][0]['status'])

# 2. Mark this job as applied (simulating Candidate 1 applying)
patch_res = req(f'http://127.0.0.1:8000/api/jobs/{job_id}/status?status=applied', method='PATCH')
print('Simulated application for Candidate 1:', patch_res['message'])
applied_job = req(f'http://127.0.0.1:8000/api/jobs/{job_id}')
assert applied_job['status'] == 'applied', 'Status should be applied'

# 3. Candidate 2 uploads their resume!
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
profile_json = Path('data/profile/profile.json').read_bytes()
body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="candidate2_resume.json"\r\n'
    f'Content-Type: application/json\r\n\r\n'
).encode() + profile_json + f'\r\n--{boundary}--\r\n'.encode()

upload_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/profile/upload',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)
with urllib.request.urlopen(upload_req) as resp:
    upload_res = json.loads(resp.read().decode())
    print('Candidate 2 upload:', upload_res['message'])

# 4. Check all jobs in DB
jobs = req('http://127.0.0.1:8000/api/jobs')
print('Jobs in DB immediately after upload:', len(jobs))
assert len(jobs) == 0, 'All jobs should be 0'

# 5. Candidate 2 searches GitLab again (discovering the same job)
res2 = req('http://127.0.0.1:8000/api/jobs/search?board=gitlab&isolate_company=true', method='POST')
rediscovered = [j for j in res2['jobs'] if j['id'] == job_id][0]
print('Rediscovered job status for Candidate 2:', rediscovered['status'])
assert rediscovered['status'] != 'applied', f'FAIL: Job status should be reset, got {rediscovered["status"]}'
assert rediscovered['status'] in ['discovered', 'matched'], f'Expected discovered or matched, got {rediscovered["status"]}'

print('\nTEST PASSED: When uploading a new resume, previously applied jobs are 100% reset!')
