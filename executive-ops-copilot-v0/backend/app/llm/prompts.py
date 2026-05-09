def parse_request_prompt(raw_text: str) -> str:
    return (
        "Extract a meeting request as strict JSON matching the ParsedMeetingRequest schema. "
        "Use only schema fields and valid enum values. Classify meeting_type from the request: "
        "customer for customer, renewal, account, escalation, Sev-1, support, or customer success requests; "
        "investor for VC, venture, fundraising, investment, or follow-on investment requests; "
        "candidate for recruiting, interview, final round, or hiring requests; "
        "board for board, board chair, board prep, disclosure, or press inquiry requests; "
        "legal_hr for legal, people, HR, employee relations, or confidential personnel requests; "
        "internal for internal sync, status update, FYI, or no-decision-needed requests. "
        "Set priority urgent for urgent, Sev-1, today, ASAP, disclosure, or press inquiry. "
        "Set async_candidate true when the request is FYI, a status update, or says no decision is needed. "
        "Set escalation_required true for Sev-1, urgent escalation, board, disclosure, press, legal, HR, or confidential requests. "
        f"Raw request: {raw_text}"
    )


def recommendation_prompt(context: dict) -> str:
    return (
        "Return scheduling recommendation JSON only. Deterministic policy and calendar slots "
        f"are provided by the backend: {context}"
    )


def draft_prompt(context: dict) -> str:
    return f"Return an email draft JSON only for this scheduling recommendation: {context}"
