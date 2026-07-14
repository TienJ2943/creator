import { useEffect, useMemo, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const PUBLIC_BASE = import.meta.env.BASE_URL || '/';

const apiUrl = (path) => `${API_BASE}${path}`;

const cinematicStats = [
  { value: '4K-ready', label: 'export workflow' },
  { value: '< 2 min', label: 'first variation preview' },
  { value: 'AI + human', label: 'review loop' },
];

const featuredCollections = [
  {
    title: 'Fashion launch',
    tag: 'Luxury',
    text: 'Golden-hour movement, tactile close-ups, and refined pacing for premium brand drops.',
  },
  {
    title: 'Travel trailer',
    tag: 'Adventure',
    text: 'Fast scenic cuts, atmospheric grading, and motion-led edits built for destination storytelling.',
  },
  {
    title: 'Night city reel',
    tag: 'Editorial',
    text: 'Neon contrast, elegant speed ramps, and sleek camera language for modern campaign films.',
  },
];

const workflowStages = [
  'Upload a source clip or campaign draft',
  'Route the brief through the orchestration layer',
  'Generate multiple cinematic directions',
  'Score quality, pacing, and brief alignment',
  'Refine winning cuts and write the final memo',
];

const styleOptions = ['Cinematic', 'Editorial', 'High Contrast', 'Dreamscape'];

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [prompt, setPrompt] = useState('Turn this clip into a premium fashion campaign with elegant motion and golden-hour lighting.');
  const [style, setStyle] = useState('Cinematic');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [library, setLibrary] = useState([]);
  const [trendSource, setTrendSource] = useState('x-search');
  const [xQuery, setXQuery] = useState('#AI');
  const [baseLinkInput, setBaseLinkInput] = useState('https://yourdomain.com/blog');
  const [campaignNameInput, setCampaignNameInput] = useState('trend_roundup');
  const [trendRows, setTrendRows] = useState([]);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendError, setTrendError] = useState('');
  const [igHashtag, setIgHashtag] = useState('sustainablefashion');
  const [threadsKeyword, setThreadsKeyword] = useState('sustainable fashion');
  const [pasteTrend, setPasteTrend] = useState('');
  const [pastePlatform, setPastePlatform] = useState('X');
  const [pasteBlock, setPasteBlock] = useState('');
  const [manualQueue, setManualQueue] = useState([]);
  const [igHashtagsQueried, setIgHashtagsQueried] = useState(new Set());

  useEffect(() => {
    fetch(apiUrl('/api/videos'))
      .then((res) => res.json())
      .then(setLibrary)
      .catch(() => setLibrary([]));
  }, []);

  const libraryItems = useMemo(() => {
    if (library.length > 0) return library;

    return featuredCollections.map((item, index) => ({
      id: `sample-${index}`,
      title: item.title,
      prompt: item.text,
      status: 'ready',
      original_url: `https://images.unsplash.com/photo-${['1515886657613-9f3515b0c78f','1492691527719-9d1e07e534b4','1500530855697-b586d89ba3ee'][index]}?auto=format&fit=crop&w=1200&q=80`,
    }));
  }, [library]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!selectedFile) {
      setError('Please upload a video first.');
      return;
    }

    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('video', selectedFile);
    formData.append('prompt', prompt);
    formData.append('style', style);

    try {
      const response = await fetch(apiUrl('/api/variations'), {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Generation failed.');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  const handleFetchTrends = async (event) => {
    event.preventDefault();
    setTrendLoading(true);
    setTrendError('');

    try {
      if (trendSource === 'manual') {
        if (manualQueue.length === 0) {
          throw new Error('Add at least one pasted post before submitting.');
        }
        const response = await fetch(apiUrl('/api/trends/manual'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            base_link: baseLinkInput,
            campaign_name: campaignNameInput,
            use_ai_rewrite: true,
            entries: manualQueue,
          }),
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || 'Could not submit pasted posts.');
        }
        setTrendRows(await response.json());
        return;
      }

      let path;
      const params = new URLSearchParams({ base_link: baseLinkInput, campaign_name: campaignNameInput });

      if (trendSource === 'x-search') {
        params.set('query', xQuery);
        path = `/api/trends/x/search?${params.toString()}`;
      } else if (trendSource === 'instagram') {
        params.set('hashtag', igHashtag);
        path = `/api/trends/instagram?${params.toString()}`;
      } else {
        params.set('keyword', threadsKeyword);
        path = `/api/trends/threads?${params.toString()}`;
      }

      const response = await fetch(apiUrl(path));
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Could not fetch trends.');
      }
      const data = await response.json();
      setTrendRows(data);

      if (trendSource === 'instagram') {
        setIgHashtagsQueried((prev) => new Set([...prev, igHashtag.replace(/^#/, '')]));
      }
    } catch (err) {
      setTrendError(err.message || 'Something went wrong.');
    } finally {
      setTrendLoading(false);
    }
  };

  const handleUseForVideo = async (row) => {
    try {
      const response = await fetch(apiUrl('/api/trends/video-prompt'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trend: row.trend,
          keywords: row.keywords,
          original_text: row.original_text,
        }),
      });
      if (!response.ok) return;
      const data = await response.json();
      setPrompt(data.prompt);
      document.getElementById('generator')?.scrollIntoView({ behavior: 'smooth' });
    } catch {
      // no-op: leave the existing prompt untouched on failure
    }
  };

  const handleExportTrends = async (format) => {
    const response = await fetch(apiUrl('/api/trends/export'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: trendRows, format, gap_minutes: 90 }),
    });
    if (!response.ok) return;

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = format === 'buffer' ? 'buffer_bulk_upload.csv' : 'posts_full_export.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleAddToQueue = (event) => {
    event.preventDefault();
    const posts = pasteBlock.includes('---')
      ? pasteBlock.split('---').map((chunk) => chunk.trim()).filter(Boolean)
      : pasteBlock.split('\n').map((line) => line.trim()).filter(Boolean);

    if (!pasteTrend.trim() || posts.length === 0) return;

    setManualQueue((prev) => [
      ...prev,
      ...posts.map((text) => ({ trend: pasteTrend.trim(), platform: pastePlatform, text })),
    ]);
    setPasteBlock('');
  };

  return (
    <div className="page-shell">
      <header className="hero">
        <nav className="topbar">
          <div className="brand-wrap">
            <div className="brand-mark">V</div>
            <div className="brand-copy">
              <div className="brand">Visionary Studio</div>
              <span>AI video generation</span>
            </div>
          </div>
          <div className="nav-links">
            <a href={`${PUBLIC_BASE}#discover`}>Discover</a>
            <a href={`${PUBLIC_BASE}#workflow`}>Workflow</a>
            <a href={`${PUBLIC_BASE}#trends`}>Trends</a>
            <a href={`${PUBLIC_BASE}#generator`}>Generator</a>
            <a href={`${PUBLIC_BASE}#library`}>Library</a>
          </div>
        </nav>

        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Cinematic AI video platform</p>
            <h1>Create campaign-ready videos with an Artlist-like visual feel.</h1>
            <p className="hero-text">
              Browse rich cinematic inspiration, upload your source footage, then generate polished
              variations through one premium creative workflow.
            </p>
            <div className="hero-actions">
              <a className="primary-btn" href={`${PUBLIC_BASE}#generator`}>Start creating</a>
              <a className="ghost-btn" href={`${PUBLIC_BASE}#discover`}>Explore looks</a>
            </div>
            <div className="stat-row">
              {cinematicStats.map((item) => (
                <div key={item.label} className="stat-card">
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="hero-visual">
            <div className="hero-frame hero-frame-main">
              <div className="frame-overlay">
                <span className="frame-tag">Featured look</span>
                <strong>Fashion campaign in amber light</strong>
                <p>Prompt-led transformation, elegant motion, premium pacing.</p>
              </div>
            </div>
            <div className="hero-side-stack">
              <div className="hero-frame hero-frame-side top">
                <div className="frame-overlay">
                  <span className="frame-tag">Travel reel</span>
                  <strong>Wide cinematic motion</strong>
                </div>
              </div>
              <div className="hero-frame hero-frame-side bottom">
                <div className="frame-overlay">
                  <span className="frame-tag">Editorial cut</span>
                  <strong>Night city neon</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main>
        <section className="discover-section" id="discover">
          <div className="section-heading split">
            <div>
              <p className="eyebrow">Discover</p>
              <h2>Browse premium moods before you generate.</h2>
            </div>
            <p className="section-text">
              Inspired by Artlist’s cinematic browsing experience, but tailored for prompt-based video
              generation and creative iteration.
            </p>
          </div>
          <div className="discover-grid">
            {featuredCollections.map((item, index) => (
              <article className={`discover-card card-${index + 1}`} key={item.title}>
                <div className="discover-overlay">
                  <span>{item.tag}</span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="workflow-panel" id="workflow">
          <div className="workflow-copy">
            <p className="eyebrow">Workflow</p>
            <h2>From raw footage to final creative memo.</h2>
            <p className="section-text">
              Visionary Studio keeps the whole production loop together, from orchestration to quality
              scoring to final export notes.
            </p>
          </div>
          <div className="workflow-list">
            {workflowStages.map((stage, index) => (
              <div className="workflow-step"  key={stage}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <p>{stage}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="trends-section" id="trends">
          <div className="section-heading split">
            <div>
              <p className="eyebrow">Trends</p>
              <h2>Pull a prompt from what's trending right now.</h2>
            </div>
            <p className="section-text">
              Fetch trending posts, then send one straight into the Generator as a
              video prompt.
            </p>
          </div>

          <form className="trends-form" onSubmit={handleFetchTrends}>
            <label>
              Source
              <select value={trendSource} onChange={(e) => setTrendSource(e.target.value)}>
                <option value="x-search">X search</option>
                <option value="instagram">Instagram hashtag</option>
                <option value="threads">Threads keyword</option>
                <option value="manual">Paste manually</option>
              </select>
            </label>
            {trendSource === 'x-search' && (
              <label>
                Search query / hashtag
                <input type="text" value={xQuery} onChange={(e) => setXQuery(e.target.value)} />
              </label>
            )}
            {trendSource === 'instagram' && (
              <label>
                Instagram hashtag
                <input type="text" value={igHashtag} onChange={(e) => setIgHashtag(e.target.value)} />
                <span className="hint">{igHashtagsQueried.size} / 30 hashtags used this window</span>
              </label>
            )}
            {trendSource === 'threads' && (
              <label>
                Threads keyword
                <input type="text" value={threadsKeyword} onChange={(e) => setThreadsKeyword(e.target.value)} />
              </label>
            )}
            <label>
              Base link
              <input type="text" value={baseLinkInput} onChange={(e) => setBaseLinkInput(e.target.value)} />
            </label>
            <label>
              Campaign name
              <input type="text" value={campaignNameInput} onChange={(e) => setCampaignNameInput(e.target.value)} />
            </label>
            <button className="primary-btn" type="submit" disabled={trendLoading}>
              {trendLoading ? 'Fetching...' : 'Fetch trends'}
            </button>
            {trendError && <p className="error-text">{trendError}</p>}
          </form>

          {trendSource === 'manual' && (
            <div className="manual-paste-panel">
              <label>
                Topic / trend label
                <input type="text" value={pasteTrend} onChange={(e) => setPasteTrend(e.target.value)} />
              </label>
              <label>
                Platform
                <select value={pastePlatform} onChange={(e) => setPastePlatform(e.target.value)}>
                  <option>X</option>
                  <option>Instagram</option>
                  <option>Threads</option>
                  <option>Facebook</option>
                  <option>Other</option>
                </select>
              </label>
              <label>
                Paste post captions (one per line, or separate multi-line posts with a line containing only ---)
                <textarea value={pasteBlock} onChange={(e) => setPasteBlock(e.target.value)} rows="4" />
              </label>
              <button className="ghost-btn" type="button" onClick={handleAddToQueue}>Add to queue</button>
              <p className="hint">{manualQueue.length} post(s) queued</p>
            </div>
          )}

          {trendRows.length > 0 && (
            <>
              <table className="trends-table">
                <thead>
                  <tr>
                    <th>Platform</th>
                    <th>Trend</th>
                    <th>Keywords</th>
                    <th>Engagement</th>
                    <th>Original text</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {trendRows.map((row) => (
                    <tr key={`${row.platform}-${row.post_id}-${row.trend}`}>
                      <td>{row.platform}</td>
                      <td>{row.trend}</td>
                      <td>{row.keywords.join(', ')}</td>
                      <td>{row.engagement_score}</td>
                      <td>{row.original_text}</td>
                      <td>
                        <button className="ghost-btn" type="button" onClick={() => handleUseForVideo(row)}>
                          Use for video
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="trends-export-actions">
                <button className="ghost-btn" type="button" onClick={() => handleExportTrends('buffer')}>
                  Download Buffer CSV
                </button>
                <button className="ghost-btn" type="button" onClick={() => handleExportTrends('full')}>
                  Download full CSV
                </button>
              </div>
            </>
          )}
        </section>

        <section className="generator-section" id="generator">
          <div className="generator-card">
            <p className="eyebrow">Generate</p>
            <h2>Upload footage and direct the look.</h2>
            <form onSubmit={handleSubmit}>
              <label>
                Video file
                <input type="file" accept="video/*" onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} />
              </label>
              <label>
                Prompt
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows="4" />
              </label>
              <label  >
                Style preset
                <select value={style} onChange={(e) => setStyle(e.target.value)}>
                  {styleOptions.map((option) => <option key={option}>{option}</option>)}
                </select>
              </label>
              <button className="primary-btn full" type="submit" disabled={loading}>
                {loading ? 'Generating...' : 'Generate variation'}
              </button>
              {error && <p className="error-text">{error}</p>}
            </form>
          </div>

          <div className="result-card">
            <p className="eyebrow">Output</p>
            <h2>Latest preview</h2>
            {result ? (
              <div className="result-grid">
                <video controls src={result.original_url} />
                <video controls src={result.variation_url} />
                <div className="result-meta">
                  <strong>Prompt</strong>
                  <p>{result.prompt}</p>
                  <strong>Notes</strong>
                  <ul>
                    {result.notes.map((note) => <li key={note}>{note}</li>)}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="placeholder-card cinematic-placeholder">
                <div>
                  <strong>Preview area</strong>
                  <p>Your latest variation, source clip, and production notes will appear here.</p>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="library-section" id="library">
          <div className="section-heading split">
            <div>
              <p className="eyebrow">Library</p>
              <h2>Curated looks, references, and recent renders.</h2>
            </div>
            <p className="section-text">
              Use the library like an inspiration browser, then jump straight into generation when a
              visual direction clicks.
            </p>
          </div>
          <div className="library-grid">
            {libraryItems.map((item) => (
              <article className="library-card" key={item.id}>
                <img src={item.original_url} alt={item.title} />
                <div className="library-copy">
                  <div className="library-title-row">
                    <h3>{item.title}</h3>
                    <span className={`status ${item.status}`}>{item.status}</span>
                  </div>
                  <p>{item.prompt}</p>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
