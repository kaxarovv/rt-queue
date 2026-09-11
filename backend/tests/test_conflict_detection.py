from app.domains.documents.conflict_detection import detect_signal_conflict


def test_srt_with_planned_pathway_and_no_acute_signals_is_a_conflict():
    result = detect_signal_conflict(
        treatment_modality="SRT",
        clinical_pathway="post_surgery_planned",
        urgency_signals={},
    )
    assert result is not None
    assert result["reason"] == "modality_suggests_urgent_but_pathway_and_signals_suggest_planned"
    assert result["requires_mandatory_doctor_decision"] is True


def test_srt_with_planned_pathway_but_acute_signal_present_is_a_different_conflict():
    result = detect_signal_conflict(
        treatment_modality="SRT",
        clinical_pathway="post_surgery_planned",
        urgency_signals={"pain_or_bleeding_mentioned": True},
    )
    assert result is not None
    assert result["reason"] == "modality_radiosurgery_but_acute_signal_present_despite_planned_pathway"


def test_non_radiosurgery_modality_never_conflicts():
    result = detect_signal_conflict(
        treatment_modality="EBRT",
        clinical_pathway="post_surgery_planned",
        urgency_signals={},
    )
    assert result is None


def test_acute_pathway_does_not_conflict():
    result = detect_signal_conflict(
        treatment_modality="SRS",
        clinical_pathway="acute_symptomatic",
        urgency_signals={},
    )
    assert result is None


def test_unknown_pathway_does_not_conflict():
    result = detect_signal_conflict(
        treatment_modality="SRT",
        clinical_pathway=None,
        urgency_signals={},
    )
    assert result is None
