from difflib import SequenceMatcher
from typing import Optional


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def verify_quote(claimed_quote: str, segment_text: str, threshold: float = 0.90) -> dict:
    """
    Returns a dict describing the verification result:
    {
        "status": "verified" | "near_match" | "rejected",
        "similarity": 0.0-1.0,
        "true_text": the real segment text (always included for reference)
    }

    - "verified": the claimed quote is an exact (or near-exact) substring
      of the real segment text.
    - "near_match": similar enough to the WHOLE segment to likely be a
      light paraphrase, but not an exact quote - we snap it back to the
      real text rather than show the paraphrase.
    - "rejected": not similar enough to trust at all - drop it.
    """
    claimed_clean = claimed_quote.strip().strip('"').strip()
    segment_clean = segment_text.strip()

    if not claimed_clean:
        return {"status": "rejected", "similarity": 0.0, "true_text": segment_clean}

    # Level 1: exact substring match (case-insensitive)
    if claimed_clean.lower() in segment_clean.lower():
        return {"status": "verified", "similarity": 1.0, "true_text": segment_clean}

    # Level 2: fuzzy match against the full segment text
    sim = _similarity(claimed_clean, segment_clean)
    if sim >= threshold:
        return {"status": "near_match", "similarity": round(sim, 3), "true_text": segment_clean}

    return {"status": "rejected", "similarity": round(sim, 3), "true_text": segment_clean}


def verify_all_quotes(claimed_items: list, segments_by_id: dict) -> list:
    """
    claimed_items: list of dicts like {"quote": "...", "segment_id": "T1_004"}
    segments_by_id: {"T1_004": Segment(...), ...}

    Returns an enriched list where each item now also has:
    - verification status
    - the real timestamp (pulled from OUR data, never from the AI)
    - the real speaker
    Items that fail verification are marked rejected but still returned
    so you can show "3 verified / 1 rejected" in the UI for transparency.
    """
    results = []
    for item in claimed_items:
        seg_id = item.get("segment_id")
        segment = segments_by_id.get(seg_id)

        if segment is None:
            results.append({
                **item,
                "status": "rejected",
                "reason": f"segment_id '{seg_id}' does not exist",
                "timestamp": None,
                "speaker": None,
            })
            continue

        check = verify_quote(item.get("quote", ""), segment.text)
        results.append({
            **item,
            "status": check["status"],
            "similarity": check["similarity"],
            "display_quote": check["true_text"] if check["status"] != "rejected" else None,
            "timestamp": segment.timestamp,   # <- always the REAL timestamp
            "speaker": segment.speaker,
            "call_id": segment.call_id,
        })
    return results


if __name__ == "__main__":
    # Quick manual test
    fake_segment_text = "The biggest issue is still capital budget approval. Hospitals may like the technology clinically."
    tests = [
        "biggest issue is still capital budget approval",   # should be VERIFIED (substring)
        "budget approval is the main obstacle",              # should be REJECTED or near_match (paraphrase)
        "the moon is made of cheese",                        # should be REJECTED
    ]
    for t in tests:
        print(t, "->", verify_quote(t, fake_segment_text))
