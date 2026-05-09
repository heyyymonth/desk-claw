def parse_request_prompt(raw_text: str) -> str:
    return (
        "Extract a meeting request as strict JSON matching the ParsedMeetingRequest schema. "
        f"Raw request: {raw_text}"
    )


def recommendation_prompt(context: dict) -> str:
    return (
        "Return scheduling recommendation JSON only. Deterministic policy and calendar slots "
        f"are provided by the backend: {context}"
    )


def draft_prompt(context: dict) -> str:
    return f"Return an email draft JSON only for this scheduling recommendation: {context}"
