from typing import Any

from app.agents.scheduling import SchedulingAgentPlanner, scheduling_agent_definition
from app.llm.schemas import CalendarBlock, ExecutiveRules, ParsedMeetingRequest, TimeWindow


def run_adk_tool_evals(cases: list[dict[str, Any]], rules: ExecutiveRules) -> dict[str, Any]:
    from google.adk.evaluation.trajectory_evaluator import TrajectoryEvaluator

    planner = SchedulingAgentPlanner()
    conversations = []
    results = []

    for case in cases:
        parsed = _parsed_case(case)
        plan = planner.plan(parsed, rules, _calendar_blocks(case, rules))
        expected_tool_use = [
            {"tool_name": tool.name, "tool_input": {}}
            for tool in scheduling_agent_definition.tools
        ]
        actual_tool_use = [
            {"tool_name": call.tool_name, "tool_input": {}}
            for call in plan.tool_calls
        ]
        row = {
            "query": case["raw_text"],
            "response": plan.decision,
            "expected_tool_use": expected_tool_use,
            "actual_tool_use": actual_tool_use,
        }
        conversations.append([row])
        results.append(
            {
                "id": case["id"],
                "decision": plan.decision,
                "tool_calls": [call.tool_name for call in plan.tool_calls],
            }
        )

    score = float(TrajectoryEvaluator.evaluate(conversations))
    return {
        "framework": "google-adk",
        "agent": scheduling_agent_definition.name,
        "metric": "tool_trajectory_avg_score",
        "score": score,
        "passed": bool(score == 1.0),
        "results": results,
    }


def _parsed_case(case: dict[str, Any]) -> ParsedMeetingRequest:
    from app.services.request_parser import fallback_parse

    parsed = fallback_parse(case["raw_text"])
    window = TimeWindow(start="2026-05-11T09:00:00-07:00", end="2026-05-11T17:00:00-07:00")
    intent = parsed.intent.model_copy(update={"preferred_windows": [window]})
    return parsed.model_copy(update={"intent": intent})


def _calendar_blocks(case: dict[str, Any], rules: ExecutiveRules) -> list[CalendarBlock]:
    blocks = [
        CalendarBlock(title=block.label, start=block.start, end=block.end, busy=True)
        for block in rules.protected_blocks
    ]
    calendar_context = case.get("calendar_context")
    if isinstance(calendar_context, dict):
        for block in calendar_context.get("protected_blocks", []):
            blocks.append(CalendarBlock(title=block["label"], start=block["start"], end=block["end"], busy=True))
    return blocks
