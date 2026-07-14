# Trending Keywords → Video Generation Integration

Date: 2026-07-14
Status: Approved for planning

## Goal

Give users an option to build a video-generation prompt from trending social
posts (X/Twitter, Instagram, Threads, or manually pasted posts from any
platform) instead of hand-typing one, then generate the video via the
existing Seedance/Ark video-variation pipeline. Also fix that pipeline,
which is currently miscalling the Ark API.

## Source material

Two standalone Python files were provided as a starting point:

- `app.py` — a Streamlit app: fetches trending posts from X/Instagram/Threads
  (or accepts manually pasted posts), extracts keywords (TF-IDF), rewrites
  captions via Claude (with a template fallback), builds UTM-tracked links,
  and exports Buffer bulk-upload CSVs.
- `twitter_trends_to_buffer.py` — an older, X-only, non-interactive subset of
  the same pipeline (script + CLI entrypoint).

`app.py` is a strict superset of `twitter_trends_to_buffer.py`. This design
ports `app.py`'s logic into the existing product; `twitter_trends_to_buffer.py`
is not carried forward as a separate artifact.

## Current state (this repo)

- `backend/app/main.py` — FastAPI app. `POST /api/variations` accepts an
  uploaded video + prompt + style, calls Seedance/Ark, falls back to an
  ffmpeg preview or a plain copy if the call fails or no key is set.
- `frontend/src/App.jsx` — single-page React app (Vite) with Discover,
  Workflow, Generator, and Library sections. Generator has the upload +
  prompt + style form that calls `/api/variations`.
- No database. No Streamlit anywhere in the product today.
- `.env` currently has `SEEDANCE_API_KEY`, `SEEDANCE_API_URL`,
  `PUBLIC_BACKEND_URL`. No X/Anthropic/Instagram/Threads credentials exist
  yet — the user must supply real values for those.

## Decisions made during brainstorming

1. **Architecture**: fold the trends pipeline into the existing FastAPI +
   React product. No Streamlit in the final product.
2. **Scope**: full parity with `app.py` — X (trending + search), Instagram
   hashtag search, Threads keyword search, manual paste, and Buffer CSV
   export are all in scope for v1. Facebook is out (no compliant API exists;
   `app.py` only ever showed an error for it).
3. **Prompt building**: selecting a trend/post auto-fills the video prompt
   field (via a new Claude rewrite template, with a template-based
   fallback), and the user can edit it before generating.
4. **Video source**: the existing video-to-video flow is unchanged — a
   source video upload is still required. This feature only changes how the
   *prompt* field gets populated. No text-to-video capability is added.
5. **Ark/Seedance contract**: the current `create_variation` implementation
   is wrong (POSTs raw multipart bytes to a single synchronous endpoint) and
   is fixed as part of this work, not deferred.
6. **State/persistence**: the manual-paste queue and the Instagram
   30-hashtags/7-days cap tracker live in React state only (no backend
   persistence, no localStorage). This is a soft UI warning, not an
   authoritative guard — acceptable since it mirrors `app.py`'s own
   per-session (not cross-device) tracking.
7. **UI placement**: a new "Trends" section is added to the single-page
   React app (nav: Discover | Workflow | Trends | Generator | Library) with
   its own source picker, results table, and CSV export buttons. Each result
   row has a "Use for video" action that scrolls to Generator and fills its
   prompt field.

## Backend design

### `backend/app/trends.py` (new module)

Pure functions ported from `app.py`, with no Streamlit dependency:

- Text helpers: `clean_text`, `extract_hashtags`, `slugify`
- X: `get_trending_topics(woeid, limit)`, `search_recent_posts(query,
  max_results)`, `engagement_score(post)`
- Instagram: `ig_find_hashtag_id`, `ig_get_hashtag_media`,
  `search_instagram_hashtag`
- Threads: `search_threads_keyword`
- Keywords: `extract_tfidf_keywords` (scikit-learn), `extract_simple_keywords`
- Rewriting: `template_rewrite` (caption fallback), `template_video_prompt`
  (new — video-prompt fallback), and a generalized `rewrite_with_claude`
  that both the caption path and the video-prompt path call with different
  prompt templates
- Links/export: `build_tracked_link`, `make_buffer_csv`,
  `make_full_export_csv`

Facebook-specific code (`search_facebook_public_posts`) is not ported — there
is no working API to call, and no Facebook option is offered in the routes
or UI.

### New routes (added to `main.py` or a `trends` router included into `app`)

```
GET  /api/trends/x?woeid=&limit=
GET  /api/trends/x/search?query=&max_results=&top_n=
GET  /api/trends/instagram?hashtag=&max_results=&top_n=
GET  /api/trends/threads?keyword=&max_results=&top_n=
POST /api/trends/manual        body: [{trend, platform, text}]
POST /api/trends/video-prompt  body: {trend, keywords, original_text} -> {prompt}
POST /api/trends/export        body: {rows: [...], format: "buffer"|"full", gap_minutes} -> CSV
```

All GET/manual routes return rows in one shared shape (Platform, Trend, Post
ID, Post URL, Original Text, Keywords, Hashtags, Likes, Comments, Retweets,
Quotes, Engagement Score, Created At) so the frontend table and the export
endpoint can consume the same schema without transformation.

