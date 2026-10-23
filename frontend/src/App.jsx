import React, { useState, useEffect, useRef } from 'react';
import {
  Briefcase,
  Building2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Check,
  X,
  RefreshCw,
  Eye,
  Download,
  Plus,
  User,
  GraduationCap,
  Code2,
  TrendingUp,
  ListChecks,
  Compass,
  ChevronRight,
  Send,
  Monitor,
  Lock,
  Sliders,
  Trash2,
  Search,
  ExternalLink,
  UploadCloud,
  FileText,
  SlidersHorizontal,
  ArrowRight
} from 'lucide-react';

import {
  fetchProfile,
  clearProfile,
  fetchJobs,
  uploadResumeFile,
  searchGreenhouse,
  isolateCompanyJobs,
  clearAllJobs,
  resetApplications,
  rankJobs,
  startApplication,
  decideApplication,
  addManualJob,
  updateJobStatus,
  updateScreeningPreferences,
  API_BASE
} from './api';

// Filter out any mock/sample test jobs
const MOCK_COMPANIES = ['nexus systems', 'horizon apps', 'acme ai', 'mobileswift labs', 'example corp'];

function isRealJob(job) {
  if (!job || !job.id) return false;
  const id = String(job.id).toLowerCase();
  if (id.startsWith('sample_') || id.startsWith('test_') || id.startsWith('mock_') || id === 'gh_test_01') {
    return false;
  }
  const company = (job.company || '').toLowerCase().trim();
  if (MOCK_COMPANIES.includes(company)) {
    return false;
  }
  return true;
}

