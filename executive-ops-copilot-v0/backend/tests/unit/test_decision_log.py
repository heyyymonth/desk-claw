from app.db.session import Database
from app.llm.schemas import DecisionFeedback
from app.services.decision_log import DecisionLogService


def test_decision_feedback_logging_round_trip(tmp_path):
    service = DecisionLogService(Database(f"sqlite:///{tmp_path / 'decisions.db'}"))
    feedback = DecisionFeedback(
        action="accept",
        recommendation_id="rec-1",
        notes="Looks good",
    )

    logged = service.log(feedback)
    entries = service.list()

    assert logged.id
    assert len(entries) == 1
    assert entries[0].action == "accept"
    assert entries[0].notes == "Looks good"
