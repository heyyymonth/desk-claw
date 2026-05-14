import json
from pathlib import Path

from app.services.parser import parse_meeting_request
from app.services.recommender import build_recommendation
from app.services.rules import default_rules


def run() -> list[dict[str, object]]:
    cases_path = Path(__file__).resolve().parents[3] / "evals" / "cases" / "basic_requests.json"
    cases = json.loads(cases_path.read_text())
    results = []
    for case in cases:
        parsed = parse_meeting_request(case["raw_text"])
        recommendation = build_recommendation(parsed, default_rules())
        results.append({
            "id": case["id"],
            "parsed_title": parsed.intent.title,
            "priority": parsed.intent.priority.value,
            "duration_minutes": parsed.intent.duration_minutes,
            "decision": recommendation.decision.value,
        })
    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