Each route checks its required env var(s) up front and returns `503` with a
descriptive message if missing (e.g. "Missing X_BEARER_TOKEN"), matching the
`st.error` guard pattern already used in `app.py`. It does not raise
unhandled exceptions for missing config.

### Video-prompt generation

New Claude prompt template (distinct from the existing caption-rewrite
template):

```
Turn the following trending topic into a short, concrete visual-direction
prompt for AI video generation (not marketing copy).

Rules:
- Describe visual subject, mood, lighting, and motion - not hashtags or CTAs.
- 1-3 sentences, concrete and filmable.
- No quotation marks, no hashtags, no links.

Trend/topic: {trend}
Key themes: {keywords}
Source post (for context only): {original_text}
```

Falls back to `template_video_prompt()` — a template-built visual
description from the trend + top keywords — if `ANTHROPIC_API_KEY` is unset
or the Claude call fails, mirroring the existing caption fallback pattern.

### Ark/Seedance contract fix

The current implementation POSTs raw multipart video bytes to a single
synchronous URL and expects `output_url`/`video_url` back immediately. Based
on BytePlus's actual Seedance/Ark API (confirmed via BytePlus docs and
corroborating third-party integration guides — see Sources below), the real
contract is JSON-based, references media by URL, and is asynchronous
(submit → poll):

1. Save the upload and serve it via the existing `/media/uploads/...`
   static route (the code already computes this URL as `original_url` but
   doesn't currently use it in the Ark call).
2. `POST {SEEDANCE_API_URL}/contents/generations/tasks` with:
   ```json
   {
     "model": "<model id>",
     "content": [
       {"type": "text", "text": "<prompt>"},
       {"type": "video_url", "video_url": {"url": "<original_url>"}}
     ]
   }
   ```
3. Poll `GET {SEEDANCE_API_URL}/contents/generations/tasks/{id}` (e.g. every
   3s, ~120s timeout) until `status` is `"succeeded"` or `"failed"`.
4. On success, download `content.video_url` into `output_path`. On
   failure/timeout, fall back to the existing ffmpeg/copy path with a
   descriptive note, same as today.

**Open items to verify against the real BytePlus account during
implementation** (BytePlus's own reference pages are JS-rendered and did not
yield literal field names even via fetch; the shape below is corroborated
by multiple third-party integration guides, not BytePlus's primary
reference):
- The exact model id string to use (e.g. something like
  `doubao-seedance-2-0-260128` — must be confirmed against the BytePlus
  console for this account).
- Whether the video-reference content type is literally `video_url` with
  that exact nesting, or something else (e.g. a `role` field alongside it
  as seen for `image_url` references).

A real smoke-test call against the live Ark endpoint is required before this
piece is considered done — this is not something unit tests alone can
verify.

Sources:
- https://docs.byteplus.com/en/docs/ModelArk/Video_Generation_API
- https://www.datacamp.com/tutorial/seedance-2-0-api-guide
- https://apidog.com/blog/seedance-2-0-api/

## Frontend design

New `<section id="trends">` in `App.jsx`, added to nav between Workflow and
Generator:

- Source selector: X search, X trending (WOEID), Instagram hashtag, Threads
  keyword, or Paste manually — mirrors `app.py`'s sidebar modes
- Per-source inputs matching each mode (query/hashtag/keyword text input, or
  a paste textarea + trend label + platform select for manual mode)
- "Fetch" button calls the matching route, populates a results table
  (Platform, Trend, Keywords, Engagement, Post URL, Original Text excerpt)
- Manual-paste queue and the Instagram hashtag-cap tracker (30/7-day) live
  in plain React state (array + `Set`) — no persistence across refresh
- Each row has a "Use for video" button: calls
  `POST /api/trends/video-prompt`, sets Generator's existing `prompt` state,
  and scrolls to `#generator`
- Two download buttons call `POST /api/trends/export` with `format=buffer`
  / `format=full` and trigger a file download from the response blob

No changes to the existing Generator or Library sections beyond the prompt
field being fillable from outside (it already is, via `useState`).

## Config & dependencies

`backend/requirements.txt` additions: `pandas`, `scikit-learn`.

`backend/.env` additions (user-supplied real values; `.env.example` gets
placeholders):

```
X_BEARER_TOKEN=
ANTHROPIC_API_KEY=
IG_ACCESS_TOKEN=
IG_BUSINESS_ACCOUNT_ID=
THREADS_ACCESS_TOKEN=
```

## Testing

- Backend unit tests for pure functions that need no network mocking:
  `extract_hashtags`, `extract_tfidf_keywords`, `template_rewrite`,
  `template_video_prompt`, `build_tracked_link`, CSV builders.
- Backend route tests with `httpx`/`requests` mocked for X, Instagram,
  Threads, Anthropic, and Ark calls.
- Frontend: manual verification via the dev server — exercise Trends →
  "Use for video" → Generate for at least one API source and the paste
  mode.
- Ark fix: manual smoke test against the real BytePlus endpoint with a real
  API key before considering the fix done, given the two open verification
  items above.

## Out of scope

- Facebook trend fetching (no compliant API exists).
- Text-to-video generation (no source-video upload).
- Server-side persistence of the manual-paste queue or Instagram
  hashtag-cap tracking.
- Any authentication/user-account system (none exists today; not being
  added here).
