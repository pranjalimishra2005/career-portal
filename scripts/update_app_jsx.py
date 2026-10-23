import re
from pathlib import Path

app_path = Path("frontend/src/App.jsx")
with open(app_path, "r", encoding="utf-8") as f:
    text = f.read()

# Normalize CRLF to LF for processing
text = text.replace("\r\n", "\n")

# 1. Imports: add isolateCompanyJobs, clearAllJobs
target_import = """import {
  fetchProfile,
  fetchJobs,
  uploadResumeFile,
  searchGreenhouse,
  rankJobs,"""

repl_import = """import {
  fetchProfile,
  fetchJobs,
  uploadResumeFile,
  searchGreenhouse,
  isolateCompanyJobs,
  clearAllJobs,
  rankJobs,"""

assert target_import in text, "target_import not found"
text = text.replace(target_import, repl_import)

# 2. State: add selectedCompany
target_state = """  // Discovery & Filtering
  const [boardInput, setBoardInput] = useState('');
  const [filter, setFilter] = useState('matched'); // 'matched' | 'all' | 'applied' | 'rejected'"""

repl_state = """  // Discovery & Filtering
  const [boardInput, setBoardInput] = useState('');
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [filter, setFilter] = useState('matched'); // 'matched' | 'all' | 'applied' | 'rejected'"""

assert target_state in text, "target_state not found"
text = text.replace(target_state, repl_state)

# 3. Handlers: handleFileUpload, handleSelectCompany, handleClearCompanyFilter, handleGreenhouseSearch
target_upload = """  // File Upload (Automatically resets pipeline and all job states for new candidate)
  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploadingResume(true);
      showToast('info', `Uploading & indexing ${file.name} into ChromaDB...`);
      const res = await uploadResumeFile(file);
      setProfile(res.profile);
      setReviewData(null);
      showToast('success', res.message);
      const updated = await fetchJobs();
      setJobs(updated);
    } catch (err) {
      showToast('error', `Failed to parse resume: ${err.message}`);
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  // Multi-ATS Board & Keyword Search (Greenhouse, Ashby, Lever)
  async function handleGreenhouseSearch(token) {
    const query = (token || boardInput || '').trim();
    if (!query) {
      showToast('error', 'Please enter a company name (e.g. cloudflare, linear, spotify, ramp, gitlab) or keyword.');
      return;
    }

    try {
      setSearchingBoard(true);
      showToast('info', `Searching ATS boards for '${query}'...`);
      const res = await searchGreenhouse(query);
      if (res.status === 'warning') {
        showToast('error', res.message);
      } else {
        showToast('success', res.message);
      }
      const updated = await fetchJobs();
      setJobs(updated);
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setSearchingBoard(false);
    }
  }"""

