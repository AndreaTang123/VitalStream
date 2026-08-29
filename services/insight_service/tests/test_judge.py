import json
from types import SimpleNamespace

from insight_service.eval.judge import HallucinationJudge, check_grounded

# --- check_grounded: rule-based, no network — hand-built "obviously ok" /
# "obviously wrong" pairs, not just the happy path (week5-layer2-deepening
# -guide.md Step 8).


def test_grounded_true_when_direction_and_number_match():
    text = "Your heart rate is around 95 bpm and trending up."
    snapshot = {"heart_rate_mean": 95.0, "heart_rate_trend": 15.0}
    assert check_grounded(text, snapshot) is True


def test_grounded_false_when_direction_contradicts_snapshot():
    text = "Your heart rate is trending down, nice work staying calm."
    snapshot = {"heart_rate_mean": 95.0, "heart_rate_trend": 15.0}
    assert check_grounded(text, snapshot) is False


def test_grounded_false_when_no_number_cited():
    text = "Keep up the great work with your health journey!"
    snapshot = {"heart_rate_mean": 95.0, "heart_rate_trend": 15.0}
    assert check_grounded(text, snapshot) is False


def test_grounded_true_for_negligible_trend_described_as_flat():
    text = "Your heart rate of 72 bpm has been steady."
    snapshot = {"heart_rate_mean": 72.0, "heart_rate_trend": 0.001}
    assert check_grounded(text, snapshot) is True


def test_grounded_false_for_negligible_trend_described_as_a_real_rise():
    text = "Great news — your heart rate of 72 bpm is climbing steadily."
    snapshot = {"heart_rate_mean": 72.0, "heart_rate_trend": 0.001}
    assert check_grounded(text, snapshot) is False


def test_grounded_lenient_when_text_has_no_direction_language_at_all():
    text = "Great to see your heart rate around 72."
    snapshot = {"heart_rate_mean": 72.0, "heart_rate_trend": 0.001}
    assert check_grounded(text, snapshot) is True


def test_grounded_number_check_applies_to_any_mean_suffixed_key():
    # the rule doesn't care about the metric's name, only the "*_mean" shape
    # — an unrecognized metric with no number cited still fails...
    snapshot = {"some_unrecognized_metric_mean": 42.0}
    assert check_grounded("Keep taking care of yourself!", snapshot) is False
    # ...and passes once a matching number shows up in the text.
    assert check_grounded("Reading of 42 looks fine.", snapshot) is True


def test_grounded_lenient_when_snapshot_has_no_mean_field_at_all():
    # truly nothing to ground against (e.g. describe_snapshot's raw-dict
    # fallback for a shape with no *_mean key) — don't penalize what the
    # rule structurally can't check.
    snapshot = {"window_count": 5}
    assert check_grounded("Keep taking care of yourself!", snapshot) is True


def test_grounded_tolerates_llm_rounding_the_cited_number():
    text = "Average heart rate variability was about 76, holding steady."
    snapshot = {"hrv_rmssd_mean": 75.64310207868984, "hrv_rmssd_trend": 0.1}  # 0.1: within flat tolerance
    assert check_grounded(text, snapshot) is True


# --- check_hallucination: mock the OpenAI call, no network needed ---


def _judge_with_mocked_response(payload: dict | str):
    judge = HallucinationJudge()

    async def fake_create(**kwargs):
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    judge._client.chat.completions.create = fake_create
    return judge


async def test_check_hallucination_parses_true():
    judge = _judge_with_mocked_response({"hallucination": True, "reason": "mentions a diagnosis"})
    flag, reason = await judge.check_hallucination("some text")
    assert flag is True
    assert "diagnosis" in reason


async def test_check_hallucination_parses_false():
    judge = _judge_with_mocked_response({"hallucination": False, "reason": "clean"})
    flag, reason = await judge.check_hallucination("some text")
    assert flag is False


async def test_check_hallucination_degrades_gracefully_on_malformed_json():
    judge = _judge_with_mocked_response("not valid json at all")
    flag, reason = await judge.check_hallucination("some text")
    assert flag is None  # unscored, not a silent "False"
    assert "judge call failed" in reason


async def test_check_hallucination_degrades_gracefully_on_missing_key():
    judge = _judge_with_mocked_response({"reason": "forgot the hallucination key"})
    flag, reason = await judge.check_hallucination("some text")
    assert flag is None


async def test_check_hallucination_degrades_gracefully_when_api_call_raises():
    judge = HallucinationJudge()

    async def raising_create(**kwargs):
        raise TimeoutError("judge timed out")

    judge._client.chat.completions.create = raising_create

    flag, reason = await judge.check_hallucination("some text")
    assert flag is None
    assert "judge call failed" in reason
