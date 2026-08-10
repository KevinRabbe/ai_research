from plural_cognition.boolean_world import (
    And,
    CatalogEntry,
    EvidenceCase,
    MechanismCatalog,
    PublicTask,
    Var,
    canonical_text,
    semantic_key,
)
from plural_cognition.boolean_world.qualification import QualificationTask
from plural_cognition.population import (
    MemberCandidate,
    SynthesisConfig,
    run_population_task_experiment,
)


def _qualification() -> QualificationTask:
    order = ("A", "B", "C")
    target = And((Var("A"), Var("B")))
    mechanisms = (
        target,
        Var("A"),
        Var("B"),
        And((Var("A"), Var("C"))),
    )
    entries = tuple(
        CatalogEntry(
            mechanism,
            semantic_key(mechanism, order)[1],
            canonical_text(mechanism),
        )
        for mechanism in mechanisms
    )
    catalog = MechanismCatalog(order, entries)
    evidence = tuple(
        EvidenceCase(
            f"E{value:03b}",
            tuple(bool((value >> shift) & 1) for shift in (2, 1, 0)),
            bool((value & 0b100) and (value & 0b010)),
        )
        for value in range(8)
    )
    public = PublicTask(
        "TASK-POPULATION-EXPERIMENT",
        order,
        evidence,
        (),
    )
    return QualificationTask(
        public,
        target,
        semantic_key(target, order)[1],
        catalog,
        (),
    )


def test_end_to_end_report_detects_strong_synthesis_event() -> None:
    report = run_population_task_experiment(
        _qualification(),
        (
            MemberCandidate("M0", And((Var("A"), Var("C")))),
            MemberCandidate("M1", Var("B")),
        ),
        synthesis_config=SynthesisConfig(
            max_rounds=1,
            max_unique_candidates=64,
        ),
    )

    assert report.analysis_available is True
    assert report.best_individual_semantic_accuracy == 0.75
    assert report.full_synthesis_exact is True
    assert report.synthesis_gain == 0.25
    assert report.novel_semantic_composition is True
    assert report.multi_source_provenance is True
    assert set(report.score_necessary_members) == {"M0", "M1"}
    assert report.strong_synthesis_event is True
    assert report.graph is not None
    assert report.knowledge is not None
    assert report.ablations is not None


def test_invalid_member_output_is_recorded_without_fabricating_packet() -> None:
    report = run_population_task_experiment(
        _qualification(),
        (
            MemberCandidate("M0", Var("A")),
            MemberCandidate("M1", None, error="malformed symbolic answer"),
        ),
    )

    assert report.analysis_available is False
    assert report.coalition is None
    assert report.unavailable_reason == "invalid member outputs: M1"
    invalid = next(item for item in report.individuals if item.member_id == "M1")
    assert invalid.valid is False
    assert invalid.packet_sha256 is None


def test_partial_analysis_can_be_enabled_explicitly() -> None:
    report = run_population_task_experiment(
        _qualification(),
        (
            MemberCandidate("M0", Var("A")),
            MemberCandidate("M1", None, error="malformed symbolic answer"),
        ),
        require_all_members_valid=False,
    )

    assert report.analysis_available is True
    assert report.coalition is not None
    assert report.coalition.members == ("M0",)