repl_upload = """  // File Upload: Automatically resets pipeline, wipes all jobs, and resets all states for new candidate
  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploadingResume(true);
      showToast('info', `Uploading & resetting all states for ${file.name}...`);
      const res = await uploadResumeFile(file);
      setProfile(res.profile);

      // COMPLETE RESET
      setJobs([]);
      setSelectedCompany(null);
      setReviewData(null);
      setApplyingJobId(null);
      setAnalysisJob(null);
      setStudioJobId(null);
      setBoardInput('');
      setFilter('all');

      showToast('success', res.message || `New resume uploaded for ${res.profile.full_name}! Everything has been reset.`);
    } catch (err) {
      showToast('error', `Failed to parse resume: ${err.message}`);
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  // Isolate Company: When any company is clicked, remove all other jobs!
  async function handleSelectCompany(companyName) {
    if (!companyName) return;
    const cleanCompany = companyName.trim();
    setSelectedCompany(cleanCompany);
    setBoardInput(cleanCompany);
    showToast('info', `Isolating ${cleanCompany} and removing other jobs...`);

    // 1. Immediately remove other companies on the client side
    setJobs((prev) => prev.filter((j) => (j.company || '').toLowerCase() === cleanCompany.toLowerCase()));

    // 2. Query ATS / backend to isolate jobs in SQLite and fetch live postings
    try {
      setSearchingBoard(true);
      const res = await searchGreenhouse(cleanCompany, true);
      if (res.jobs && res.jobs.length > 0) {
        setJobs(res.jobs);
        if (res.jobs.length > 0) {
          setStudioJobId(res.jobs[0].id);
        }
        showToast('success', `Showing ${res.jobs.length} jobs for ${cleanCompany}. All other jobs removed.`);
      } else {
        const iso = await isolateCompanyJobs(cleanCompany);
        if (iso.jobs) setJobs(iso.jobs);
      }
    } catch (err) {
      console.warn('ATS search fallback to isolate:', err);
      try {
        const iso = await isolateCompanyJobs(cleanCompany);
        if (iso.jobs) setJobs(iso.jobs);
      } catch (e2) {}
    } finally {
      setSearchingBoard(false);
    }
  }

  function handleClearCompanyFilter() {
    setSelectedCompany(null);
    setBoardInput('');
    fetchJobs().then((updated) => {
      setJobs(updated);
      showToast('info', 'Company filter cleared. Showing all jobs.');
    });
  }

  // Multi-ATS Board & Keyword Search (Greenhouse, Ashby, Lever)
  async function handleGreenhouseSearch(token) {
    const query = (token || boardInput || '').trim();
    if (!query) {
      showToast('error', 'Please enter a company name (e.g. cloudflare, linear, spotify, ramp, gitlab) or keyword.');
      return;
    }

    try {
      setSearchingBoard(true);
      setSelectedCompany(query);
      showToast('info', `Searching ATS boards for '${query}' & removing other jobs...`);
      const res = await searchGreenhouse(query, true);
      if (res.status === 'warning') {
        showToast('error', res.message);
      } else {
        showToast('success', res.message);
      }
      const updated = await fetchJobs();
      setJobs(updated);
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setSearchingBoard(false);
    }
  }"""

assert target_upload in text, "target_upload not found"
text = text.replace(target_upload, repl_upload)

# 4. FilteredJobs: filter by selectedCompany
target_filtered = """  // Filtered jobs: in 'matched', strictly keep score > 60
  const filteredJobs = uniqueJobs.filter((j) => {
    const score = getJobMatchScore(j);
    if (filter === 'all') return true;
    if (filter === 'matched') {
      return score !== null && score > 60 && j.status !== 'rejected_by_user';
    }
    if (filter === 'applied') return j.status === 'applied';
    if (filter === 'rejected') {
      return j.status === 'rejected_by_user' || (score !== null && score <= 60);
    }
    return j.status === filter;
  });"""

repl_filtered = """  // Filtered jobs: strictly exclude jobs from other companies if selectedCompany is active
  const filteredJobs = uniqueJobs.filter((j) => {
    if (selectedCompany && (j.company || '').toLowerCase() !== selectedCompany.toLowerCase()) {
      return false;
    }
    const score = getJobMatchScore(j);
    if (filter === 'all') return true;
    if (filter === 'matched') {
      return score !== null && score > 60 && j.status !== 'rejected_by_user';
    }
    if (filter === 'applied') return j.status === 'applied';
    if (filter === 'rejected') {
      return j.status === 'rejected_by_user' || (score !== null && score <= 60);
    }
    return j.status === filter;
  });"""

assert target_filtered in text, "target_filtered not found"
text = text.replace(target_filtered, repl_filtered)

# 5. Dashboard Recommended Job Card: clickable company name
target_dash_comp = """                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium text-sky-400">{job.company}</span>"""

repl_dash_comp = """                            <div className="flex items-center gap-2">
                              <span
                                onClick={() => {
                                  handleSelectCompany(job.company);
                                  setNavView('discovery');
                                }}
                                title={`Click to show only jobs from ${job.company} and remove other jobs`}
                                className="text-xs font-medium text-sky-400 hover:text-sky-300 hover:underline cursor-pointer flex items-center gap-1 transition"
                              >
                                <Building2 className="w-3 h-3 text-sky-400" />
                                {job.company}
                              </span>"""

