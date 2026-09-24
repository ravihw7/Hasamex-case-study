import re
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class Segment:
    id: str
    call_id: str
    speaker: str
    timestamp: str
    text: str

    def to_dict(self):
        return asdict(self)


# Matches a line that is ONLY a timestamp, e.g. "01:20" or "00:00"
TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}$")


def parse_transcript(file_path: str, call_id: str) -> List[Segment]:
    """
    Reads one transcript file and returns a list of Segment objects.

    How it works (step by step):
    1. Read all lines.
    2. Walk through them looking for a timestamp line (e.g. "01:20").
    3. The line right after it is "Speaker: their words".
    4. We pair the timestamp + speaker + text into one Segment.
    5. We skip the interviewer's questions? -> NO, we keep everything,
       because sometimes useful context is in the question. We just
       tag who is speaking so the app can filter later if needed.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]

    segments = []
    seg_counter = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if TIMESTAMP_RE.match(line):
            timestamp = line
            # the next non-empty line should be "Speaker: text"
            j = i + 1
            while j < len(lines) and lines[j] == "":
                j += 1
            if j < len(lines) and ":" in lines[j]:
                speaker, _, text = lines[j].partition(":")
                speaker = speaker.strip()
                text = text.strip()
                seg_counter += 1
                seg_id = f"{call_id}_{seg_counter:03d}"
                segments.append(
                    Segment(
                        id=seg_id,
                        call_id=call_id,
                        speaker=speaker,
                        timestamp=timestamp,
                        text=text,
                    )
                )
                i = j + 1
                continue
        i += 1
    return segments


def parse_all_transcripts(file_map: dict) -> List[Segment]:
    """
    file_map example:
    {
        "T1": ("Transcript_1_France.txt", "Dr. Jean Martin", "France"),
        "T2": ("Transcript_2_Germany.txt", "Anna Keller", "Germany"),
        "T3": ("Transcript_3_UK.txt", "Expert 3", "UK"),
    }
    Returns one flat list of all segments across all transcripts.
    """
    all_segments = []
    for call_id, (path, _expert_name, _market) in file_map.items():
        all_segments.extend(parse_transcript(path, call_id))
    return all_segments


if __name__ == "__main__":
    # Quick manual test - run: python parser.py
    segs = parse_transcript("../../case_pack/Transcript_1_France.txt", "T1")
    for s in segs[:5]:
        print(s.to_dict())
    print(f"\nTotal segments parsed: {len(segs)}")
