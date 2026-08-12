from insight_service.eval.benchmark import score_insight, summarize


def test_score_insight_grounded_and_clean():
    result = score_insight(
        features={"resting_heart_rate": 52.0},
        content="Your resting heart rate looks healthy this week — keep it up!",
    )
    assert result.groundedness_score == 1.0
    assert result.hallucinated is False


def test_score_insight_flags_diagnostic_language():
    result = score_insight(
        features={"resting_heart_rate": 52.0},
        content="This pattern suggests you have a condition that requires a prescription.",
    )
    assert result.hallucinated is True


def test_summarize_averages_across_cases():
    results = [
        score_insight({"resting_heart_rate": 52.0}, "mentions resting heart rate"),
        score_insight({"resting_heart_rate": 52.0}, "says nothing relevant"),
    ]
    report = summarize(results)
    assert report.case_count == 2
    assert report.avg_groundedness_score == 0.5
    assert report.hallucination_rate == 0.0
