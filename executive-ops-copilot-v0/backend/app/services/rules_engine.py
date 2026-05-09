from app.llm.schemas import ExecutiveRules, RuleViolation
from app.services.rules import default_rules as app_default_rules


class RulesEngine:
    def default_rules(self) -> ExecutiveRules:
        return ExecutiveRules.model_validate(app_default_rules().model_dump())

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
