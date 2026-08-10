from dataclasses import replace

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
    paired_bootstrap_mean_interval,
    qualify_population_signal,
    run_population_task_experiment,
    summarize_population_experiment,
)


def _report():
    order = ("A", "B", "C")
    target = And((Var("A"), Var("B")))
    mechanisms = (
        target,
        Var("A"),
        Var("B"),
        And((Var("A"), Var("C"))),
    )
    catalog = MechanismCatalog(
        order,
        tuple(
            CatalogEntry(
                mechanism,
                semantic_key(mechanism, order)[1],
                canonical_text(mechanism),
            )
            for mechanism in mechanisms
        ),
    )
    evidence = tuple(
        EvidenceCase(
            f"E{value:03b}",
            tuple(bool((value >> shift) & 1) for shift in (2, 1, 0)),
            bool((value & 0b100) and (value & 0b010)),
        )
        for value in range(8)
    )
    public = PublicTask("TASK-STATS", order, evidence, ())
    task = QualificationTask(
        public,
        target,
        semantic_key(target, order)[1],
        catalog,
        (),
    )
    return run_population_task_experiment(
        task,
        (
            MemberCandidate("M0", And((Var("A"), Var("C")))),
            MemberCandidate("M1", Var("B")),
        ),
        synthesis_config=SynthesisConfig(max_rounds=1, max_unique_candidates=64),
    )


def test_paired_bootstrap_is_deterministic() -> None:
    first = paired_bootstrap_mean_interval(
        (0.1, 0.2, 0.3), resamples=500, seed=7
    )
    second = paired_bootstrap_mean_interval(
        (0.1, 0.2, 0.3), resamples=500, seed=7
    )

    assert first == second
    assert first.estimate == 0.2
    assert first.lower <= first.estimate <= first.upper


def test_summary_and_gate_accept_constructed_strong_signal() -> None:
    summary = summarize_population_experiment(
        (_report(),),
        bootstrap_resamples=200,
    )
    decision = qualify_population_signal(summary)

    assert summary.analysis_coverage == 1.0
    assert summary.mean_synthesis_gain == 0.25
    assert summary.synthesis_gain_ci.lower == 0.25
    assert summary.strong_synthesis_event_count == 1
    assert decision.passed is True
    assert decision.reasons == ()


def test_gate_reports_each_failed_boundary() -> None:
    summary = summarize_population_experiment(
        (_report(),),
        bootstrap_resamples=200,
    )
    failed = replace(
        summary,
        analysis_coverage=0.5,
        mean_synthesis_gain=0.0,
        strong_synthesis_event_count=0,
    )
    decision = qualify_population_signal(failed)

    assert decision.passed is False
    assert any("coverage" in reason for reason in decision.reasons)
    assert any("mean synthesis gain" in reason for reason in decision.reasons)
    assert any("strong synthesis events" in reason for reason in decision.reasons)
