export async function fetchHealth() {
  const res = await fetch('/api/health');
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchProfile() {
  const res = await fetch('/api/profile');
  if (!res.ok) throw new Error('Failed to load profile');
  return res.json();
}

export async function uploadResumeFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/api/profile/upload', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to upload resume');
  }
  return res.json();
}

export async function fetchJobs(status = null) {
  const url = status ? `/api/jobs?status=${status}` : '/api/jobs';
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to load jobs');
  return res.json();
}

export async function searchGreenhouse(board = 'cloudflare', isolate = true) {
  const res = await fetch(`/api/jobs/search?board=${encodeURIComponent(board)}&isolate_company=${isolate}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to search ATS for ${board}`);
  return res.json();
}

export async function isolateCompanyJobs(company) {
  const res = await fetch(`/api/jobs/isolate?company=${encodeURIComponent(company)}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to isolate jobs for ${company}`);
  return res.json();
}

export async function clearAllJobs() {
  const res = await fetch('/api/jobs', { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to clear jobs');
  return res.json();
}

export async function resetApplications() {
  const res = await fetch('/api/applications/reset', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset applications');
  return res.json();
}

export async function rankJobs() {
  const res = await fetch('/api/jobs/rank', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to rank jobs');
  return res.json();
}

export async function addManualJob(jobData) {
  const res = await fetch('/api/jobs/manual', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jobData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to add custom job');
  }
  return res.json();
}

export async function updateJobStatus(jobId, status) {
  const res = await fetch(`/api/jobs/${jobId}/status?status=${status}`, {
    method: 'PATCH',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update job status');
  }
  return res.json();
}

export async function startApplication(jobId) {
  const res = await fetch('/api/applications/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to start application pipeline');
  }
  return res.json();
}

export async function decideApplication(threadId, approve, feedback = '') {
  const res = await fetch('/api/applications/decide', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: threadId, approve, feedback }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit decision');
  }
  return res.json();
}

export async function fetchScreeningPreferences() {
  const res = await fetch('/api/profile/screening');
  if (!res.ok) throw new Error('Failed to load screening preferences');
  return res.json();
}

export async function updateScreeningPreferences(screeningData) {
  const res = await fetch('/api/profile/screening', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(screeningData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update screening preferences');
  }
  return res.json();
}