assert target_dash_comp in text, "target_dash_comp not found"
text = text.replace(target_dash_comp, repl_dash_comp, 1)

# 6. Discovery View: Popular Board Pills & Active Company Banner
target_pills = """              {/* Categorized Multi-ATS Popular Board Pills */}
              <div className="space-y-2 pt-2 text-xs border-t border-slate-800/60">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20 uppercase">Greenhouse</span>
                  {['cloudflare', 'gitlab', 'stripe', 'figma'].map((b) => (
                    <button
                      key={b}
                      onClick={() => {
                        setBoardInput(b);
                        handleGreenhouseSearch(b);
                      }}
                      className="px-2.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 capitalize transition text-[11px]"
                    >
                      {b}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20 uppercase">Ashby</span>
                  {['linear', 'ramp', 'notion'].map((b) => (
                    <button
                      key={b}
                      onClick={() => {
                        setBoardInput(b);
                        handleGreenhouseSearch(b);
                      }}
                      className="px-2.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 capitalize transition text-[11px]"
                    >
                      {b}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 uppercase">Lever</span>
                  {['spotify', 'rover'].map((b) => (
                    <button
                      key={b}
                      onClick={() => {
                        setBoardInput(b);
                        handleGreenhouseSearch(b);
                      }}
                      className="px-2.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 capitalize transition text-[11px]"
                    >
                      {b}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">"""

repl_pills = """              {/* Categorized Multi-ATS Popular Board Pills */}
              <div className="space-y-2 pt-2 text-xs border-t border-slate-800/60">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20 uppercase">Greenhouse</span>
                  {['cloudflare', 'gitlab', 'stripe', 'figma'].map((b) => (
                    <button
                      key={b}
                      onClick={() => handleSelectCompany(b)}
                      title={`Click to isolate ${b} and remove other jobs`}
                      className={`px-2.5 py-0.5 rounded border capitalize transition text-[11px] ${
                        selectedCompany?.toLowerCase() === b.toLowerCase()
                          ? 'bg-sky-600 text-white border-sky-500 font-semibold'
                          : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                      }`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20 uppercase">Ashby</span>
                  {['linear', 'ramp', 'notion'].map((b) => (
                    <button
                      key={b}
                      onClick={() => handleSelectCompany(b)}
                      title={`Click to isolate ${b} and remove other jobs`}
                      className={`px-2.5 py-0.5 rounded border capitalize transition text-[11px] ${
                        selectedCompany?.toLowerCase() === b.toLowerCase()
                          ? 'bg-purple-600 text-white border-purple-500 font-semibold'
                          : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                      }`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 uppercase">Lever</span>
                  {['spotify', 'rover'].map((b) => (
                    <button
                      key={b}
                      onClick={() => handleSelectCompany(b)}
                      title={`Click to isolate ${b} and remove other jobs`}
                      className={`px-2.5 py-0.5 rounded border capitalize transition text-[11px] ${
                        selectedCompany?.toLowerCase() === b.toLowerCase()
                          ? 'bg-amber-600 text-white border-amber-500 font-semibold'
                          : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                      }`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {selectedCompany && (
              <div className="flex items-center justify-between bg-sky-950/70 border border-sky-800/80 px-4 py-2.5 rounded-xl text-xs text-sky-200 shadow-sm animate-in fade-in duration-150">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-sky-400" />
                  <span>Only showing jobs for <strong className="text-white capitalize">{selectedCompany}</strong> (all other jobs removed)</span>
                </div>
                <button
                  onClick={handleClearCompanyFilter}
                  className="px-2.5 py-1 rounded-lg bg-sky-900/80 hover:bg-sky-800 text-sky-100 border border-sky-700/60 flex items-center gap-1 transition text-xs font-medium"
                >
                  <X className="w-3.5 h-3.5" />
                  Show All Companies
                </button>
              </div>
            )}

            <div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">"""

