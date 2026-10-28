# Expert Call Analyzer — Hasamex AI Engineer Case.   

Analyzes 3 expert-call transcripts (robotic surgery market research) to:
answer interview-guide questions per expert, extract exact quotes with
timestamps, identify cross-expert themes/disagreements, and answer
free-form questions across all transcripts.

## Why this design

The single biggest risk in this task is **hallucination**: an LLM
inventing a quote or a timestamp that sounds plausible but isn't real.
This app is built around one core idea to prevent that:

> **The LLM never generates a timestamp. It only points at a segment ID
> we gave it. Our code looks up the real timestamp and independently
> verifies the claimed quote text against the source before showing it.**

Every transcript line is parsed into a `Segment` with a unique ID, a
speaker, a real timestamp, and the exact text. The LLM is given these
labeled segments and asked to answer using **structured JSON only**,
citing segment IDs for every quote. A separate verification step
(`verifier.py`) then checks each claimed quote against the real segment
text — exact match first, fuzzy match as a fallback — and marks it
✅ verified, ⚠️ near-match, or ❌ rejected. Rejected quotes are dropped
from what's shown to the user.

## Architecture

```
Transcripts (.txt)
      |
   parser.py        -> Segment[] (id, call_id, speaker, timestamp, text)
      |
   llm_client.py     -> asks Claude for JSON {answer, quotes:[{quote, segment_id}]}
      |
   verifier.py       -> checks each quote against the real segment text
      |
   pipeline.py       -> orchestrates the above per feature
      |
   app.py (Streamlit)-> UI: Interview Guide / Themes / Ask / Transcripts
```

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
cd app
streamlit run app.py
```

To demo without an API key, run in mock mode instead (uses simple
keyword matching, not real AI reasoning — for UI testing only):

```bash
export USE_MOCK=true
streamlit run app.py
```

## Key design decisions

- **No vector database / RAG.** With only 3 short transcripts (~40
  segments total), passing all segments directly to the model is more
  accurate and simpler than retrieval. At 30+ transcripts, this would
  need to change — see "Scaling" below.
- **Structured JSON output, not free text.** Every LLM call returns a
  strict JSON shape so the app can programmatically verify it, rather
  than trusting prose.
- **Quotes are verified in code, not trusted from the model.** This is
  the main hallucination defense — see `verifier.py`.
- **"Not addressed" is a valid answer.** The model is explicitly
  instructed to say when a topic wasn't discussed rather than guessing.

## Scaling to 30+ transcripts

- Add a vector index (e.g. FAISS/Chroma) over segments, retrieve
  top-k relevant segments per question instead of sending everything.
- Batch/parallelize per-call LLM calls.
- Add a lightweight metadata filter (market, role) so users can narrow
  the corpus before asking.
- Cache LLM responses per (question, call) pair to avoid recomputation.
- The verification layer (`verifier.py`) does not need to change —
  it scales to any number of segments as-is.

## Limitations

- Fuzzy-match verification threshold (0.90) is a heuristic; edge cases
  (heavy paraphrasing of a true statement) may be rejected as false
  negatives — intentional, since we favor precision over recall for
  quotes.
- Mock mode uses naive keyword matching and is not representative of
  real answer quality.
