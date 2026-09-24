from parser import parse_all_transcripts, Segment
from verifier import verify_all_quotes
from llm_client import answer_question_for_call, synthesize_theme, answer_free_question

FILE_MAP = {
    "T1": ("../case_pack/Transcript_1_France.txt", "Dr. Jean Martin", "France"),
    "T2": ("../case_pack/Transcript_2_Germany.txt", "Anna Keller", "Germany"),
    "T3": ("../case_pack/Transcript_3_UK.txt", "Expert 3", "UK"),
}

GUIDE_QUESTIONS = [
    "How would you describe current adoption of robotic surgery in your market?",
    "What are the main barriers to adoption?",
    "How important are hospital budgets and ROI in purchasing decisions?",
    "How important are surgeon training and clinical outcomes?",
    "What adoption trend do you expect over the next 3-5 years?",
    "What is the typical hospital decision-making timeline for purchasing a new robotic system?",
]


def load_all_segments():
    """Returns (all_segments, segments_by_call, segments_by_id)."""
    all_segments = parse_all_transcripts(FILE_MAP)
    segments_by_call = {}
    for s in all_segments:
        segments_by_call.setdefault(s.call_id, []).append(s)
    segments_by_id = {s.id: s for s in all_segments}
    return all_segments, segments_by_call, segments_by_id


def get_verified_answer_for_call(question: str, call_id: str, segments_by_call: dict, segments_by_id: dict) -> dict:
    """
    Full pipeline for ONE question + ONE call:
    1. Ask the AI (llm_client.answer_question_for_call)
    2. Verify every quote it returned (verifier.verify_all_quotes)
    3. Return a clean result with only verified/near_match quotes shown
    """
    call_segments = segments_by_call[call_id]
    raw = answer_question_for_call(question, call_segments)

    if raw.get("not_addressed"):
        return {"answer": None, "not_addressed": True, "quotes": []}

    verified_quotes = verify_all_quotes(raw.get("quotes", []), segments_by_id)

    return {
        "answer": raw.get("answer"),
        "not_addressed": False,
        "confidence": raw.get("confidence", "medium"),
        "quotes": verified_quotes,  # includes status: verified / near_match / rejected
    }


def get_theme_across_calls(question: str, segments_by_call: dict, segments_by_id: dict) -> dict:
    """
    Runs get_verified_answer_for_call for EACH of the 3 calls, then asks
    the AI to synthesize a theme/agreement/disagreement across them.
    """
    per_call_results = {}
    for call_id in segments_by_call.keys():
        per_call_results[call_id] = get_verified_answer_for_call(
            question, call_id, segments_by_call, segments_by_id
        )

    # only pass verified content into the synthesis step - never rejected quotes
    clean_for_synthesis = {}
    for call_id, result in per_call_results.items():
        clean_for_synthesis[call_id] = {
            "answer": result["answer"],
            "verified_quotes": [
                q["display_quote"] for q in result["quotes"] if q["status"] != "rejected"
            ],
        }

    theme = synthesize_theme(question, clean_for_synthesis)
    return {"per_call": per_call_results, "theme": theme}


def ask_free_question(question: str, all_segments, segments_by_id: dict) -> dict:
    """Full pipeline for the free-form 'ask anything' feature."""
    raw = answer_free_question(question, all_segments)
    if raw.get("not_addressed"):
        return {"answer": None, "not_addressed": True, "quotes": []}
    verified_quotes = verify_all_quotes(raw.get("quotes", []), segments_by_id)
    return {
        "answer": raw.get("answer"),
        "not_addressed": False,
        "quotes": verified_quotes,
    }
