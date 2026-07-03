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
              <div className="workflow-step" key={stage}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <p>{stage}</p>
              </div>
            ))}
          </div>
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
              <label>
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
