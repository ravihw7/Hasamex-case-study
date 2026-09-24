import os
import json
import re

USE_MOCK = os.environ.get("USE_MOCK", "false").lower() == "true"

MODEL = "claude-sonnet-4-6"


def _format_segments_for_prompt(segments) -> str:
    """
    Turns segments into a compact text block the AI can read, e.g.:
    [T1_004] Dr. Martin: The biggest issue is still capital budget approval...
    """
    lines = []
    for s in segments:
        lines.append(f"[{s.id}] {s.speaker}: {s.text}")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """
    LLMs sometimes wrap JSON in ```json fences or add a sentence before it.
    This strips that so json.loads() doesn't crash.
    """
    text = text.strip()
    text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.MULTILINE)
    # If there's still leading/trailing junk, grab the outermost {...}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def answer_question_for_call(question: str, segments) -> dict:
    """
    Asks the AI to answer ONE interview-guide question using ONLY the
    segments from ONE call (one expert).

    Returns JSON shaped like:
    {
        "answer": "short 1-2 sentence summary",
        "quotes": [
            {"quote": "...", "segment_id": "T1_004"},
            ...
        ],
        "confidence": "high" | "medium" | "low",
        "not_addressed": false
    }

    If the expert never addressed this topic, the AI should set
    "not_addressed": true instead of guessing - this is a key
    anti-hallucination instruction.
    """
    if USE_MOCK:
        return _mock_answer(question, segments)

    from anthropic import Anthropic
    client = Anthropic()

    segment_block = _format_segments_for_prompt(segments)

    system_prompt = """You are analysing ONE expert-call transcript for a market research project.
You will be given labeled segments like [T1_004] Speaker: text.

Rules you MUST follow:
1. Only use information present in the segments below. Never add outside knowledge.
2. Every quote you give must be copied EXACTLY (verbatim) from a segment's text.
3. You must cite the segment_id for every quote - never invent a timestamp yourself.
4. If the expert did not address this question, set "not_addressed": true and leave quotes empty.
5. Respond with ONLY valid JSON, no other text, in this exact shape:
{
  "answer": "1-2 sentence summary in your own words",
  "quotes": [{"quote": "exact text from a segment", "segment_id": "T1_004"}],
  "confidence": "high",
  "not_addressed": false
}"""

    user_prompt = f"""SEGMENTS:
{segment_block}

QUESTION: {question}

Respond with JSON only."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = response.content[0].text
    return _extract_json(raw_text)


def synthesize_theme(question: str, per_expert_answers: dict) -> dict:
    """
    Given each expert's verified answer to the SAME question, ask the AI
    to summarize agreement / disagreement across all 3.

    per_expert_answers example:
    {
        "T1": {"answer": "...", "verified_quotes": [...]},
        "T2": {"answer": "...", "verified_quotes": [...]},
        "T3": {"answer": "...", "verified_quotes": [...]},
    }

    Returns JSON:
    {
        "theme_summary": "...",
        "agreement": "...",
        "disagreement": "..." or null,
    }
    """
    if USE_MOCK:
        return _mock_theme(question, per_expert_answers)

    from anthropic import Anthropic
    client = Anthropic()

    context = json.dumps(per_expert_answers, indent=2)

    system_prompt = """You compare answers from 3 experts to the same interview question.
Only use the summaries and quotes given to you - do not add outside knowledge.
Respond with ONLY valid JSON in this shape:
{
  "theme_summary": "1-2 sentences on the overall pattern",
  "agreement": "what the experts agree on, or null if none",
  "disagreement": "what they disagree on, or null if none"
}"""

    user_prompt = f"""QUESTION: {question}

EXPERT ANSWERS:
{context}

Respond with JSON only."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = response.content[0].text
    return _extract_json(raw_text)


def answer_free_question(question: str, all_segments) -> dict:
    """
    For the "ask anything across transcripts" feature.
    Same JSON-with-citations pattern as answer_question_for_call, but
    across ALL segments from ALL 3 calls at once.
    """
    if USE_MOCK:
        return _mock_answer(question, all_segments)

    from anthropic import Anthropic
    client = Anthropic()

    segment_block = _format_segments_for_prompt(all_segments)

    system_prompt = """You answer a user's free-form question using ONLY the transcript
segments provided below, which come from 3 different expert calls (T1, T2, T3).

Rules:
1. Only use information present in the segments. Never use outside knowledge.
2. Every quote must be copied EXACTLY from a segment's text.
3. Cite segment_id for every quote used.
4. If the answer is not in the transcripts, set "not_addressed": true.
5. Respond with ONLY valid JSON:
{
  "answer": "your answer in plain language",
  "quotes": [{"quote": "exact text", "segment_id": "T2_005"}],
  "not_addressed": false
}"""

    user_prompt = f"""SEGMENTS (from all 3 calls):
{segment_block}

QUESTION: {question}

Respond with JSON only."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = response.content[0].text
    return _extract_json(raw_text)


# ---------------------------------------------------------------------------
# MOCK MODE - lets you run and demo the app with ZERO API key / ZERO cost.
# It does simple keyword matching instead of real AI reasoning. Useful for
# testing the UI, but for your real submission, set USE_MOCK=false and use
# a real API key so the answers are genuinely AI-generated.
# ---------------------------------------------------------------------------

def _mock_answer(question: str, segments) -> dict:
    keywords = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", question)]
    best = None
    best_score = 0
    for s in segments:
        if s.speaker.lower() == "interviewer":
            continue
        score = sum(1 for k in keywords if k in s.text.lower())
        if score > best_score:
            best_score = score
            best = s
    if best is None or best_score == 0:
        return {"answer": "Not addressed in this call.", "quotes": [], "confidence": "low", "not_addressed": True}
    return {
        "answer": f"(mock) {best.speaker} discusses this around {best.timestamp}.",
        "quotes": [{"quote": best.text, "segment_id": best.id}],
        "confidence": "medium",
        "not_addressed": False,
    }


def _mock_theme(question: str, per_expert_answers: dict) -> dict:
    return {
        "theme_summary": "(mock) All experts touch on this topic with varying emphasis.",
        "agreement": "(mock) Budget/economics comes up across experts.",
        "disagreement": None,
    }