export default function App() {
  // Navigation: 'dashboard' | 'discovery' | 'studio' | 'tracker' | 'profile'
  const [navView, setNavView] = useState('dashboard');

  // Core Data
  const [profile, setProfile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Discovery & Filtering
  const [boardInput, setBoardInput] = useState('');
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [filter, setFilter] = useState('matched'); // 'matched' | 'all' | 'applied' | 'rejected'
  const [searchingBoard, setSearchingBoard] = useState(false);
  const [ranking, setRanking] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);

  // Manual Job Entry Modal
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualTitle, setManualTitle] = useState('');
  const [manualCompany, setManualCompany] = useState('');
  const [manualLocation, setManualLocation] = useState('Remote');
  const [manualUrl, setManualUrl] = useState('');
  const [manualDescription, setManualDescription] = useState('');
  const [savingManual, setSavingManual] = useState(false);

  // Match Analysis Modal
  const [analysisJob, setAnalysisJob] = useState(null);

  // Studio Selected Job
  const [studioJobId, setStudioJobId] = useState(null);
  const [studioTab, setStudioTab] = useState('resume'); // 'resume' | 'cover_letter' | 'profile'

  // Human Review Gate (Active Pipeline Run)
  const [applyingJobId, setApplyingJobId] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [activeReviewTab, setActiveReviewTab] = useState('preview'); // 'preview' | 'cover_letter' | 'resume' | 'audit'
  const [feedback, setFeedback] = useState('');
  const [deciding, setDeciding] = useState(false);
  const [openingBrowser, setOpeningBrowser] = useState(false);

  // Candidate Screening & Work Auth Vault
  const [screeningVault, setScreeningVault] = useState({
    authorized_to_work: true,
    requires_sponsorship: false,
    notice_period: 'Immediate',
    willing_to_relocate: true,
    work_location_preference: 'Flexible',
    pronouns: '',
    expected_salary: 'Negotiable',
    custom_qa: []
  });
  const [savingScreening, setSavingScreening] = useState(false);
  const [newCustomQ, setNewCustomQ] = useState('');
  const [newCustomA, setNewCustomA] = useState('');

  // Feedback Toast
  const [toast, setToast] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [pData, jData] = await Promise.all([
        fetchProfile().catch(() => null),
        fetchJobs().catch(() => [])
      ]);
      setProfile(pData);
      if (pData?.screening) {
        setScreeningVault(pData.screening);
      }
      setJobs(jData || []);
      if (jData && jData.length > 0 && !studioJobId) {
        setStudioJobId(jData[0].id);
      }
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResetProfile() {
    if (!window.confirm("Are you sure you want to start afresh? This will clear your uploaded resume, indexed facts, and tracked jobs so a new user can start from scratch.")) {
      return;
    }
    try {
      setLoading(true);
      await clearProfile();
      setProfile(null);
      setJobs([]);
      setSelectedCompany(null);
      setReviewData(null);
      setApplyingJobId(null);
      setAnalysisJob(null);
      setStudioJobId(null);
      setBoardInput('');
      setFilter('all');
      setScreeningVault({
        authorized_to_work: true,
        requires_sponsorship: false,
        notice_period_days: 0,
        willing_to_relocate: true,
        preferred_work_type: 'Remote',
        primary_country: 'United States',
        veteran_status: 'No',
        disability_status: 'No',
        gender: '',
        race_ethnicity: '',
        pronouns: '',
        expected_salary: 'Negotiable',
        custom_qa: []
      });
      showToast('success', 'Reset complete! You can now start afresh and upload a new resume.');
    } catch (err) {
      showToast('error', `Failed to reset: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function showToast(type, message) {
    setToast({ type, message });
    setTimeout(() => setToast(null), 5000);
  }

  function getJobMatchScore(job) {
    if (!job) return 0;
    if (job.llm_score !== null && job.llm_score !== undefined) {
      return Math.round(job.llm_score);
    }
    if (job.embedding_score !== null && job.embedding_score !== undefined) {
      const calibrated = Math.round(((job.embedding_score - 0.50) / 0.25) * 100);
      return Math.max(0, Math.min(100, calibrated));
    }
    return null;
  }

  function getJobFormUrl(url) {
    if (!url || url.includes('nexussystems') || url.includes('acme') || !url.startsWith('http')) {
      return '/test-form';
    }
    return url;
  }

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploadingResume(true);
      showToast('info', `Uploading & indexing ${file.name}...`);
      const res = await uploadResumeFile(file);
      setProfile(res.profile);
      if (res.profile?.screening) {
        setScreeningVault(res.profile.screening);
      }

      setJobs([]);
      setSelectedCompany(null);
      setReviewData(null);
      setApplyingJobId(null);
      setAnalysisJob(null);
      setStudioJobId(null);
      setBoardInput('');
      setFilter('all');

      showToast('success', res.message || `Profile updated for ${res.profile.full_name}`);
    } catch (err) {
      showToast('error', `Failed to parse resume: ${err.message}`);
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleSelectCompany(companyName) {
    if (!companyName) return;
    const cleanCompany = companyName.trim();
    setSelectedCompany(cleanCompany);
    setBoardInput(cleanCompany);

    setJobs((prev) => prev.filter((j) => (j.company || '').toLowerCase() === cleanCompany.toLowerCase()));

    try {
      setSearchingBoard(true);
      const res = await searchGreenhouse(cleanCompany, true);
      if (res.jobs && res.jobs.length > 0) {
        setJobs(res.jobs);
        if (res.jobs.length > 0) {
          setStudioJobId(res.jobs[0].id);
        }
      } else {
        const iso = await isolateCompanyJobs(cleanCompany);
        if (iso.jobs) setJobs(iso.jobs);
      }
    } catch (err) {
      console.warn('Search fallback to isolate:', err);
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
    });
  }

  async function handleGreenhouseSearch(token) {
    const query = (token || boardInput || '').trim();
    if (!query) {
      showToast('error', 'Please enter a company name (e.g. cloudflare, gitlab, stripe, notion).');
      return;
    }

    try {
      setSearchingBoard(true);
      setSelectedCompany(query);
      const res = await searchGreenhouse(query, true);
      if (res.status === 'warning') {
        showToast('error', res.message);
      } else {
        showToast('success', `Found ${res.count || (res.jobs ? res.jobs.length : 0)} openings for ${query}`);
      }
      const updated = await fetchJobs();
      setJobs(updated);
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setSearchingBoard(false);
    }
  }

  async function handleRank() {
    try {
      setRanking(true);
      showToast('info', 'Analyzing profile alignment across all positions...');
      const res = await rankJobs();
      setJobs(res.ranked_jobs);
      showToast('success', `Evaluated ${res.ranked_jobs.length} jobs.`);
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setRanking(false);
    }
  }

  async function handleManualJobSubmit(e) {
    e.preventDefault();
    if (!manualTitle.trim() || !manualCompany.trim() || !manualDescription.trim()) {
      showToast('error', 'Title, Company, and Description are required.');
      return;
    }

    try {
      setSavingManual(true);
      const res = await addManualJob({
        title: manualTitle,
        company: manualCompany,
        location: manualLocation,
        url: manualUrl,
        description: manualDescription
      });
      showToast('success', res.message || 'Job added successfully');
      setShowManualModal(false);
      setManualTitle('');
      setManualCompany('');
      setManualDescription('');
      const updated = await fetchJobs();
      setJobs(updated);
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setSavingManual(false);
    }
  }

  async function handleStatusChange(jobId, newStatus) {
    try {
      await updateJobStatus(jobId, newStatus);
      showToast('success', `Status updated to ${newStatus}`);
      const updated = await fetchJobs();
      setJobs(updated);
    } catch (err) {
      showToast('error', err.message);
    }
  }

  async function handleStartApplication(jobId) {
    try {
      setApplyingJobId(jobId);
      showToast('info', 'Preparing application package and populating form...');
      const result = await startApplication(jobId);
      setReviewData(result);
      setActiveReviewTab('preview');
      showToast('success', 'Form prepared. Paused for your final review.');
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setApplyingJobId(null);
    }
  }

  async function handleDecision(approve) {
    if (!reviewData) return;
    try {
      setDeciding(true);
      const res = await decideApplication(reviewData.thread_id, approve, feedback);
      showToast(approve ? 'success' : 'info', res.message);
      setReviewData(null);
      setFeedback('');
      const updatedJobs = await fetchJobs();
      setJobs(updatedJobs);
    } catch (err) {
      showToast('error', err.message);
    } finally {
      setDeciding(false);
    }
  }

  async function handleOpenLiveBrowser(jobId) {
    if (!jobId) return;
    try {
      setOpeningBrowser(true);
      showToast('info', 'Opening Chromium browser window...');
      const res = await fetch(`${API_BASE}/api/applications/open-browser`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId })
      });
      const data = await res.json();
      if (res.ok) {
        showToast('success', data.message || 'Browser opened');
      } else {
        showToast('error', data.detail || 'Could not open browser window.');
      }
    } catch (err) {
      showToast('error', 'Error launching browser: ' + err.message);
    } finally {
      setOpeningBrowser(false);
    }
  }

  async function handleSaveScreening() {
    try {
      setSavingScreening(true);
      const res = await updateScreeningPreferences(screeningVault);
      showToast('success', res.message || 'Preferences updated');
      const updated = await fetchProfile();
      setProfile(updated);
    } catch (err) {
      showToast('error', err.message || 'Failed to save preferences');
    } finally {
      setSavingScreening(false);
    }
  }

  function handleAddCustomQA() {
    if (!newCustomQ.trim() || !newCustomA.trim()) {
      showToast('error', 'Please enter both the question and answer.');
      return;
    }
    setScreeningVault(prev => ({
      ...prev,
      custom_qa: [...(prev.custom_qa || []), { question: newCustomQ.trim(), answer: newCustomA.trim(), tags: [] }]
    }));
    setNewCustomQ('');
    setNewCustomA('');
  }

  function handleRemoveCustomQA(index) {
    setScreeningVault(prev => ({
      ...prev,
      custom_qa: (prev.custom_qa || []).filter((_, i) => i !== index)
    }));
  }

  const uniqueJobs = Array.from(
    jobs.filter(isRealJob).reduce((map, job) => {
      const normTitle = (job.title || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      const normCompany = (job.company || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      const key = `${normCompany}_${normTitle}`;
      if (!map.has(key)) {
        map.set(key, job);
      }
      return map;
    }, new Map()).values()
  );

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
  });

  const matchedCount = uniqueJobs.filter((j) => {
    const s = getJobMatchScore(j);
    return s !== null && s > 60 && j.status !== 'rejected_by_user';
  }).length;
  const appliedCount = uniqueJobs.filter((j) => j.status === 'applied').length;
  const pendingCount = reviewData ? 1 : 0;

  const currentStudioJob = uniqueJobs.find((j) => j.id === studioJobId) || uniqueJobs[0];

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 text-slate-800">
        <RefreshCw className="w-7 h-7 text-slate-700 animate-spin mb-3" />
        <h2 className="text-sm font-semibold text-slate-900">Loading Application Workspace...</h2>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-20 selection:bg-slate-900 selection:text-white">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 flex items-center gap-2.5 px-4 py-3 rounded-lg shadow-lg text-xs font-medium border animate-in slide-in-from-top-2 duration-200 ${
            toast.type === 'error'
              ? 'bg-rose-50 border-rose-200 text-rose-800'
              : toast.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-white border-slate-200 text-slate-800 shadow-md'
          }`}
        >
          {toast.type === 'error' ? (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Hidden File Input for Resume Upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept=".pdf,.docx,.txt,.json"
        className="hidden"
      />

      {/* Top Navbar */}
      <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur-md sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 text-white flex items-center justify-center font-bold text-sm tracking-tight shadow-sm shadow-indigo-200">
              CP
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-semibold text-slate-900 text-sm tracking-tight">CareerPortal</h1>
                {profile ? (
                  <div className="flex items-center gap-1.5">
                    <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                      {profile.full_name}
                    </span>
                    <button
                      onClick={handleResetProfile}
                      title="Clear session and start afresh"
                      className="px-2 py-0.5 rounded text-[10px] font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50 border border-rose-200 transition active:scale-95"
                    >
                      Start Afresh
                    </button>
                  </div>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                    No Resume Uploaded
                  </span>
                )}
                <span className="hidden sm:inline-flex px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/80 uppercase tracking-wide">
                  Greenhouse • Ashby • Lever
                </span>
              </div>
              <p className="text-[11px] text-slate-500">Autonomous Application & Screening Assistant</p>
            </div>
          </div>

          {/* Quick Header Actions */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingResume}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs transition hover:border-slate-400 disabled:opacity-50"
            >
              <UploadCloud className={`w-3.5 h-3.5 ${uploadingResume ? 'animate-bounce text-indigo-600' : 'text-slate-500'}`} />
              {uploadingResume ? 'Processing...' : 'Upload Resume'}
            </button>
            <button
              onClick={handleRank}
              disabled={ranking}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm shadow-indigo-100 transition hover:shadow-md disabled:opacity-50"
            >
              <TrendingUp className={`w-3.5 h-3.5 ${ranking ? 'animate-spin' : ''}`} />
              {ranking ? 'Evaluating...' : 'Score Matches'}
            </button>
          </div>
        </div>

        {/* Module Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-6 flex items-center gap-1 overflow-x-auto border-t border-slate-100 text-xs">
          {[
            { id: 'dashboard', label: 'Overview', icon: Briefcase },
            { id: 'discovery', label: 'Find Jobs', icon: Compass, count: matchedCount },
            { id: 'studio', label: 'Document Studio', icon: FileText },
            { id: 'tracker', label: 'Applications', icon: ListChecks, count: appliedCount },
            { id: 'profile', label: 'Profile & Preferences', icon: User }
          ].map((tab) => {
            const Icon = tab.icon;
            const active = navView === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setNavView(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 font-medium border-b-2 transition whitespace-nowrap ${
                  active
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50/50 font-semibold'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? 'text-indigo-600' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {tab.count !== undefined && tab.count > 0 && (
                  <span
                    className={`px-1.5 py-0.2 rounded-full text-[10px] font-semibold transition ${
                      active ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 pt-6 space-y-6">
        {/* VIEW 1: DASHBOARD */}
        {navView === 'dashboard' && (
          <div className="space-y-6">
            {/* Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white border border-slate-200/90 rounded-xl p-5 shadow-xs hover:shadow-md hover:border-slate-300 transition duration-200 group">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-xs font-medium text-slate-600">Available Openings</span>
                  <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100/80 group-hover:scale-105 transition">
                    <Briefcase className="w-4 h-4" />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-slate-900">{uniqueJobs.length}</span>
                  <span className="text-xs text-slate-500">in pipeline</span>
                </div>
              </div>

              <div className="bg-white border border-slate-200/90 rounded-xl p-5 shadow-xs hover:shadow-md hover:border-slate-300 transition duration-200 group">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-xs font-medium text-slate-600">High Match (&gt;60%)</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100/80 group-hover:scale-105 transition">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-emerald-600">{matchedCount}</span>
                  <span className="text-xs text-slate-500">recommended</span>
                </div>
              </div>

              <div className="bg-white border border-slate-200/90 rounded-xl p-5 shadow-xs hover:shadow-md hover:border-slate-300 transition duration-200 group">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-xs font-medium text-slate-600">Awaiting Review</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-100/80 group-hover:scale-105 transition">
                    <Clock className="w-4 h-4" />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-amber-600">{pendingCount}</span>
                  <span className="text-xs text-slate-500">in review gate</span>
                </div>
              </div>

              <div className="bg-white border border-slate-200/90 rounded-xl p-5 shadow-xs hover:shadow-md hover:border-slate-300 transition duration-200 group">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-xs font-medium text-slate-600">Submitted</span>
                  <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-100/80 group-hover:scale-105 transition">
                    <Send className="w-4 h-4" />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-indigo-600">{appliedCount}</span>
                  <span className="text-xs text-slate-500">tracked</span>
                </div>
              </div>
            </div>

            {/* Recommended Positions & Profile Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 bg-white border border-slate-200/90 rounded-xl p-6 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Recommended Roles</h3>
                    <p className="text-xs text-slate-500 mt-0.5">Top alignment with your background</p>
                  </div>
                  <button
                    onClick={() => {
                      setFilter('matched');
                      setNavView('discovery');
                    }}
                    className="text-xs text-indigo-600 hover:text-indigo-700 font-semibold flex items-center gap-1"
                  >
                    View All <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="space-y-3">
                  {uniqueJobs
                    .filter((j) => (getJobMatchScore(j) || 0) >= 70)
                    .slice(0, 4)
                    .map((job) => {
                      const score = getJobMatchScore(job);
                      return (
                        <div
                          key={job.id}
                          className="border border-slate-200/80 hover:border-indigo-200 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 transition bg-white hover:bg-indigo-50/20 hover:shadow-xs"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span
                                onClick={() => {
                                  handleSelectCompany(job.company);
                                  setNavView('discovery');
                                }}
                                className="text-xs font-semibold text-slate-900 hover:text-indigo-600 hover:underline cursor-pointer flex items-center gap-1 transition"
                              >
                                <Building2 className="w-3.5 h-3.5 text-slate-500" />
                                {job.company}
                              </span>
                              <span className={`text-[10px] px-2 py-0.5 rounded font-semibold uppercase ${
                                job.platform === 'ashby'
                                  ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                  : job.platform === 'lever'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-sky-50 text-sky-700 border border-sky-200'
                              }`}>
                                {job.platform || 'greenhouse'}
                              </span>
                              <span className="text-slate-300">•</span>
                              <span className="text-xs text-slate-500">{job.location}</span>
                            </div>
                            <h4 className="text-sm font-semibold text-slate-900 mt-1">{job.title}</h4>
                            {job.llm_reasoning && (
                              <p className="text-xs text-slate-600 mt-1 line-clamp-1 border-l-2 border-indigo-400 pl-2 bg-indigo-50/30 py-0.5 rounded-r">{job.llm_reasoning}</p>
                            )}
                          </div>

                          <div className="flex items-center gap-3 shrink-0 w-full sm:w-auto justify-between sm:justify-end">
                            <span className="px-2.5 py-1 rounded text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs">
                              {score}% Match
                            </span>
                            <button
                              onClick={() => handleStartApplication(job.id)}
                              disabled={applyingJobId === job.id}
                              className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white transition disabled:opacity-50 flex items-center gap-1.5 shadow-xs shadow-indigo-100 active:scale-95"
                            >
                              {applyingJobId === job.id ? 'Preparing...' : 'Review & Apply'}
                            </button>
                          </div>
                        </div>
                      );
                    })}

                  {uniqueJobs.filter((j) => (getJobMatchScore(j) || 0) >= 70).length === 0 && (
                    <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-200 rounded-lg">
                      No roles scored above 70% yet. Click <strong>"Score Matches"</strong> to evaluate fits.
                    </div>
                  )}
                </div>
              </div>

              {profile ? (
                <div className="bg-white border border-slate-200/90 rounded-xl p-6 shadow-xs flex flex-col justify-between border-t-2 border-t-indigo-600">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                        <User className="w-4 h-4 text-indigo-600" />
                        Candidate Profile
                      </h3>
                      <button
                        onClick={() => setNavView('profile')}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                      >
                        Edit
                      </button>
                    </div>

                    <div>
                      <h4 className="text-base font-semibold text-slate-900">{profile.full_name}</h4>
                      <p className="text-xs text-slate-500">{profile.email}</p>
                      <p className="text-xs text-slate-500">{profile.location}</p>
                    </div>

                    <div className="border-t border-slate-100 pt-3">
                      <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Top Projects</span>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {profile.projects?.slice(0, 4).map((p) => (
                          <span
                            key={p.title}
                            className="px-2 py-0.5 rounded text-xs bg-slate-50 text-slate-700 border border-slate-200"
                          >
                            {p.title}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-100 mt-4 flex items-center justify-between text-xs text-slate-500">
                    <span>Work Authorization</span>
                    <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {screeningVault.authorized_to_work ? 'Authorized' : 'Requires Auth'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="bg-white border border-slate-200/90 rounded-xl p-6 shadow-xs flex flex-col items-center justify-center text-center border-t-2 border-t-indigo-600">
                  <div className="w-12 h-12 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center mb-3">
                    <UploadCloud className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">Upload Your Resume</h3>
                  <p className="text-xs text-slate-500 mt-1.5 max-w-xs">
                    Upload your resume to automatically extract your skills, index your experience in vector search, and score jobs.
                  </p>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingResume}
                    className="mt-4 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs shadow-indigo-100 transition active:scale-95 disabled:opacity-50"
                  >
                    {uploadingResume ? 'Processing...' : 'Upload Resume (.pdf, .docx)'}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* VIEW 2: JOB DISCOVERY & PIPELINE */}
        {navView === 'discovery' && (
          <div className="space-y-6">
            {/* Search and Filters Header */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Job Board Search</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Explore active openings from Greenhouse, Ashby, and Lever</p>
                </div>
                <button
                  onClick={() => setShowManualModal(true)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs flex items-center gap-1.5 transition"
                >
                  <Plus className="w-3.5 h-3.5 text-slate-600" />
                  Add Custom Job
                </button>
              </div>

              <div className="flex flex-col sm:flex-row items-center gap-3">
                <div className="relative flex-1 w-full">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Search company (cloudflare, gitlab, stripe, figma, linear)..."
                    value={boardInput}
                    onChange={(e) => setBoardInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleGreenhouseSearch()}
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white border border-slate-300 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  />
                </div>
                <button
                  onClick={() => handleGreenhouseSearch()}
                  disabled={searchingBoard}
                  className="w-full sm:w-auto px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white transition disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-xs shadow-indigo-100 active:scale-95"
                >
                  <Search className={`w-3.5 h-3.5 ${searchingBoard ? 'animate-spin' : ''}`} />
                  {searchingBoard ? 'Searching...' : 'Search Board'}
                </button>
              </div>

              {/* Categorized Multi-ATS Popular Board Pills */}
              <div className="space-y-2 pt-2 text-xs border-t border-slate-100">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 uppercase tracking-wide">Greenhouse</span>
                  {['gitlab', 'cloudflare', 'stripe', 'figma'].map((b) => (
                    <button
                      key={b}
                      onClick={() => handleSelectCompany(b)}
                      className={`px-2.5 py-0.5 rounded border capitalize transition text-xs ${
                        selectedCompany?.toLowerCase() === b.toLowerCase()
                          ? 'bg-sky-600 text-white border-sky-600 font-medium shadow-xs'
                          : 'bg-white hover:bg-sky-50 text-slate-700 border-slate-200 hover:border-sky-300'
                      }`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200 uppercase tracking-wide">Ashby</span>
                  {['linear', 'ramp', 'notion'].map((b) => (
                    <button
                      key={b}
                      onClick={() => handleSelectCompany(b)}
                      className={`px-2.5 py-0.5 rounded border capitalize transition text-xs ${
                        selectedCompany?.toLowerCase() === b.toLowerCase()
                          ? 'bg-purple-600 text-white border-purple-600 font-medium shadow-xs'
                          : 'bg-white hover:bg-purple-50 text-slate-700 border-slate-200 hover:border-purple-300'
                      }`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 uppercase tracking-wide">Lever</span>
                  {['spotify', 'rover'].map((b) => (
                    <button
                      key={b}
                      onClick={() => handleSelectCompany(b)}
                      className={`px-2.5 py-0.5 rounded border capitalize transition text-xs ${
                        selectedCompany?.toLowerCase() === b.toLowerCase()
                          ? 'bg-amber-600 text-white border-amber-600 font-medium shadow-xs'
                          : 'bg-white hover:bg-amber-50 text-slate-700 border-slate-200 hover:border-amber-300'
                      }`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {selectedCompany && (
              <div className="flex items-center justify-between bg-indigo-50/50 border border-indigo-200/80 px-4 py-2.5 rounded-lg text-xs text-slate-800">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-indigo-600" />
                  <span>Filtered to company: <strong className="capitalize text-slate-900">{selectedCompany}</strong></span>
                </div>
                <button
                  onClick={handleClearCompanyFilter}
                  className="px-2 py-1 rounded text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-xs flex items-center gap-1 transition"
                >
                  <X className="w-3 h-3" /> Clear Filter
                </button>
              </div>
            )}

            {/* Job Grid & Filtering */}
            <div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Positions ({filteredJobs.length})</h3>
                </div>

                <div className="flex items-center gap-1 bg-white border border-slate-200 p-1 rounded-lg text-xs shadow-xs">
                  {[
                    { id: 'matched', label: 'Recommended (>60%)' },
                    { id: 'all', label: 'All' },
                    { id: 'applied', label: 'Applied' },
                    { id: 'rejected', label: 'Passed' }
                  ].map((f) => (
                    <button
                      key={f.id}
                      onClick={() => setFilter(f.id)}
                      className={`px-3 py-1 rounded transition font-medium ${
                        filter === f.id
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredJobs.map((job) => {
                  const score = getJobMatchScore(job);
                  const isApplied = job.status === 'applied';

                  return (
                    <div
                      key={job.id}
                      className="bg-white border border-slate-200 hover:border-indigo-300 rounded-xl p-5 flex flex-col justify-between transition-all duration-200 shadow-xs hover:shadow-md group"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2">
                              <span
                                onClick={() => handleSelectCompany(job.company)}
                                className="text-xs font-semibold text-slate-900 hover:text-indigo-600 hover:underline cursor-pointer flex items-center gap-1 transition"
                              >
                                <Building2 className="w-3.5 h-3.5 text-slate-500" />
                                {job.company}
                              </span>
                              <span className={`text-[10px] px-2 py-0.5 rounded font-semibold uppercase ${
                                job.platform === 'ashby'
                                  ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                  : job.platform === 'lever'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-sky-50 text-sky-700 border border-sky-200'
                              }`}>
                                {job.platform || 'greenhouse'}
                              </span>
                            </div>
                            <h4 className="text-sm font-semibold text-slate-900 mt-1 line-clamp-1">
                              {job.title}
                            </h4>
                            <p className="text-xs text-slate-500 mt-0.5">{job.location}</p>
                          </div>

                          {score !== null && (
                            <div
                              className={`px-2 py-0.5 rounded text-xs font-bold border shrink-0 ${
                                score >= 75
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 shadow-2xs'
                                  : score >= 60
                                  ? 'bg-amber-50 text-amber-700 border-amber-200 shadow-2xs'
                                  : 'bg-slate-100 text-slate-600 border-slate-200'
                              }`}
                            >
                              {score}%
                            </div>
                          )}
                        </div>

                        {job.llm_reasoning ? (
                          <div className="p-3 rounded-lg bg-indigo-50/40 border border-indigo-100/80 text-xs text-slate-700 leading-relaxed line-clamp-3">
                            {job.llm_reasoning}
                          </div>
                        ) : (
                          <p className="text-xs text-slate-600 line-clamp-3 leading-relaxed">
                            {job.description}
                          </p>
                        )}
                      </div>

                      <div className="pt-4 border-t border-slate-100 mt-4 flex items-center justify-between gap-2">
                        <button
                          onClick={() => setAnalysisJob(job)}
                          className="text-xs text-slate-600 hover:text-indigo-600 font-medium flex items-center gap-1 transition"
                        >
                          <Eye className="w-3.5 h-3.5" /> Details
                        </button>

                        <div className="flex items-center gap-2">
                          <a
                            href={getJobFormUrl(job.url)}
                            target="_blank"
                            rel="noreferrer"
                            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-transparent transition"
                            title="Open direct job posting"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>

                          <button
                            onClick={() => handleStartApplication(job.id)}
                            disabled={applyingJobId === job.id || isApplied}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${
                              isApplied
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 cursor-default font-semibold'
                                : 'bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 shadow-xs shadow-indigo-100 active:scale-95'
                            }`}
                          >
                            {isApplied ? (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Applied
                              </>
                            ) : applyingJobId === job.id ? (
                              <>
                                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Preparing...
                              </>
                            ) : (
                              <>
                                <Send className="w-3.5 h-3.5" /> Review & Apply
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {filteredJobs.length === 0 && (
                <div className="bg-white border border-dashed border-slate-200 rounded-xl p-12 text-center space-y-3">
                  <Briefcase className="w-8 h-8 text-slate-400 mx-auto" />
                  <div className="space-y-1">
                    <h4 className="text-sm font-semibold text-slate-900">
                      {selectedCompany ? `No roles found for "${selectedCompany}"` : 'No matching jobs available'}
                    </h4>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                      Search for a company board above or adjust your filters.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* VIEW 3: DOCUMENT STUDIO */}
        {navView === 'studio' && (
          <div className="space-y-6">
            <div className="bg-white border border-slate-200 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-slate-700" />
                  Document Studio
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Tailored resumes and cover letters aligned to target requirements
                </p>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-600 font-medium">Role:</span>
                <select
                  value={studioJobId || ''}
                  onChange={(e) => setStudioJobId(e.target.value)}
                  className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                >
                  {uniqueJobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.company} — {j.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {currentStudioJob && (
              <div className="space-y-6">
                <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                  <div className="flex items-center gap-2">
                    {[
                      { id: 'resume', label: 'Tailored Resume' },
                      { id: 'cover_letter', label: 'Cover Letter' }
                    ].map((st) => (
                      <button
                        key={st.id}
                        onClick={() => setStudioTab(st.id)}
                        className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${
                          studioTab === st.id
                            ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-100 font-semibold'
                            : 'bg-white text-slate-700 hover:text-slate-900 border border-slate-200 shadow-xs hover:bg-slate-50'
                        }`}
                      >
                        {st.label}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-2">
                    {studioTab === 'resume' ? (
                      <>
                        <a
                          href={`${API_BASE}/exports/${currentStudioJob.id}_resume.pdf`}
                          download={`${profile?.full_name ? profile.full_name.replace(/\s+/g, '_') : 'Tailored'}_Resume.pdf`}
                          className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white shadow-xs shadow-indigo-200 flex items-center gap-1.5 transition active:scale-95"
                        >
                          <Download className="w-3.5 h-3.5 text-white" />
                          Download PDF
                        </a>
                        <a
                          href={`${API_BASE}/exports/${currentStudioJob.id}_resume.docx`}
                          download
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs flex items-center gap-1.5 transition"
                        >
                          <Download className="w-3.5 h-3.5 text-slate-500" />
                          Word (.docx)
                        </a>
                      </>
                    ) : (
                      <>
                        <a
                          href={`${API_BASE}/exports/${currentStudioJob.id}_cover_letter.pdf`}
                          download={`${profile?.full_name ? profile.full_name.replace(/\s+/g, '_') : 'Tailored'}_Cover_Letter.pdf`}
                          className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white shadow-xs shadow-indigo-200 flex items-center gap-1.5 transition active:scale-95"
                        >
                          <Download className="w-3.5 h-3.5 text-white" />
                          Download PDF
                        </a>
                        <a
                          href={`${API_BASE}/exports/${currentStudioJob.id}_cover_letter.docx`}
                          download
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs flex items-center gap-1.5 transition"
                        >
                          <Download className="w-3.5 h-3.5 text-slate-500" />
                          Word (.docx)
                        </a>
                      </>
                    )}
                  </div>
                </div>

                {studioTab === 'resume' && (
                  <div className="bg-white border border-slate-200 rounded-xl p-8 space-y-6 shadow-xs max-w-4xl mx-auto border-t-4 border-t-indigo-600">
                    <div className="border-b border-slate-200 pb-4">
                      <span className="text-xs font-medium text-indigo-600 uppercase tracking-wider font-semibold">Target Position: {currentStudioJob.title}</span>
                      <h2 className="text-xl font-bold text-slate-900 mt-1">{profile?.full_name}</h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {profile?.email} • {profile?.phone} • {profile?.location}
                      </p>
                    </div>

                    <div>
                      <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">
                        Professional Summary
                      </h4>
                      <p className="text-xs text-slate-700 leading-relaxed bg-slate-50/70 p-4 rounded-xl border border-slate-200/80">
                        {profile?.summary}
                      </p>
                    </div>

                    <div>
                      <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">
                        Featured Projects
                      </h4>
                      <div className="space-y-4">
                        {profile?.projects?.map((proj) => (
                          <div key={proj.title} className="bg-slate-50/70 p-4 rounded-xl border border-slate-200/80 space-y-2 hover:border-indigo-200 transition">
                            <div className="flex items-center justify-between">
                              <h5 className="text-sm font-semibold text-slate-900">{proj.title}</h5>
                              <span className="text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded shadow-2xs">Verified Fact</span>
                            </div>
                            <p className="text-xs text-slate-600">{proj.description}</p>
                            <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 pt-1">
                              {proj.highlights?.map((h, i) => (
                                <li key={i}>{h}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">Education</h4>
                      <div className="space-y-2">
                        {profile?.education?.map((edu, i) => (
                          <div key={i} className="text-xs text-slate-700 bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                            <strong>{edu.institution}</strong> — {edu.degree} in {edu.field_of_study} ({edu.start_year || '2024'} - {edu.end_year || '2027'})
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {studioTab === 'cover_letter' && (
                  <div className="bg-white border border-slate-200 rounded-xl p-8 space-y-4 max-w-3xl mx-auto shadow-xs border-t-4 border-t-indigo-600">
                    <div className="text-xs text-slate-600 space-y-1 border-b border-slate-200 pb-4">
                      <p className="font-semibold text-slate-900 text-base">{profile?.full_name}</p>
                      <p>{profile?.email} | {profile?.phone}</p>
                      <p className="pt-2 text-slate-700 font-medium">
                        Hiring Team <br />
                        {currentStudioJob.company} <br />
                        Re: Application for {currentStudioJob.title}
                      </p>
                    </div>

                    <div className="text-xs text-slate-700 leading-relaxed space-y-4 pt-2">
                      <p>Dear Hiring Team,</p>
                      <p>
                        I am writing to express my strong interest in the {currentStudioJob.title} position at {currentStudioJob.company}. 
                        With a solid foundation in engineering, software development, and technical problem solving, 
                        I am eager to contribute effectively to your engineering objectives.
                      </p>
                      <p>
                        Through hands-on projects, I have engineered backend systems, designed data workflows, 
                        and built scalable solutions with high reliability and clean code standards.
                      </p>
                      <p>
                        Thank you for your consideration. I look forward to the opportunity to discuss my qualifications with your team.
                      </p>
                      <p className="pt-2">
                        Sincerely,<br />
                        <strong className="text-slate-900">{profile?.full_name}</strong>
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {!currentStudioJob && (
              <div className="bg-white border border-dashed border-slate-200 rounded-xl p-12 text-center space-y-3">
                <FileText className="w-8 h-8 text-slate-400 mx-auto" />
                <h4 className="text-sm font-semibold text-slate-900">No Job Selected</h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Upload your resume and search or add jobs to generate and preview tailored resumes and cover letters in real time.
                </p>
              </div>
            )}
          </div>
        )}

        {/* VIEW 4: APPLICATION TRACKER */}
        {navView === 'tracker' && (
          <div className="space-y-6">
            <div className="bg-white border border-slate-200 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                  <ListChecks className="w-4 h-4 text-slate-700" />
                  Application Tracker
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Track the progress of your applications across boards
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                  Total Tracked: <strong className="text-slate-900">{uniqueJobs.length}</strong>
                </span>
                <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Submitted: <strong className="text-emerald-900">{uniqueJobs.filter(j => j.status === 'applied').length}</strong>
                </span>
                {uniqueJobs.filter(j => j.status === 'applied').length > 0 && (
                  <button
                    onClick={async () => {
                      try {
                        await resetApplications();
                        const updated = await fetchJobs();
                        setJobs(updated);
                        showToast('success', 'Reset statuses back to discovered.');
                      } catch (err) {
                        showToast('error', err.message);
                      }
                    }}
                    className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs transition flex items-center gap-1.5 active:scale-95"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Reset
                  </button>
                )}
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-700">
                  <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-200 font-semibold">
                    <tr>
                      <th className="px-5 py-3">Company & Role</th>
                      <th className="px-5 py-3">Location</th>
                      <th className="px-5 py-3">Fit</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {uniqueJobs.map((job) => {
                      const score = getJobMatchScore(job);
                      return (
                        <tr key={job.id} className="hover:bg-indigo-50/20 transition">
                          <td className="px-5 py-4">
                            <div className="flex items-center gap-2">
                              <span
                                onClick={() => {
                                  handleSelectCompany(job.company);
                                  setNavView('discovery');
                                }}
                                className="text-xs font-semibold text-slate-900 hover:text-indigo-600 hover:underline cursor-pointer flex items-center gap-1 transition"
                              >
                                <Building2 className="w-3.5 h-3.5 text-slate-500" />
                                {job.company}
                              </span>
                              <span className={`text-[10px] px-2 py-0.5 rounded font-semibold uppercase ${
                                job.platform === 'ashby'
                                  ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                  : job.platform === 'lever'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-sky-50 text-sky-700 border border-sky-200'
                              }`}>
                                {job.platform || 'greenhouse'}
                              </span>
                            </div>
                            <div className="text-sm font-semibold text-slate-900 mt-0.5">{job.title}</div>
                          </td>
                          <td className="px-5 py-4 text-slate-500">{job.location}</td>
                          <td className="px-5 py-4">
                            {score !== null ? (
                              <span
                                className={`px-2 py-0.5 rounded text-xs font-bold ${
                                  score >= 75
                                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                    : score >= 60
                                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                    : 'bg-slate-100 text-slate-600 border border-slate-200'
                                }`}
                              >
                                {score}%
                              </span>
                            ) : (
                              <span className="text-slate-400">Unscored</span>
                            )}
                          </td>
                          <td className="px-5 py-4">
                            <select
                              value={job.status || 'discovered'}
                              onChange={(e) => handleStatusChange(job.id, e.target.value)}
                              className="border border-slate-300 rounded px-2.5 py-1 text-xs font-medium bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                            >
                              <option value="discovered">Discovered</option>
                              <option value="matched">Matched</option>
                              <option value="applied">Applied</option>
                              <option value="interview">Interview</option>
                              <option value="offer">Offer</option>
                              <option value="rejected">Declined</option>
                            </select>
                          </td>
                          <td className="px-5 py-4">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleStartApplication(job.id)}
                                disabled={applyingJobId === job.id}
                                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium transition disabled:opacity-50 shadow-xs shadow-indigo-100 active:scale-95"
                              >
                                Review & Apply
                              </button>
                              <a
                                href={getJobFormUrl(job.url)}
                                target="_blank"
                                rel="noreferrer"
                                className="p-1 text-slate-400 hover:text-slate-700"
                                title="View original job link"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                              </a>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 5: PROFILE & WORK AUTH VAULT */}
        {navView === 'profile' && (
          <div className="space-y-6">
            {profile ? (
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs border-t-4 border-t-indigo-600">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 text-white flex items-center justify-center font-bold text-lg shadow-sm shadow-indigo-200">
                      {profile.full_name?.charAt(0)}
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900">{profile.full_name}</h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {profile.email} • {profile.phone} • {profile.location}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploadingResume}
                      className="px-3.5 py-2 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs transition flex items-center gap-2 active:scale-95"
                    >
                      <UploadCloud className="w-4 h-4 text-slate-600" /> Replace Resume
                    </button>
                    <button
                      onClick={handleResetProfile}
                      className="px-3.5 py-2 rounded-lg text-xs font-medium bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 shadow-xs transition flex items-center gap-1.5 active:scale-95"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-600" /> Start Afresh
                    </button>
                  </div>
                </div>

                <p className="text-xs text-slate-700 mt-4 leading-relaxed border-t border-slate-100 pt-3">
                  {profile.summary}
                </p>
              </div>
            ) : (
              <div className="bg-white border border-slate-200 rounded-xl p-8 text-center max-w-xl mx-auto shadow-xs border-t-4 border-t-indigo-600">
                <div className="w-14 h-14 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center mx-auto mb-3">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <h3 className="text-base font-bold text-slate-900">No Candidate Resume Loaded</h3>
                <p className="text-xs text-slate-500 mt-1.5 max-w-sm mx-auto">
                  Upload your resume in PDF or DOCX format to parse your contact info, technical skills, projects, and education.
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingResume}
                  className="mt-5 px-5 py-2.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition active:scale-95 disabled:opacity-50"
                >
                  {uploadingResume ? 'Processing...' : 'Upload Resume (.pdf, .docx)'}
                </button>
              </div>
            )}

            {/* SCREENING & WORK AUTHORIZATION */}
            <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-6 shadow-xs">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                    <Lock className="w-4 h-4 text-indigo-600" />
                    Standard Screening Preferences
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Configure your standard answers for common questions during application form autofill.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleSaveScreening}
                  disabled={savingScreening}
                  className="px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white transition flex items-center gap-2 shadow-xs shadow-indigo-100 active:scale-95"
                >
                  <Check className="w-3.5 h-3.5" />
                  {savingScreening ? 'Saving...' : 'Save Preferences'}
                </button>
              </div>

              {/* Preferences Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Work Authorization */}
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
                  <label className="text-xs font-semibold text-slate-900 block">
                    Legally Authorized to Work?
                  </label>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setScreeningVault(prev => ({ ...prev, authorized_to_work: true }))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition ${
                        screeningVault.authorized_to_work === true
                          ? 'bg-indigo-600 border-indigo-600 text-white font-semibold shadow-xs'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      Yes, Authorized
                    </button>
                    <button
                      type="button"
                      onClick={() => setScreeningVault(prev => ({ ...prev, authorized_to_work: false }))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition ${
                        screeningVault.authorized_to_work === false
                          ? 'bg-indigo-600 border-indigo-600 text-white font-semibold shadow-xs'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      No
                    </button>
                  </div>
                </div>

                {/* Visa Sponsorship */}
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
                  <label className="text-xs font-semibold text-slate-900 block">
                    Requires Visa Sponsorship?
                  </label>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setScreeningVault(prev => ({ ...prev, requires_sponsorship: false }))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition ${
                        screeningVault.requires_sponsorship === false
                          ? 'bg-indigo-600 border-indigo-600 text-white font-semibold shadow-xs'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      No Sponsorship
                    </button>
                    <button
                      type="button"
                      onClick={() => setScreeningVault(prev => ({ ...prev, requires_sponsorship: true }))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition ${
                        screeningVault.requires_sponsorship === true
                          ? 'bg-indigo-600 border-indigo-600 text-white font-semibold shadow-xs'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      Requires Visa
                    </button>
                  </div>
                </div>

                {/* Notice Period */}
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
                  <label className="text-xs font-semibold text-slate-900 block">
                    Notice Period / Availability
                  </label>
                  <select
                    value={screeningVault.notice_period || 'Immediate'}
                    onChange={(e) => setScreeningVault(prev => ({ ...prev, notice_period: e.target.value }))}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  >
                    <option value="Immediate">Immediate</option>
                    <option value="2 Weeks">2 Weeks</option>
                    <option value="30 Days">30 Days</option>
                    <option value="60 Days">60 Days</option>
                    <option value="90 Days">90 Days</option>
                  </select>
                </div>

                {/* Relocation */}
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
                  <label className="text-xs font-semibold text-slate-900 block">
                    Open to Relocation?
                  </label>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setScreeningVault(prev => ({ ...prev, willing_to_relocate: true }))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition ${
                        screeningVault.willing_to_relocate === true
                          ? 'bg-indigo-600 border-indigo-600 text-white font-semibold shadow-xs'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      type="button"
                      onClick={() => setScreeningVault(prev => ({ ...prev, willing_to_relocate: false }))}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition ${
                        screeningVault.willing_to_relocate === false
                          ? 'bg-indigo-600 border-indigo-600 text-white font-semibold shadow-xs'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      No
                    </button>
                  </div>
                </div>

                {/* Work Location Mode */}
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
                  <label className="text-xs font-semibold text-slate-900 block">
                    Location Preference
                  </label>
                  <select
                    value={screeningVault.work_location_preference || 'Flexible'}
                    onChange={(e) => setScreeningVault(prev => ({ ...prev, work_location_preference: e.target.value }))}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  >
                    <option value="Flexible">Flexible (Remote, Hybrid, On-site)</option>
                    <option value="Remote">Remote</option>
                    <option value="Hybrid">Hybrid</option>
                    <option value="On-site">On-site</option>
                  </select>
                </div>

                {/* Pronouns */}
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 space-y-2">
                  <label className="text-xs font-semibold text-slate-900 block">
                    Pronouns (Optional)
                  </label>
                  <input
                    type="text"
                    value={screeningVault.pronouns || ''}
                    placeholder="e.g. She/Her, He/Him, They/Them"
                    onChange={(e) => setScreeningVault(prev => ({ ...prev, pronouns: e.target.value }))}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  />
                </div>
              </div>

              {/* Custom Q&A */}
              <div className="border-t border-slate-100 pt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-slate-900 flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-indigo-600" />
                    Custom Screening Q&A ({screeningVault.custom_qa?.length || 0})
                  </h4>
                  <span className="text-xs text-slate-500">Auto-matches standard form questions</span>
                </div>

                {screeningVault.custom_qa?.length > 0 && (
                  <div className="space-y-2">
                    {screeningVault.custom_qa.map((qa, idx) => (
                      <div key={idx} className="bg-slate-50 p-3 rounded-lg border border-slate-200 flex items-start justify-between gap-3 text-xs">
                        <div className="space-y-0.5 flex-1">
                          <p className="font-semibold text-slate-900">Q: {qa.question}</p>
                          <p className="text-slate-600">A: {qa.answer}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveCustomQA(idx)}
                          className="p-1 text-slate-400 hover:text-rose-600 transition"
                          title="Remove"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 grid grid-cols-1 md:grid-cols-3 gap-2">
                  <input
                    type="text"
                    value={newCustomQ}
                    placeholder="Question (e.g. Years of Python experience?)"
                    onChange={(e) => setNewCustomQ(e.target.value)}
                    className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  />
                  <input
                    type="text"
                    value={newCustomA}
                    placeholder="Answer (e.g. 2+ years academic & full-stack)"
                    onChange={(e) => setNewCustomA(e.target.value)}
                    className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  />
                  <button
                    type="button"
                    onClick={handleAddCustomQA}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white transition flex items-center justify-center gap-1.5 shadow-xs shadow-indigo-100 active:scale-95"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Question
                  </button>
                </div>
              </div>
            </div>

            {/* Technical Projects & Education */}
            {profile && (
              <>
                <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4 shadow-xs">
                  <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                    <Code2 className="w-4 h-4 text-indigo-600" /> Highlighted Projects
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {profile.projects?.map((proj) => (
                      <div key={proj.title} className="bg-slate-50/70 p-4 rounded-xl border border-slate-200/80 space-y-2 hover:border-indigo-200 hover:shadow-xs transition">
                        <h4 className="text-sm font-semibold text-slate-900">{proj.title}</h4>
                        <p className="text-xs text-slate-600 leading-relaxed">{proj.description}</p>
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {proj.technologies?.map((t) => (
                            <span key={t} className="px-2 py-0.5 rounded text-[11px] bg-indigo-50/70 border border-indigo-200/70 text-indigo-700 font-medium">
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4 shadow-xs">
                  <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                    <GraduationCap className="w-4 h-4 text-slate-600" /> Education
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {profile.education?.map((edu, i) => (
                      <div key={i} className="bg-slate-50 p-4 rounded-lg border border-slate-200 space-y-1">
                        <span className="text-[11px] text-slate-500 font-medium">
                          {edu.start_year || '2024'} - {edu.end_year || '2027'}
                        </span>
                        <h4 className="text-xs font-semibold text-slate-900">{edu.institution}</h4>
                        <p className="text-xs text-slate-600">{edu.degree} in {edu.field_of_study}</p>
                        {edu.gpa && <p className="text-xs text-emerald-700 font-medium">GPA: {edu.gpa}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </main>

      {/* MODAL 1: JOB DETAILS */}
      {analysisJob && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-6 space-y-5 shadow-2xl animate-in fade-in duration-150">
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-xs font-medium text-slate-500">{analysisJob.company}</span>
                <h3 className="text-base font-bold text-slate-900">{analysisJob.title}</h3>
              </div>
              <button
                onClick={() => setAnalysisJob(null)}
                className="p-1 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-xs font-medium text-slate-600">Calculated Match Score</span>
              <span className="text-lg font-bold text-emerald-700">
                {getJobMatchScore(analysisJob)}%
              </span>
            </div>

            {analysisJob.llm_reasoning && (
              <div>
                <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">
                  Match Assessment
                </h4>
                <p className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-3.5 rounded-lg border border-slate-200">
                  {analysisJob.llm_reasoning}
                </p>
              </div>
            )}

            <div>
              <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">Description</h4>
              <p className="text-xs text-slate-600 max-h-40 overflow-y-auto leading-relaxed bg-slate-50 p-3.5 rounded-lg border border-slate-200 whitespace-pre-line">
                {analysisJob.description}
              </p>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
              <button
                onClick={() => setAnalysisJob(null)}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs"
              >
                Close
              </button>
              <button
                onClick={() => {
                  const id = analysisJob.id;
                  setAnalysisJob(null);
                  handleStartApplication(id);
                }}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 shadow-xs shadow-indigo-100 transition active:scale-95"
              >
                <Send className="w-3.5 h-3.5" /> Review & Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: MANUAL JOB ENTRY */}
      {showManualModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleManualJobSubmit}
            className="bg-white border border-slate-200 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl animate-in fade-in duration-150"
          >
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Plus className="w-4 h-4 text-indigo-600" /> Add Position
              </h3>
              <button
                type="button"
                onClick={() => setShowManualModal(false)}
                className="p-1 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-medium mb-1">Job Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Software Engineer"
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-medium mb-1">Company *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. GitLab"
                    value={manualCompany}
                    onChange={(e) => setManualCompany(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-medium mb-1">Location</label>
                  <input
                    type="text"
                    placeholder="e.g. Remote / Hybrid"
                    value={manualLocation}
                    onChange={(e) => setManualLocation(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-medium mb-1">Application URL</label>
                <input
                  type="text"
                  placeholder="https://boards.greenhouse.io/... (or leave blank)"
                  value={manualUrl}
                  onChange={(e) => setManualUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-medium mb-1">Job Description *</label>
                <textarea
                  rows={4}
                  required
                  placeholder="Paste requirements, responsibilities, and qualifications..."
                  value={manualDescription}
                  onChange={(e) => setManualDescription(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
                />
              </div>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowManualModal(false)}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingManual}
                className="px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs shadow-indigo-100 disabled:opacity-50 transition active:scale-95"
              >
                {savingManual ? 'Saving...' : 'Add Job'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* MODAL 3: HUMAN REVIEW & APPROVAL GATE */}
      {reviewData && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
                  <h3 className="text-sm font-semibold text-slate-900">
                    Application Review
                  </h3>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Target: <strong className="text-slate-900">{reviewData.job?.company}</strong> — {reviewData.job?.title}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleOpenLiveBrowser(reviewData.job?.id)}
                  disabled={openingBrowser}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs flex items-center gap-1.5 disabled:opacity-50 transition active:scale-95"
                  title="Open live Chromium browser window"
                >
                  <Monitor className="w-3.5 h-3.5 text-slate-600" />
                  {openingBrowser ? 'Launching...' : 'Open Browser'}
                </button>
                <a
                  href={reviewData.application_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-xs flex items-center gap-1.5 transition"
                >
                  Form URL <ExternalLink className="w-3 h-3 text-slate-500" />
                </a>
                <button
                  onClick={() => setReviewData(null)}
                  className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="px-6 border-b border-slate-200 flex items-center gap-4 text-xs font-medium bg-white">
              {[
                { id: 'preview', label: 'Form Preview' },
                { id: 'cover_letter', label: 'Cover Letter' },
                { id: 'resume', label: 'Resume' },
                { id: 'audit', label: 'Fact Verification' }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveReviewTab(tab.id)}
                  className={`py-3 border-b-2 transition ${
                    activeReviewTab === tab.id
                      ? 'border-indigo-600 text-indigo-600 font-semibold'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-4 bg-slate-50/30">
              {activeReviewTab === 'preview' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      <span className="text-slate-700 font-medium">Autofilled Application Preview</span>
                    </div>
                    <button
                      onClick={() => handleOpenLiveBrowser(reviewData.job?.id)}
                      disabled={openingBrowser}
                      className="px-2.5 py-1 rounded text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 flex items-center gap-1.5 transition"
                    >
                      <Monitor className="w-3 h-3" /> Focus Browser Window
                    </button>
                  </div>
                  {reviewData.screenshot_url ? (
                    <div className="rounded-xl overflow-hidden border border-slate-200 bg-white shadow-xs flex flex-col items-center">
                      <img
                        src={reviewData.screenshot_url?.startsWith('http') ? reviewData.screenshot_url : `${API_BASE}${reviewData.screenshot_url}?t=${Date.now()}`}
                        alt="Application Form Preview"
                        className="w-full max-h-[480px] object-top object-contain mx-auto"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none';
                          const fallback = e.currentTarget.parentElement.querySelector('.img-fallback');
                          if (fallback) fallback.style.display = 'block';
                        }}
                      />
                      <div className="img-fallback hidden p-8 text-center text-xs text-slate-500 space-y-2">
                        <p className="text-slate-700 font-medium">Preview captured and ready in Chromium window.</p>
                        <button
                          onClick={() => handleOpenLiveBrowser(reviewData.job?.id)}
                          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium inline-flex items-center gap-1.5 shadow-xs shadow-indigo-100 transition active:scale-95"
                        >
                          <Monitor className="w-3.5 h-3.5" /> Open Browser Window
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-12 text-center text-xs text-slate-500 border border-dashed border-slate-200 rounded-xl space-y-2 bg-white">
                      <p>Preview screenshot not captured yet.</p>
                      <button
                        onClick={() => handleOpenLiveBrowser(reviewData.job?.id)}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium inline-flex items-center gap-1.5 shadow-xs shadow-indigo-100 transition active:scale-95"
                      >
                        <Monitor className="w-3.5 h-3.5" /> Open Browser Window
                      </button>
                    </div>
                  )}
                </div>
              )}

              {activeReviewTab === 'cover_letter' && reviewData.tailored_cover_letter && (
                <div className="bg-white p-6 rounded-xl border border-slate-200 text-xs text-slate-700 leading-relaxed space-y-4 font-sans shadow-xs border-t-4 border-t-indigo-600">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <span className="font-semibold text-slate-900">Tailored Cover Letter</span>
                    <div className="flex items-center gap-2">
                      <a
                        href={`${API_BASE}/exports/${reviewData.job?.id}_cover_letter.pdf`}
                        download
                        className="px-2.5 py-1 rounded text-xs font-medium bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white flex items-center gap-1 shadow-xs shadow-indigo-200 transition active:scale-95"
                      >
                        <Download className="w-3 h-3 text-white" /> Download PDF
                      </a>
                      <a
                        href={`${API_BASE}/exports/${reviewData.job?.id}_cover_letter.docx`}
                        download
                        className="px-2.5 py-1 rounded text-xs font-medium bg-white text-slate-700 border border-slate-200 flex items-center gap-1 shadow-xs hover:bg-slate-50 transition"
                      >
                        <Download className="w-3 h-3 text-slate-500" /> Word (.docx)
                      </a>
                    </div>
                  </div>
                  <p className="font-semibold text-slate-900">{reviewData.tailored_cover_letter.salutation}</p>
                  <p>{reviewData.tailored_cover_letter.opening_paragraph}</p>
                  {reviewData.tailored_cover_letter.body_paragraphs?.map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
                  <p>{reviewData.tailored_cover_letter.closing_paragraph}</p>
                  <p className="pt-2 font-semibold text-slate-900 whitespace-pre-line">
                    {reviewData.tailored_cover_letter.sign_off}
                  </p>
                </div>
              )}

              {activeReviewTab === 'resume' && reviewData.tailored_resume && (
                <div className="bg-white p-6 rounded-xl border border-slate-200 space-y-4 text-xs shadow-xs border-t-4 border-t-indigo-600">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <span className="font-semibold text-slate-900">Tailored Resume</span>
                    <div className="flex items-center gap-2">
                      <a
                        href={`${API_BASE}/exports/${reviewData.job?.id}_resume.pdf`}
                        download
                        className="px-2.5 py-1 rounded text-xs font-medium bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white flex items-center gap-1 shadow-xs shadow-indigo-200 transition active:scale-95"
                      >
                        <Download className="w-3 h-3 text-white" /> Download PDF
                      </a>
                      <a
                        href={`${API_BASE}/exports/${reviewData.job?.id}_resume.docx`}
                        download
                        className="px-2.5 py-1 rounded text-xs font-medium bg-white text-slate-700 border border-slate-200 flex items-center gap-1 shadow-xs hover:bg-slate-50 transition"
                      >
                        <Download className="w-3 h-3 text-slate-500" /> Word (.docx)
                      </a>
                    </div>
                  </div>
                  <div>
                    <h5 className="font-semibold text-slate-900 uppercase tracking-wider">Professional Summary</h5>
                    <p className="text-slate-700 mt-1 leading-relaxed bg-slate-50/70 p-3 rounded-lg border border-slate-200/80">
                      {reviewData.tailored_resume.professional_summary}
                    </p>
                  </div>

                  <div>
                    <h5 className="font-semibold text-slate-900 uppercase tracking-wider">Highlighted Skills</h5>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {reviewData.tailored_resume.highlighted_skills?.map((s) => (
                        <span key={s} className="px-2 py-0.5 rounded text-[11px] bg-indigo-50/70 text-indigo-700 border border-indigo-200/80 font-medium">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h5 className="font-semibold text-slate-900 uppercase tracking-wider">Featured Projects</h5>
                    <div className="space-y-3 mt-2">
                      {reviewData.tailored_resume.projects?.map((p) => (
                        <div key={p.title} className="p-3 rounded-lg bg-slate-50/70 border border-slate-200/80 space-y-1">
                          <h6 className="font-semibold text-slate-900">{p.title}</h6>
                          <ul className="list-disc list-inside space-y-1 text-slate-600 mt-1">
                            {p.bullets?.map((b, i) => (
                              <li key={i}>{b.text}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeReviewTab === 'audit' && reviewData.audit_report && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between font-medium">
                    <span>
                      Fact Check Verdict: <strong className="font-bold">{reviewData.audit_report.passed_audit ? '100% Verified' : 'Needs Review'}</strong>
                    </span>
                    <span className="bg-emerald-100/70 px-2.5 py-0.5 rounded-full text-emerald-900">
                      {reviewData.audit_report.verified_claims} / {reviewData.audit_report.total_claims} Claims Grounded
                    </span>
                  </div>

                  <div className="space-y-2">
                    {reviewData.audit_report.claims?.map((c, i) => (
                      <div key={i} className="p-3 rounded-lg bg-white border border-slate-200 text-xs space-y-1 shadow-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-slate-800">"{c.claim_text}"</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            Verified
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500">{c.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-200 bg-white flex flex-col sm:flex-row items-center justify-between gap-3">
              <input
                type="text"
                placeholder="Optional notes or feedback..."
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                className="w-full sm:w-80 px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-xs transition"
              />

              <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                <button
                  onClick={() => handleDecision(false)}
                  disabled={deciding}
                  className="px-4 py-2 rounded-lg text-xs font-medium bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 transition disabled:opacity-50 flex items-center gap-1.5 shadow-xs active:scale-95"
                >
                  <X className="w-3.5 h-3.5" /> Decline
                </button>
                <button
                  onClick={() => handleDecision(true)}
                  disabled={deciding}
                  className="px-5 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition disabled:opacity-50 flex items-center gap-1.5 shadow-sm shadow-emerald-200 active:scale-95"
                >
                  <Check className="w-3.5 h-3.5" />
                  {deciding ? 'Submitting...' : 'Approve & Submit Application'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
