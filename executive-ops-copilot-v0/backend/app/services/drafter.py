from app.models import Decision, DraftResponse, MeetingRequest, ModelStatus, Recommendation, Tone


def draft_response(meeting_request: MeetingRequest, recommendation: Recommendation) -> DraftResponse:
    intent = meeting_request.intent
    subject = f"Re: {intent.title}"

    if recommendation.decision == Decision.schedule and recommendation.proposed_slots:
        slot = recommendation.proposed_slots[0]
        body = (
            f"Thanks for reaching out. We can offer {slot.start.strftime('%A, %B %d at %I:%M %p')} "
            f"for {intent.duration_minutes} minutes. Please confirm whether that works on your side."
        )
        tone = Tone.warm
    elif recommendation.decision == Decision.clarify:
        missing = ", ".join(intent.missing_fields)
        body = f"Thanks for the note. Could you share a bit more detail on {missing} so we can route this correctly?"
        tone = Tone.concise
    elif recommendation.decision == Decision.decline:
        body = "Thanks for reaching out. We are not able to prioritize this meeting right now, but appreciate the context."
        tone = Tone.firm
    else:
        body = "Thanks for reaching out. We need to review availability and priority before proposing a time."
        tone = Tone.concise

    return DraftResponse(subject=subject, body=body, tone=tone, model_status=ModelStatus.not_configured)
