from datetime import datetime
from zoneinfo import ZoneInfo

from app.llm.schemas import ExecutiveRules, ProtectedBlock, RuleViolation, WorkingHours


class RulesEngine:
    def default_rules(self) -> ExecutiveRules:
        tz = ZoneInfo("America/Los_Angeles")
        return ExecutiveRules(
            executive_name="Executive",
            timezone="America/Los_Angeles",
            working_hours=WorkingHours(start="09:00", end="17:00"),
            protected_blocks=[
                ProtectedBlock(
                    label="Focus block",
                    start=datetime(2026, 5, 11, 9, 0, tzinfo=tz),
                    end=datetime(2026, 5, 11, 11, 0, tzinfo=tz),
                )
            ],
            preferences=[
                "Prefer customer and investor requests before 2 PM.",
                "Ask for clarification when requester, purpose, or duration is missing.",
                "Do not perform external calendar or email actions automatically.",
            ],
        )

    def validate(self, rules: ExecutiveRules) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        for block in rules.protected_blocks:
            if block.start.timetz().replace(tzinfo=None) < rules.working_hours.start or block.end.timetz().replace(tzinfo=None) > rules.working_hours.end:
                violations.append(
                    RuleViolation(
                        code="protected_block_outside_working_hours",
                        message=f"Protected block '{block.label}' is outside working hours.",
                    )
                )
        return violations
