from pathlib import Path

app_path = Path("frontend/src/App.jsx")
with open(app_path, "r", encoding="utf-8") as f:
    text = f.read().replace("\r\n", "\n")

# 1. Import resetApplications
old_import = """import {
  fetchProfile,
  fetchJobs,
  uploadResumeFile,
  searchGreenhouse,
  isolateCompanyJobs,
  clearAllJobs,
  rankJobs,"""

new_import = """import {
  fetchProfile,
  fetchJobs,
  uploadResumeFile,
  searchGreenhouse,
  isolateCompanyJobs,
  clearAllJobs,
  resetApplications,
  rankJobs,"""

assert old_import in text, "old_import not found"
text = text.replace(old_import, new_import)

# 2. Add Reset Applied button in Tracker header
old_tracker_header = """              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                  Unique Roles: <strong className="text-white">{uniqueJobs.length}</strong>
                </span>
                <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Applied: <strong className="text-white">{uniqueJobs.filter(j => j.status === 'applied').length}</strong>
                </span>
              </div>"""

new_tracker_header = """              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                  Unique Roles: <strong className="text-white">{uniqueJobs.length}</strong>
                </span>
                <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Applied: <strong className="text-white">{uniqueJobs.filter(j => j.status === 'applied').length}</strong>
                </span>
                {uniqueJobs.filter(j => j.status === 'applied').length > 0 && (
                  <button
                    onClick={async () => {
                      try {
                        await resetApplications();
                        const updated = await fetchJobs();
                        setJobs(updated);
                        showToast('success', 'All applied statuses have been reset to discovered.');
                      } catch (err) {
                        showToast('error', err.message);
                      }
                    }}
                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-rose-950/60 hover:bg-rose-900/60 text-rose-300 border border-rose-800/60 transition flex items-center gap-1.5"
                    title="Reset all applied statuses back to discovered"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Reset Applied
                  </button>
                )}
              </div>"""

assert old_tracker_header in text, "old_tracker_header not found"
text = text.replace(old_tracker_header, new_tracker_header)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(text)

print("SUCCESS: resetApplications added to App.jsx!")