assert target_pills in text, "target_pills not found"
text = text.replace(target_pills, repl_pills)

# 7. Discovery Job Card: Clickable company badge
target_disc_comp = """                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium text-sky-400">{job.company}</span>"""

repl_disc_comp = """                          <div>
                            <div className="flex items-center gap-2">
                              <span
                                onClick={() => handleSelectCompany(job.company)}
                                title={`Click to show only jobs from ${job.company} and remove other jobs`}
                                className="text-xs font-medium text-sky-400 hover:text-sky-300 hover:underline cursor-pointer flex items-center gap-1 transition"
                              >
                                <Building2 className="w-3 h-3 text-sky-400" />
                                {job.company}
                              </span>"""

assert target_disc_comp in text, "target_disc_comp not found"
text = text.replace(target_disc_comp, repl_disc_comp)

# 8. Discovery Empty State: Reset & Filter awareness
target_empty = """              {filteredJobs.length === 0 && (
                <div className="bg-slate-900/40 border border-dashed border-slate-800 rounded-xl p-12 text-center space-y-3">
                  <Compass className="w-8 h-8 text-slate-500 mx-auto" />
                  <h4 className="text-sm font-semibold text-white">No jobs found under "{filter}"</h4>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    Try searching for another company board (like <code>linear</code> or <code>spotify</code>) or click <strong>"Rank All Jobs"</strong>.
                  </p>
                </div>
              )}"""

repl_empty = """              {filteredJobs.length === 0 && (
                <div className="bg-slate-900/40 border border-dashed border-slate-800 rounded-xl p-12 text-center space-y-4">
                  <Briefcase className="w-10 h-10 text-slate-500 mx-auto" />
                  <div className="space-y-1">
                    <h4 className="text-sm font-semibold text-white">
                      {selectedCompany ? `No jobs found for "${selectedCompany}"` : 'Pipeline Reset (0 Jobs)'}
                    </h4>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto">
                      {selectedCompany
                        ? 'Try clearing the company filter or searching for another company board.'
                        : 'Upload a resume or click any company below to discover live jobs!'}
                    </p>
                  </div>
                  <div className="flex items-center justify-center gap-2 flex-wrap pt-1">
                    {selectedCompany ? (
                      <button
                        onClick={handleClearCompanyFilter}
                        className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-sky-600 hover:bg-sky-500 text-white transition flex items-center gap-1.5"
                      >
                        <RefreshCw className="w-3.5 h-3.5" /> Show All Companies
                      </button>
                    ) : (
                      ['cloudflare', 'gitlab', 'linear', 'spotify', 'stripe'].map((b) => (
                        <button
                          key={b}
                          onClick={() => handleSelectCompany(b)}
                          className="px-3 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 capitalize transition"
                        >
                          Discover {b}
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}"""

assert target_empty in text, "target_empty not found"
text = text.replace(target_empty, repl_empty)

# 9. Tracker Table: Clickable company badge
target_track_comp = """                          <td className="px-5 py-4">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-semibold text-sky-400">{job.company}</span>"""

repl_track_comp = """                          <td className="px-5 py-4">
                            <div className="flex items-center gap-2">
                              <span
                                onClick={() => {
                                  handleSelectCompany(job.company);
                                  setNavView('discovery');
                                }}
                                title={`Click to show only jobs from ${job.company} and remove other jobs`}
                                className="text-[11px] font-semibold text-sky-400 hover:text-sky-300 hover:underline cursor-pointer flex items-center gap-1 transition"
                              >
                                <Building2 className="w-3 h-3 text-sky-400" />
                                {job.company}
                              </span>"""

assert target_track_comp in text, "target_track_comp not found"
text = text.replace(target_track_comp, repl_track_comp)

# Write back
with open(app_path, "w", encoding="utf-8") as f:
    f.write(text)

print("SUCCESS: frontend/src/App.jsx updated cleanly!")
