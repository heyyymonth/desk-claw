from app.llm.schemas import CalendarAnalysis, ParsedMeetingRequest, Risk


class RiskClassifier:
    def classify(self, parsed_request: ParsedMeetingRequest, analysis: CalendarAnalysis) -> list[Risk]:
        risks: list[Risk] = []
        if parsed_request.intent.missing_fields:
            risks.append(
                Risk(
                    level="medium",
                    message="Request is missing: " + ", ".join(parsed_request.intent.missing_fields),
                )
            )
        if analysis.conflicts and not analysis.open_slots:
            risks.append(Risk(level="high", message="Preferred windows conflict with busy calendar blocks."))
        elif analysis.conflicts:
            risks.append(Risk(level="medium", message="Some preferred time overlaps existing calendar blocks."))
        return risks
