import { useState, useEffect } from 'react';
import ApiService from './services/ApiService';

const App = () => {
  const [token, setToken] = useState(localStorage.getItem('wajo_token') || '');
  const [authState, setAuthState] = useState(token ? 'authenticated' : 'idle');
  const [phone, setPhone] = useState('+919570678427');
  const [otp, setOtp] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState('36');
  const [clipReelId, setClipReelId] = useState('');
  const [bulkNotes, setBulkNotes] = useState([
    { content: '', visibility: 'public', private_to: '' },
  ]);
  const [noteId, setNoteId] = useState('');
  const [replyContent, setReplyContent] = useState('');

  // Rich UI states
  const [highlights, setHighlights] = useState([]);
  const [shareGroups, setShareGroups] = useState([]);
  const [comments, setComments] = useState([]);
  const [notes, setNotes] = useState([]);
  const [noteReplies, setNoteReplies] = useState([]);
  const [sessionUsers, setSessionUsers] = useState([]);
  const [activeTeam, setActiveTeam] = useState('All');
  const [showRawJson, setShowRawJson] = useState(false);
  const [userProfile, setUserProfile] = useState(null);

  const addNoteRow = () =>
    setBulkNotes(prev => [...prev, { content: '', visibility: 'public', private_to: '' }]);

  const removeNoteRow = (idx) =>
    setBulkNotes(prev => prev.filter((_, i) => i !== idx));

  const updateNoteRow = (idx, field, value) =>
    setBulkNotes(prev => prev.map((n, i) => i === idx ? { ...n, [field]: value } : n));

  const submitBulkNotes = () => {
    const payload = bulkNotes.map(n => {
      const note = { content: n.content, visibility: n.visibility };
      if (n.visibility === 'private' && n.private_to.trim()) {
        note.private_to = n.private_to.split(',').map(s => s.trim()).filter(Boolean);
      }
      return note;
    });
    callApi(() => ApiService.addBulkNotes(clipReelId, payload));
  };

  const handleSetToken = (t) => {
    setToken(t);
    ApiService.setToken(t);
  };

  const handleSendOtp = async () => {
    setLoading(true);
    const result = await ApiService.sendOtp(phone);
    setResponse(result);
    if (result.ok) {
      setAuthState('otp_sent');
    }
    setLoading(false);
  };

  const handleLogin = async () => {
    setLoading(true);
    const data = {
      phone_no: phone,
      otp: otp,
      selected_language: "he",
      fcm_token: "dWkyOQFARBKUw7tKGoR2Q3:APA91bH7YUEgscPEfLFFkt87OS3drNcarQ_43iguhV-57xXA4gZcJ_BN70I8QwWLtOdSQkiq8J7LSzZKXJM5GudDq_DuTtnNea9Gzwo8t8MvySZn-Ahls1n"
    };
    const result = await ApiService.login(data);
    setResponse(result);
    if (result.ok && result.data.token) {
      handleSetToken(result.data.token);
      setAuthState('authenticated');
      fetchUserProfile();
    }
    setLoading(false);
  };

  const fetchUserProfile = async () => {
    try {
      const result = await ApiService.getUserProfile();
      if (result.ok) {
        setUserProfile(result.data);
      }
    } catch (err) {
      console.error('Failed to fetch profile:', err);
    }
  };

  useEffect(() => {
    if (token && authState === 'authenticated') {
      fetchUserProfile();
    }
  }, [token, authState]);

  // Generic API call (keeps raw JSON response only)
  const callApi = async (method) => {
    setLoading(true);
    setResponse(null);
    try {
      const result = await method();
      setResponse(result);
    } catch (err) {
      setResponse({ error: 'Exception occurred', details: err.message });
    } finally {
      setLoading(false);
    }
  };

  // Fetch highlights → rich UI
  const fetchHighlights = async (apiCall) => {
    setLoading(true); setResponse(null); setHighlights([]);
    try {
      const result = await apiCall();
      setResponse(result);
      if (result.ok && result.data?.highlights) setHighlights(result.data.highlights);
      else if (result.ok && result.data?.results) setHighlights(result.data.results);
    } catch (err) { setResponse({ error: 'Exception', details: err.message }); }
    finally { setLoading(false); }
  };

  // Fetch shares → rich UI
  const fetchShares = async (apiCall) => {
    setLoading(true); setResponse(null); setShareGroups([]);
    try {
      const result = await apiCall();
      setResponse(result);
      if (result.ok) {
        // shared-with-me returns array of groups [{shared_by, clip_reels}]
        if (Array.isArray(result.data)) setShareGroups(result.data);
        // shared-by-me returns {shares: [...]}
        else if (result.data?.shares) setShareGroups([{ shared_by: null, clip_reels: result.data.shares }]);
      }
    } catch (err) { setResponse({ error: 'Exception', details: err.message }); }
    finally { setLoading(false); }
  };

  // Fetch comments → rich UI
  const fetchComments = async (clipId) => {
    setLoading(true); setResponse(null); setComments([]);
    try {
      const result = await ApiService.getComments(clipId);
      setResponse(result);
      if (result.ok) {
        const data = result.data;
        if (Array.isArray(data)) setComments(data);
        else if (data?.results) setComments(data.results);
        else if (data?.comments) setComments(data.comments);
      }
    } catch (err) { setResponse({ error: 'Exception', details: err.message }); }
    finally { setLoading(false); }
  };

  // Fetch notes → rich UI
  const fetchNotes = async (clipId) => {
    setLoading(true); setResponse(null); setNotes([]);
    try {
      const result = await ApiService.getNotes(clipId);
      setResponse(result);
      if (result.ok) {
        const data = result.data;
        if (Array.isArray(data)) setNotes(data);
        else if (data?.results) setNotes(data.results);
        else if (data?.notes) setNotes(data.notes);
      }
    } catch (err) { setResponse({ error: 'Exception', details: err.message }); }
    finally { setLoading(false); }
  };

  // Fetch replies → rich UI
  const fetchReplies = async (nId) => {
    setLoading(true); setResponse(null); setNoteReplies([]);
    try {
      const result = await ApiService.getNoteReplies(nId);
      setResponse(result);
      if (result.ok) {
        const data = result.data;
        if (data?.replies) setNoteReplies(data.replies);
        else if (Array.isArray(data)) setNoteReplies(data);
      }
    } catch (err) { setResponse({ error: 'Exception', details: err.message }); }
    finally { setLoading(false); }
  };

  // Fetch session users → rich UI
  const fetchSessionUsers = async (sId) => {
    setLoading(true); setResponse(null); setSessionUsers([]);
    try {
      console.log(`Starting fetch for session ${sId}...`);
      const result = await ApiService.getSessionUsers(sId);
      console.log('User Fetch Result:', result);
      setResponse(result);
      if (result.ok) {
        // Handle both {users: [...]} and direct list [...]
        const list = result.data?.users || (Array.isArray(result.data) ? result.data : []);
        console.log(`Found ${list.length} users`);
        setSessionUsers(list);
      } else {
        console.error('Fetch failed:', result.status, result.data);
      }
    } catch (err) {
      console.error('Fetch exception:', err);
      setResponse({ error: 'Exception', details: err.message });
    }
    finally { setLoading(false); }
  };

  const getGroupedUsers = () => {
    const groups = { 'No Team': [] };
    if (!Array.isArray(sessionUsers)) return groups;

    sessionUsers.forEach(u => {
      if (!u) return;
      // In the API, u.team is an array of objects like {id, name}
      const teams = Array.isArray(u.team) ? u.team : [];
      if (teams.length === 0) {
        groups['No Team'].push(u);
      } else {
        teams.forEach(t => {
          const tName = t.name || 'Unnamed Team';
          if (!groups[tName]) groups[tName] = [];
          groups[tName].push(u);
        });
      }
    });
    return groups;
  };

  // Helpers
  const getEventEmoji = (type) => {
    const map = { goal: '⚽', shot: '🎯', yellow_card: '🟡', red_card: '🔴', foul: '⚠️', corner: '🔄', possession: '🎮' };
    return map[type] || '📌';
  };
  const getStatusColor = (s) => s === 'completed' ? 'badge-success' : (s === 'processing' || s === 'pending') ? 'badge-warning' : 'badge-error';
  const timeAgo = (dt) => {
    if (!dt) return '';
    const d = new Date(dt);
    const diff = (Date.now() - d) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return d.toLocaleDateString();
  };

  const renderResponse = () => {
    try {
      if (!response) return <div className="text-muted italic">Execute a request to see results...</div>;

      const data = response.data;

      // Auto-detect structured data if not explicitly showing raw JSON
      if (!showRawJson) {
        // User Profile
        if (data?.id && data?.phone_no && (data?.role || data?.email)) {
          return (
            <div className="animate-fade-in mt-4">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold">User Profile</h3>
                <RawJsonToggle hasData={true} />
              </div>
              {renderUserCard(data)}
            </div>
          );
        }

        // Highlights
        if (data?.highlights || (data?.results && (data?.results[0]?.event_type || data?.results[0]?.label))) {
          const hList = data.highlights || data.results;
          if (Array.isArray(hList)) {
            return (
              <div className="animate-fade-in mt-4">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-bold">Highlights List</h3>
                  <RawJsonToggle hasData={true} />
                </div>
                <div className="flex flex-col gap-4">
                  {hList.map((h, i) => h && renderHighlightBrief(h, i))}
                </div>
              </div>
            );
          }
        }

        // Session Users
        const sUsers = data?.users || (Array.isArray(data) && (data[0]?.user_id || data[0]?.user_name) ? data : null);
        if (sUsers && Array.isArray(sUsers)) {
          return (
            <div className="animate-fade-in mt-4">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold">Session Users ({sUsers.length})</h3>
                <RawJsonToggle hasData={true} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sUsers.map((u, i) => u && renderSessionUserCard(u, i))}
              </div>
            </div>
          );
        }

        // Shares
        if (data?.shares || (Array.isArray(data) && data[0]?.shared_by)) {
          const groups = Array.isArray(data) ? data : [{ shared_by: null, clip_reels: data.shares }];
          if (Array.isArray(groups)) {
            return (
              <div className="animate-fade-in mt-4">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-xl font-bold">Shared Data</h3>
                  <RawJsonToggle hasData={true} />
                </div>
                <div className="flex flex-col gap-6">
                  {groups.map((group, gi) => group && (
                    <div key={gi} className="space-y-4">
                      {group.shared_by && (
                        <div className="flex items-center gap-3 p-2 bg-white/5 rounded-lg">
                          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold">
                            {String(group.shared_by.name || 'U')[0].toUpperCase()}
                          </div>
                          <div>
                            <p className="font-bold">{group.shared_by.name || group.shared_by.phone_no}</p>
                            <p className="text-xs text-muted">{group.shared_by.role || 'User'}</p>
                          </div>
                        </div>
                      )}
                      <div className="flex flex-col gap-4">
                        {Array.isArray(group.clip_reels) && group.clip_reels.map((cr, ci) => cr && renderSharedClipBrief(cr, ci))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          }
        }
      }

      return (
        <div className="animate-fade-in mt-4">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-4">
              <h3 className="text-xl font-bold">Response</h3>
              {!showRawJson && response.ok && <span className="text-xs text-warning animate-pulse">Unknown data structure - showing JSON</span>}
              {!response.ok && <span className="badge badge-error">API Error: {response.status}</span>}
            </div>
            <div className="flex items-center gap-3">
              <RawJsonToggle hasData={true} />
              <span className={`badge ${response.ok ? 'badge-success' : 'badge-error'}`}>
                Status: {response.status}
              </span>
            </div>
          </div>
          <pre className="glass p-4 rounded-lg overflow-x-auto max-h-[500px] text-sm font-mono leading-relaxed" style={{ background: 'rgba(0,0,0,0.4)', borderColor: response.ok ? 'rgba(255,255,255,0.1)' : 'rgba(239,68,68,0.2)' }}>
            {JSON.stringify(response.data, null, 2)}
          </pre>
          {!response.ok && response.status === 401 && (
            <div className="mt-4 p-4 glass border-error bg-error/10 text-center animate-pulse">
              <p className="text-error font-bold mb-2">AUTH EXPIRED - Your local token is invalid for staging.</p>
              <button className="btn btn-primary" onClick={() => { localStorage.removeItem('wajo_token'); window.location.reload(); }}>
                🔄 Clear Session & Logout
              </button>
            </div>
          )}
        </div>
      );
    } catch (err) {
      console.error('Render crash:', err);
      return (
        <div style={{ padding: '40px', background: 'rgba(239, 68, 68, 0.1)', border: '2px solid #ef4444', borderRadius: '16px' }}>
          <p style={{ color: '#ef4444', fontWeight: 800, fontSize: '1.2rem', margin: 0 }}>🚨 Render Error</p>
          <p style={{ fontFamily: 'monospace', fontSize: '13px', margin: '14px 0', opacity: 0.8 }}>{err.message}</p>
          <pre style={{ fontSize: '10px', opacity: 0.4, overflow: 'auto', maxHeight: '100px' }}>{err.stack}</pre>
          <button className="btn btn-outline border-error mt-4" onClick={() => window.location.reload()}>Reload Dashboard</button>
        </div>
      );
    }
  };

  /* ─── Reusable Renderers ─── */

  const renderHighlightBrief = (h, i) => {
    if (!h) return null;
    return (
      <div key={i} className="glass p-4 rounded-xl flex items-center justify-between hover:bg-white/5 transition-all" style={{ borderLeft: `3px solid ${h.side === 'home' ? '#6366f1' : '#f59e0b'}` }}>
        <div className="flex items-center gap-4">
          <div className="text-2xl w-12 h-12 rounded-lg bg-white/5 flex items-center justify-center">
            {getEventEmoji(h.event_type)}
          </div>
          <div>
            <p className="font-bold">{h.label || h.event_name || `Highlight #${h.id}`}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-muted">ID: {h.id}</span>
              {h.side && <span className="badge" style={{ fontSize: '0.65rem', background: h.side === 'home' ? 'rgba(99,102,241,0.1)' : 'rgba(245,158,11,0.1)' }}>{h.side}</span>}
              {h.match_time && <span className="text-[10px] opacity-60">⏱ {h.match_time}</span>}
            </div>
          </div>
        </div>
        {h.trace_player && (
          <div className="text-right">
            <p className="text-xs font-bold">{h.trace_player.name}</p>
            <p className="text-[10px] text-muted">#{h.trace_player.jersey_number}</p>
          </div>
        )}
      </div>
    );
  };

  const renderSessionUserCard = (u, i) => {
    if (!u) return null;
    // Handling both nested and flat structures
    const user = u.user || u;
    const name = u.user_name || user.name || user.phone_no || 'User';
    const role = u.user_role || user.role || 'Member';
    const isReg = u.is_registered !== undefined ? u.is_registered : user.is_registered;
    const initial = String(name || '?')[0].toUpperCase();

    return (
      <div key={i} className="glass p-4 rounded-xl flex items-center gap-4 hover:bg-white/5 transition-all">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center font-bold text-lg flex-shrink-0">
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <p className="font-bold truncate">{name}</p>
            <span className={`badge ${isReg ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '0.65rem' }}>
              {isReg ? 'Registered' : 'Pending'}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-indigo-400 font-bold">{role}</span>
            <span className="text-[10px] text-muted truncate opacity-60">{u.mobile_number || user.phone_no}</span>
          </div>
          {/* Handling team name display */}
          {Array.isArray(u.team) && u.team.length > 0 && (
            <p className="text-[10px] text-muted italic mt-1">
              Teams: {u.team.map(t => t.name).join(', ')}
            </p>
          )}
        </div>
      </div>
    );
  };

  const renderUserCard = (u) => (
    <div className="glass p-8 rounded-2xl relative overflow-hidden" style={{ borderLeft: '4px solid #6366f1' }}>
      <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
        <span className="text-8xl">👤</span>
      </div>
      <div className="flex flex-col md:flex-row gap-8 items-start md:items-center">
        <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-indigo-600 to-purple-500 p-1 flex-shrink-0">
          <div className="w-full h-full rounded-full bg-slate-900 flex items-center justify-center text-3xl font-black">
            {u.name?.[0]?.toUpperCase() || u.phone_no?.[1] || 'W'}
          </div>
        </div>
        <div className="flex-1 space-y-4">
          <div>
            <h2 className="text-3xl font-black mb-1">{u.name || 'Anonymous User'}</h2>
            <div className="flex items-center gap-3">
              <span className="badge badge-primary">{u.role || 'Member'}</span>
              <span className="text-muted font-mono">{u.phone_no}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-3 gap-6 pt-4">
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-widest text-muted font-bold">User ID</p>
              <p className="font-mono text-xs opacity-60 truncate">{u.id}</p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-widest text-muted font-bold">Language</p>
              <p className="text-sm font-bold uppercase">{u.selected_language || 'en'}</p>
            </div>
            {u.team_id && (
              <div className="space-y-1">
                <p className="text-[10px] uppercase tracking-widest text-muted font-bold">Team ID</p>
                <p className="text-sm font-bold">{u.team_id}</p>
              </div>
            )}
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-widest text-muted font-bold">Registration</p>
              <p className="text-sm font-bold">{u.is_registered ? '✅ Verified' : '⏳ Pending'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderSharedClipBrief = (cr, ci) => {
    const clipId = cr.clip_id || cr.clip_reel || cr.id;
    const evType = cr.event_type || cr.highlight?.event_type;
    return (
      <div key={ci} className="glass p-4 rounded-xl flex items-center justify-between hover:bg-white/5 transition-all">
        <div className="flex items-center gap-4">
          <div className="text-2xl w-12 h-12 rounded-lg bg-white/5 flex items-center justify-center">
            {getEventEmoji(evType)}
          </div>
          <div>
            <p className="font-bold">{cr.label || cr.event_name || `Clip #${clipId}`}</p>
            <p className="text-xs text-muted">Clip ID: {clipId} • {timeAgo(cr.shared_at)}</p>
          </div>
        </div>
        {cr.primary_player && (
          <div className="text-right">
            <p className="text-sm font-bold">{cr.primary_player.name}</p>
            <p className="text-xs text-muted">Player ID: {cr.primary_player.id}</p>
          </div>
        )}
      </div>
    );
  };

  const renderCommentCard = (c) => (
    <div key={c.id} className="glass" style={{ padding: '14px 18px', borderRadius: '10px', borderLeft: `3px solid ${c.visibility === 'private' ? '#f59e0b' : '#6366f1'}` }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '6px' }}>
        <div className="flex items-center gap-2">
          <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{c.author?.name || c.author?.phone_no || 'Unknown'}</span>
          <span className="badge" style={{ background: c.visibility === 'private' ? 'rgba(245,158,11,0.15)' : 'rgba(99,102,241,0.15)', color: c.visibility === 'private' ? '#fbbf24' : '#818cf8', fontSize: '0.7rem' }}>
            {c.visibility === 'private' ? '🔒 Private' : '🌐 Public'}
          </span>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{timeAgo(c.created_at)}</span>
      </div>
      <p style={{ margin: '8px 0', lineHeight: 1.5 }}>{c.content}</p>
      <div className="flex items-center gap-3" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        <span>❤️ {c.likes_count || 0}</span>
        <span>💬 {c.replies_count || 0}</span>
        {c.is_liked && <span style={{ color: '#ef4444' }}>Liked</span>}
      </div>
    </div>
  );

  const renderNoteCard = (n) => (
    <div key={n.id || n.note_id} className="glass" style={{ padding: '14px 18px', borderRadius: '10px', borderLeft: `3px solid ${(n.visibility === 'private' || n.is_private) ? '#f59e0b' : '#10b981'}` }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '6px' }}>
        <div className="flex items-center gap-2">
          <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>
            {n.author?.name || n.author?.phone_no || `Note #${n.id || n.note_id}`}
          </span>
          <span className="badge" style={{ background: (n.visibility === 'private' || n.is_private) ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)', color: (n.visibility === 'private' || n.is_private) ? '#fbbf24' : '#34d399', fontSize: '0.7rem' }}>
            {(n.visibility === 'private' || n.is_private) ? '🔒 Private' : '🌐 Public'}
          </span>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{timeAgo(n.created_at)}</span>
      </div>
      <p style={{ margin: '8px 0', lineHeight: 1.5 }}>{n.content || n.note}</p>
      {/* Inline replies */}
      {n.reply && n.reply.length > 0 && (
        <div style={{ marginTop: '10px', paddingLeft: '14px', borderLeft: '2px solid rgba(255,255,255,0.08)' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '6px' }}>Replies ({n.reply.length})</p>
          {n.reply.map((r, i) => (
            <div key={r.reply_id || i} style={{ padding: '6px 0', fontSize: '0.85rem' }}>
              <span style={{ fontWeight: 600 }}>{r.user_replied?.name || 'Anonymous'}: </span>
              <span>{r.reply_text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderReplyCard = (r, i) => (
    <div key={r.reply_id || i} className="glass" style={{ padding: '14px 18px', borderRadius: '10px', borderLeft: '3px solid #818cf8' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '6px' }}>
        <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>
          {r.user_replied?.name || r.author?.name || 'Anonymous'}
        </span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Reply #{r.reply_id || r.id}</span>
      </div>
      <p style={{ margin: '8px 0', lineHeight: 1.5 }}>{r.reply_text || r.content}</p>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        Parent Note #{r.parent_id || r.note?.id || '?'}
      </div>
    </div>
  );

  const renderVideoPlayer = (v) => (
    <div key={v.id} className="video-card" style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '10px', overflow: 'hidden' }}>
      {v.url && v.status === 'completed' ? (
        <video controls preload="metadata"
          style={{ width: '100%', maxHeight: '400px', background: '#000', display: 'block' }}
          onPlay={(e) => { document.querySelectorAll('video').forEach(el => { if (el !== e.target) el.pause(); }); }}>
          <source src={v.url} type="video/mp4" />
        </video>
      ) : (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '2rem', display: 'block', marginBottom: '8px' }}>
            {v.status === 'processing' ? '⏳' : v.status === 'pending' ? '🔄' : '🚫'}
          </span>
          <p style={{ fontWeight: 600 }}>{v.status === 'completed' ? 'No URL available' : `Status: ${v.status || 'unknown'}`}</p>
        </div>
      )}
      <div className="flex items-center justify-between" style={{ padding: '10px 14px', fontSize: '0.8rem' }}>
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--text-muted)' }}>Clip #{v.id}</span>
          <span className={`badge ${getStatusColor(v.status)}`}>{v.status}</span>
          {v.ratio && <span style={{ color: 'var(--text-muted)' }}>{v.ratio}</span>}
        </div>
        {v.primary_player && (
          <span style={{ color: 'var(--text-muted)' }}>
            {v.primary_player.name} {v.primary_player.jersey_number != null ? `#${v.primary_player.jersey_number}` : ''}
          </span>
        )}
      </div>
    </div>
  );

  /* ─── Raw JSON toggle button ─── */
  const RawJsonToggle = ({ hasData }) =>
    hasData ? (
      <button className={`btn ${showRawJson ? 'btn-primary' : 'btn-outline'}`}
        style={{ padding: '6px 14px', fontSize: '0.8rem' }}
        onClick={() => setShowRawJson(!showRawJson)}>
        {showRawJson ? '🎨 Rich View' : '{ } Raw JSON'}
      </button>
    ) : null;

  // Auth screen
  if (authState !== 'authenticated') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="auth-container glass p-8 animate-fade-in">
          <h1 className="text-3xl font-bold mb-2">WAJO API</h1>
          <p className="text-muted mb-6 font-bold tracking-wide text-sm">Authentication Required</p>

          {authState === 'idle' && (
            <div className="space-y-4">
              <div className="input-group"><label>Phone Number</label>
                <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="+91..." />
              </div>
              <button onClick={handleSendOtp} disabled={loading} className="btn btn-primary w-full">
                {loading ? 'Sending...' : 'Send OTP'}
              </button>
            </div>
          )}

          {authState === 'otp_sent' && (
            <div className="space-y-4">
              <div className="input-group"><label>OTP Code</label>
                <input value={otp} onChange={e => setOtp(e.target.value)} placeholder="Enter OTP" />
              </div>
              <button onClick={handleLogin} disabled={loading} className="btn btn-primary w-full">
                {loading ? 'Verifying...' : 'Login & Explore'}
              </button>
              <button onClick={() => setAuthState('idle')} className="btn btn-outline w-full">Change Phone Number</button>
            </div>
          )}

          {response && !response.ok && (
            <div className="p-4 bg-error/10 border border-error/20 rounded-lg text-error text-sm">
              {response.data?.error || response.data?.message || 'Authentication failed'}
            </div>
          )}
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'shares', label: 'Shares', icon: '🔗' },
    { id: 'highlights', label: 'Highlights', icon: '⚽' },
    { id: 'interactions', label: 'Interactions', icon: '💬' },
    { id: 'users', label: 'Users', icon: '👥' },
  ];

  return (
    <div className="flex flex-col md:flex-row min-h-screen w-full">
      {/* Sidebar */}
      <aside className="w-full md:w-64 glass m-4 flex flex-col p-6 gap-8">
        <div>
          <h1 className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-500 mb-2">
            WAJO API
          </h1>
          <p className="text-xs text-muted font-bold tracking-widest uppercase">Test Explorer</p>
        </div>

        <nav className="flex flex-col gap-2">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); setShowRawJson(false); }}
              className={`btn flex items-center justify-start gap-4 p-4 text-left ${activeTab === tab.id ? 'btn-primary' : 'btn-outline border-transparent'}`}
              style={{ justifyContent: 'flex-start' }}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-4">
          <div className="p-4 glass rounded-lg text-xs">
            <p className="text-muted mb-1">Authenticated as</p>
            <p className="font-mono opacity-60 truncate">{phone}</p>
          </div>
          <button
            className="btn btn-outline w-full"
            onClick={() => {
              localStorage.removeItem('wajo_token');
              setToken('');
              setAuthState('idle');
            }}
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 flex flex-col gap-4 overflow-y-auto">
        <section className="glass p-8 min-h-[400px]">

          {activeTab === 'dashboard' && (
            <div className="animate-fade-in space-y-8">
              <div>
                <h2 className="text-4xl font-black mb-2 bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                  Welcome Back, Agent
                </h2>
                <p className="text-text-muted max-w-2xl leading-relaxed">
                  You are currently authenticated to the Wajo Vision internal diagnostics system.
                  Use the tools below to monitor real-time data flow and API health.
                </p>
              </div>

              {/* User Profile Section */}
              {userProfile ? (
                <div className="space-y-4">
                  <h3 className="text-xs font-black uppercase tracking-[0.2em] text-indigo-500">Active Profile</h3>
                  {renderUserCard(userProfile)}
                </div>
              ) : (
                <div className="glass p-8 rounded-2xl animate-pulse flex items-center justify-center">
                  <p className="text-muted">Loading profile data...</p>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="card glass p-6 border-l-4 border-slate-700 bg-white/[0.02]">
                  <h4 className="text-[10px] uppercase font-black tracking-widest text-muted mb-4">Security Credentials</h4>
                  <div className="space-y-2">
                    <p className="text-xs font-bold">API Session Token</p>
                    <p className="text-[10px] break-all font-mono opacity-50 bg-black/20 p-3 rounded">{token}</p>
                  </div>
                </div>
                <div className="card glass p-6 border-l-4 border-indigo-500 bg-white/[0.02]">
                  <h4 className="text-[10px] uppercase font-black tracking-widest text-muted mb-4">Focus Context</h4>
                  <div className="space-y-4">
                    <div className="input-group">
                      <label style={{ fontSize: '10px' }}>Trace Session ID</label>
                      <input type="number" value={sessionId} onChange={e => setSessionId(e.target.value)}
                        className="bg-black/20 border-white/5 w-full mt-1"
                        style={{ height: '40px', fontSize: '1.2rem', fontWeight: 'bold' }} />
                    </div>
                    <p className="text-[10px] text-muted italic">All tab-specific data fetches will prioritize this session ID.</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═══ SHARES TAB ═══ */}
          {activeTab === 'shares' && (
            <div className="animate-fade-in">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">Clip Reel Shares</h2>
                <RawJsonToggle hasData={shareGroups.length > 0} />
              </div>

              <div className="flex flex-wrap gap-3 mb-8">
                <button className="btn btn-primary" onClick={() => fetchShares(() => ApiService.getSharedWithMe())}>
                  🔗 List Shared With Me (All)
                </button>
                <button className="btn btn-outline" onClick={() => fetchShares(() => ApiService.getSharedWithMeBySession(sessionId))}>
                  Shared With Me (Session {sessionId})
                </button>
                <button className="btn btn-outline" onClick={() => fetchShares(() => ApiService.getSharedByMe())}>
                  Shared By Me
                </button>
              </div>

              {/* Raw JSON */}
              {showRawJson && response && (
                <div className="animate-fade-in"><pre>{JSON.stringify(response.data, null, 2)}</pre></div>
              )}

              {/* Rich share cards */}
              {!showRawJson && shareGroups.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  {shareGroups.map((group, gi) => (
                    <div key={gi}>
                      {/* Sharer header */}
                      {group.shared_by && (
                        <div className="flex items-center gap-3" style={{ marginBottom: '14px' }}>
                          <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'linear-gradient(135deg, #6366f1, #a855f7)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '1rem' }}>
                            {(group.shared_by.name || group.shared_by.phone_no || '?')[0].toUpperCase()}
                          </div>
                          <div>
                            <p style={{ fontWeight: 700 }}>{group.shared_by.name || group.shared_by.phone_no}</p>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{group.shared_by.role || 'User'}</p>
                          </div>
                        </div>
                      )}

                      {/* Clip reels from this sharer */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {(group.clip_reels || []).map((cr, ci) => {
                          const clipId = cr.clip_id || cr.clip_reel || cr.id;
                          const videoUrl = cr.url || cr.clip_reel?.video_url;
                          const evType = cr.event_type || cr.highlight?.event_type;
                          const label = cr.label || cr.event_name || `Clip #${clipId}`;

                          return (
                            <div key={ci} className="highlight-card glass" style={{ padding: '18px', borderRadius: '14px', borderLeft: '4px solid #6366f1' }}>
                              {/* Clip header */}
                              <div className="flex items-center justify-between" style={{ marginBottom: '12px' }}>
                                <div className="flex items-center gap-3">
                                  <span style={{ fontSize: '1.3rem' }}>{getEventEmoji(evType)}</span>
                                  <div>
                                    <h4 style={{ fontWeight: 700, margin: 0 }}>{label}</h4>
                                    <div className="flex items-center gap-2" style={{ marginTop: '4px' }}>
                                      <span className="badge" style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: '0.7rem' }}>
                                        Clip #{clipId}
                                      </span>
                                      {cr.can_comment !== undefined && (
                                        <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                                          {cr.can_comment ? '💬 Can Comment' : '🚫 No Comment'}
                                        </span>
                                      )}
                                      {cr.shared_at && (
                                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                          {timeAgo(cr.shared_at)}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                                {cr.primary_player && (
                                  <div style={{ textAlign: 'right' }}>
                                    <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{cr.primary_player.name}</span>
                                    {cr.primary_player.jersey_number != null && (
                                      <span style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                        #{cr.primary_player.jersey_number}
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>

                              {/* Video player */}
                              {videoUrl ? (
                                <div className="video-card" style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '10px', overflow: 'hidden', marginBottom: '12px' }}>
                                  <video controls preload="metadata"
                                    style={{ width: '100%', maxHeight: '360px', background: '#000', display: 'block' }}
                                    onPlay={(e) => { document.querySelectorAll('video').forEach(el => { if (el !== e.target) el.pause(); }); }}>
                                    <source src={videoUrl} type="video/mp4" />
                                  </video>
                                </div>
                              ) : null}

                              {/* Comments */}
                              {cr.comments && cr.comments.length > 0 && (
                                <div style={{ marginTop: '12px' }}>
                                  <p style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px', color: '#818cf8' }}>
                                    💬 Comments ({cr.comments.length})
                                  </p>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {cr.comments.map(c => renderCommentCard(c))}
                                  </div>
                                </div>
                              )}

                              {/* Public Notes */}
                              {cr.public_notes && cr.public_notes.length > 0 && (
                                <div style={{ marginTop: '12px' }}>
                                  <p style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px', color: '#34d399' }}>
                                    📝 Public Notes ({cr.public_notes.length})
                                  </p>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {cr.public_notes.map(n => renderNoteCard(n))}
                                  </div>
                                </div>
                              )}

                              {/* Private Notes */}
                              {cr.private_notes && cr.private_notes.length > 0 && (
                                <div style={{ marginTop: '12px' }}>
                                  <p style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px', color: '#fbbf24' }}>
                                    🔒 Private Notes ({cr.private_notes.length})
                                  </p>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {cr.private_notes.map(n => renderNoteCard(n))}
                                  </div>
                                </div>
                              )}

                              {/* No content */}
                              {(!cr.comments || cr.comments.length === 0) &&
                                (!cr.public_notes || cr.public_notes.length === 0) &&
                                (!cr.private_notes || cr.private_notes.length === 0) &&
                                !videoUrl && (
                                  <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                                    No video, comments, or notes for this clip
                                  </div>
                                )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* No shares */}
              {!showRawJson && !loading && shareGroups.length === 0 && response && response.ok && (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: '12px' }}>🔗</span>
                  <p style={{ fontWeight: 600 }}>No shares found</p>
                </div>
              )}
            </div>
          )}

          {/* ═══ HIGHLIGHTS TAB ═══ */}
          {activeTab === 'highlights' && (
            <div className="animate-fade-in">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">Session Highlights</h2>
                <RawJsonToggle hasData={highlights.length > 0} />
              </div>

              <div className="flex flex-wrap gap-3 mb-8">
                <button className="btn btn-primary" onClick={() => fetchHighlights(() => ApiService.getSessionHighlights(sessionId))}>
                  ⚽ Get Highlights (Session {sessionId})
                </button>
                <button className="btn btn-outline" onClick={() => fetchHighlights(() => ApiService.getLegacySessionHighlights(sessionId))}>
                  Get Highlights (Legacy)
                </button>
              </div>

              {showRawJson && response && (
                <div className="animate-fade-in"><pre>{JSON.stringify(response.data, null, 2)}</pre></div>
              )}

              {!showRawJson && highlights.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {highlights.map((h) => (
                    <div key={h.id} className="highlight-card glass" style={{ padding: '20px', borderRadius: '14px', borderLeft: `4px solid ${h.side === 'home' ? '#6366f1' : '#f59e0b'}` }}>
                      <div className="flex items-center justify-between" style={{ marginBottom: '14px' }}>
                        <div className="flex items-center gap-3">
                          <span style={{ fontSize: '1.5rem' }}>{getEventEmoji(h.event_type)}</span>
                          <div>
                            <h3 style={{ fontWeight: 700, fontSize: '1.05rem', margin: 0 }}>{h.label || h.event_name}</h3>
                            <div style={{ display: 'flex', gap: '8px', marginTop: '4px', flexWrap: 'wrap' }}>
                              {h.side && <span className="badge" style={{ background: h.side === 'home' ? 'rgba(99,102,241,0.2)' : 'rgba(245,158,11,0.2)', color: h.side === 'home' ? '#818cf8' : '#fbbf24', textTransform: 'uppercase' }}>{h.side}</span>}
                              {h.half && <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>Half {h.half}</span>}
                              {h.match_time && <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>⏱ {h.match_time}</span>}
                              {h.event_type && <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>{h.event_type}</span>}
                            </div>
                          </div>
                        </div>
                        {h.trace_player && (
                          <div style={{ textAlign: 'right' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{h.trace_player.name}</span>
                            {h.trace_player.jersey_number != null && (
                              <span style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.8rem' }}>#{h.trace_player.jersey_number} • {h.trace_player.position || ''}</span>
                            )}
                          </div>
                        )}
                      </div>

                      {h.videos && h.videos.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          {h.videos.map(v => renderVideoPlayer(v))}
                        </div>
                      ) : (
                        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem', background: 'rgba(0,0,0,0.15)', borderRadius: '8px' }}>
                          No videos available for this highlight
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {!showRawJson && !loading && highlights.length === 0 && response && response.ok && (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: '12px' }}>🎬</span>
                  <p style={{ fontWeight: 600 }}>No highlights found for this session</p>
                </div>
              )}
            </div>
          )}

          {/* ═══ INTERACTIONS TAB ═══ */}
          {activeTab === 'interactions' && (
            <div className="animate-fade-in">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">Comments & Notes</h2>
                <RawJsonToggle hasData={comments.length > 0 || notes.length > 0 || noteReplies.length > 0} />
              </div>

              {/* Clip Reel Selector */}
              <div className="mb-6">
                <h3 className="font-bold mb-2">Clip Reel ID</h3>
                <input type="number" placeholder="Enter Clip Reel ID..." value={clipReelId}
                  onChange={e => setClipReelId(e.target.value)} style={{ maxWidth: 260 }} />
              </div>

              {/* Read actions */}
              <div className="flex gap-3 mb-8">
                <button className="btn btn-outline" onClick={() => fetchComments(clipReelId)} disabled={!clipReelId || loading}>
                  💬 Get Comments
                </button>
                <button className="btn btn-outline" onClick={() => fetchNotes(clipReelId)} disabled={!clipReelId || loading}>
                  📝 Get Notes
                </button>
              </div>

              {/* Raw JSON */}
              {showRawJson && response && (
                <div className="animate-fade-in"><pre>{JSON.stringify(response.data, null, 2)}</pre></div>
              )}

              {/* Rich comments view */}
              {!showRawJson && comments.length > 0 && (
                <div style={{ marginBottom: '24px' }}>
                  <h3 style={{ fontWeight: 700, marginBottom: '12px', color: '#818cf8' }}>
                    💬 Comments ({comments.length})
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {comments.map(c => renderCommentCard(c))}
                  </div>
                </div>
              )}

              {/* Rich notes view */}
              {!showRawJson && notes.length > 0 && (
                <div style={{ marginBottom: '24px' }}>
                  <h3 style={{ fontWeight: 700, marginBottom: '12px', color: '#34d399' }}>
                    📝 Notes ({notes.length})
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {notes.map(n => renderNoteCard(n))}
                  </div>
                </div>
              )}

              {/* Rich replies view */}
              {!showRawJson && noteReplies.length > 0 && (
                <div style={{ marginBottom: '24px' }}>
                  <h3 style={{ fontWeight: 700, marginBottom: '12px', color: '#818cf8' }}>
                    ↩️ Replies ({noteReplies.length})
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {noteReplies.map((r, i) => renderReplyCard(r, i))}
                  </div>
                </div>
              )}

              {/* Bulk Notes Creator */}
              {!showRawJson && (
                <>
                  <div className="glass p-6 rounded-xl">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-bold text-lg">📝 Create Bulk Notes</h3>
                      <button className="btn btn-outline" style={{ padding: '6px 16px', fontSize: '0.85rem' }} onClick={addNoteRow}>
                        + Add Note
                      </button>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {bulkNotes.map((note, idx) => (
                        <div key={idx} className="glass p-4 rounded-lg" style={{ borderLeft: '3px solid var(--color-primary, #6366f1)' }}>
                          <div className="flex items-center justify-between mb-3">
                            <span className="font-bold text-sm" style={{ opacity: 0.7 }}>Note #{idx + 1}</span>
                            {bulkNotes.length > 1 && (
                              <button onClick={() => removeNoteRow(idx)}
                                style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1rem' }}>
                                ✕ Remove
                              </button>
                            )}
                          </div>
                          <div className="input-group mb-3"><label>Content</label>
                            <textarea rows={2} placeholder="Enter note content..." value={note.content}
                              onChange={e => updateNoteRow(idx, 'content', e.target.value)}
                              style={{ resize: 'vertical', width: '100%' }} />
                          </div>
                          <div className="input-group mb-3"><label>Visibility</label>
                            <select value={note.visibility} onChange={e => updateNoteRow(idx, 'visibility', e.target.value)}
                              style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'inherit' }}>
                              <option value="public">🌐 Public</option>
                              <option value="private">🔒 Private</option>
                            </select>
                          </div>
                          {note.visibility === 'private' && (
                            <div className="input-group"><label>Private To (User IDs, comma-separated)</label>
                              <input type="text" placeholder="uuid1, uuid2, ..." value={note.private_to}
                                onChange={e => updateNoteRow(idx, 'private_to', e.target.value)} />
                              <span style={{ fontSize: '0.75rem', opacity: 0.5, marginTop: 4, display: 'block' }}>
                                e.g. 28513d86-dc08-4464-bd31-245fbfe303de, 2c31121d-...
                              </span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    <button className="btn btn-primary w-full" style={{ marginTop: '20px' }}
                      onClick={submitBulkNotes} disabled={loading || !clipReelId}>
                      {loading ? 'Creating...' : `🚀 Submit ${bulkNotes.length} Note(s) to Clip Reel #${clipReelId || '?'}`}
                    </button>
                  </div>

                  {/* Note Replies */}
                  <div className="glass p-6 rounded-xl" style={{ marginTop: '24px' }}>
                    <h3 className="font-bold text-lg" style={{ marginBottom: '16px' }}>💬 Note Replies</h3>

                    <div className="input-group"><label>Note ID</label>
                      <input type="number" placeholder="Enter Note ID (e.g. 65)" value={noteId}
                        onChange={e => setNoteId(e.target.value)} style={{ maxWidth: 260 }} />
                    </div>

                    <div className="flex gap-3 mb-8">
                      <button className="btn btn-outline" onClick={() => fetchReplies(noteId)} disabled={loading || !noteId}>
                        📋 List Replies for Note #{noteId || '?'}
                      </button>
                    </div>

                    <div className="input-group"><label>Reply Content</label>
                      <textarea rows={2} placeholder="Type your reply..." value={replyContent}
                        onChange={e => setReplyContent(e.target.value)} style={{ resize: 'vertical', width: '100%' }} />
                    </div>

                    <button className="btn btn-primary w-full"
                      onClick={() => { callApi(() => ApiService.replyToNote(noteId, replyContent)); setReplyContent(''); }}
                      disabled={loading || !noteId || !replyContent.trim()}>
                      {loading ? 'Sending...' : `🚀 Reply to Note #${noteId || '?'}`}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ═══ USERS TAB ═══ */}
          {activeTab === 'users' && (
            <div className="animate-fade-in">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">Session Users</h2>
                <div className="flex items-center gap-3">
                  <button className="btn btn-outline" style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                    onClick={() => console.log({ sessionUsers, response, loading })}>
                    🔍 Debug State
                  </button>
                  <RawJsonToggle hasData={sessionUsers.length > 0} />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 mb-8">
                <button className="btn btn-primary" onClick={() => fetchSessionUsers(sessionId)} disabled={loading}>
                  {loading ? 'Fetching...' : `👥 Get Users for Session ${sessionId}`}
                </button>

                {sessionUsers.length > 0 && !showRawJson && (
                  <div className="flex items-center gap-2 ml-4 p-1 bg-white/5 rounded-lg border border-white/10">
                    {['All', ...Object.keys(getGroupedUsers())].map(team => (
                      <button key={team}
                        onClick={() => setActiveTeam(team)}
                        className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTeam === team ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30' : 'hover:bg-white/5 text-muted'}`}>
                        {team}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {loading && <div className="text-center py-12 animate-pulse text-indigo-400 font-bold">CONNECTING TO WAJO API...</div>}

              {showRawJson && response && (
                <div className="animate-fade-in mb-8">
                  <pre className="glass p-4 rounded-lg overflow-x-auto max-h-[500px] text-sm font-mono leading-relaxed" style={{ background: 'rgba(0,0,0,0.4)' }}>
                    {JSON.stringify(response.data, null, 2)}
                  </pre>
                </div>
              )}

              {!showRawJson && sessionUsers.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
                  {(() => {
                    const groups = getGroupedUsers();
                    const list = activeTeam === 'All'
                      ? sessionUsers
                      : (groups[activeTeam] || []);
                    return list.map((u, i) => renderSessionUserCard(u, i));
                  })()}
                </div>
              )}

              {!loading && sessionUsers.length === 0 && response && response.ok && (
                <div className="glass p-12 text-center rounded-2xl border-dashed border-2 border-white/10">
                  <span className="text-4xl mb-4 block">👥</span>
                  <p className="text-muted">No users found for this session.</p>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Response Area - only for tabs that still show raw JSON */}
        {(activeTab === 'dashboard' ||
          (activeTab === 'interactions' && !showRawJson && comments.length === 0 && notes.length === 0 && noteReplies.length === 0)) && (
            <section className="glass p-8 min-h-[400px]">
              {loading ? (
                <div className="flex items-center justify-center h-full gap-4">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                  <p className="animate-pulse">Loading...</p>
                </div>
              ) : renderResponse()}
            </section>
          )}
      </main>

      <style>{`
        .justify-start { justify-content: flex-start; }
        .flex-1 { flex: 1; }
        .min-h-screen { min-height: 100vh; }
        .max-w-2xl { max-width: 42rem; }
        .opacity-60 { opacity: 0.6; }
        .border-t-transparent { border-top-color: transparent; }
        .italic { font-style: italic; }
        .flex-wrap { flex-wrap: wrap; }
        .truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      `}</style>
    </div>
  );
};

export default App;
