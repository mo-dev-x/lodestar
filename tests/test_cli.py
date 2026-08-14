from __future__ import annotations

from typer.testing import CliRunner

from lodestar.cli import app
from lodestar.models import EvalRun

runner = CliRunner()


def test_every_command_offline(fixture_dir, tmp_path) -> None:
    source = fixture_dir / "generations_sample.json"
    run_dir = tmp_path / "run"
    common = [
        str(source), "--target-concept", "poutine", "--model-name", "Qwen/test",
        "--sae-checkpoint-id", "sae", "--hook-layer", "12", "--random-feature-id", "9",
    ]
    result = runner.invoke(
        app, ["eval", *common, "--judge", "mock", "--repeats", "2", "-o", str(run_dir)]
    )
    assert result.exit_code == 0, result.output
    assert (run_dir / "run.json").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "reliability.csv").exists()

    optimal = runner.invoke(
        app, ["optimal", str(run_dir), "--objective", "max concept_relevance s.t. coherence >= 1"]
    )
    assert optimal.exit_code == 0, optimal.output

    labels = tmp_path / "labels.csv"
    validate = runner.invoke(app, ["validate", str(run_dir), "--export", str(labels)])
    assert validate.exit_code == 0, validate.output
    assert labels.exists()

    report = runner.invoke(app, ["report", str(run_dir), "-o", str(tmp_path / "report.html"), "--objective", "max concept_relevance s.t. coherence >= 1"])
    assert report.exit_code == 0, report.output

    compare = runner.invoke(app, ["compare", str(run_dir), str(run_dir), "--by", "language"])
    assert compare.exit_code == 0, compare.output


def test_report_command_generates_the_canonical_report(fixture_dir, tmp_path) -> None:
    source = fixture_dir / "generations_sample.json"
    run_dir = tmp_path / "run"
    common = [
        str(source), "--target-concept", "poutine", "--model-name", "Qwen/test",
        "--sae-checkpoint-id", "sae", "--hook-layer", "12", "--random-feature-id", "9",
    ]
    eval_result = runner.invoke(
        app, ["eval", *common, "--judge", "mock", "--repeats", "2", "-o", str(run_dir)]
    )
    assert eval_result.exit_code == 0, eval_result.output

    report_path = tmp_path / "report.html"
    report_result = runner.invoke(app, ["report", str(run_dir), "-o", str(report_path)])
    assert report_result.exit_code == 0, report_result.output
    document = report_path.read_text(encoding="utf-8")
    assert 'data-v="overview"' in document
    assert "<svg" in document

    help_result = runner.invoke(app, ["report", "--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "--style" not in help_result.output


def test_eval_rejects_bare_alias_judge_without_allow_alias(fixture_dir, tmp_path) -> None:
    # THM3.C / THM3.D: eval MUST refuse a moving model alias unless the caller
    # explicitly opts in with --allow-alias.
    source = fixture_dir / "generations_sample.json"
    result = runner.invoke(
        app,
        [
            "eval", str(source), "--target-concept", "poutine", "--model-name", "Qwen/test",
            "--sae-checkpoint-id", "sae", "--hook-layer", "12", "--random-feature-id", "9",
            "--judge", "claude-sonnet-4-5", "-o", str(tmp_path / "run"),
        ],
    )
    assert result.exit_code != 0
    assert "snapshot" in result.output.casefold()
    assert "--allow-alias" in result.output


def test_eval_mock_judge_unaffected_by_snapshot_guard(fixture_dir, tmp_path) -> None:
    # The snapshot guard MUST NOT apply to the offline mock judge.
    source = fixture_dir / "generations_sample.json"
    result = runner.invoke(
        app,
        [
            "eval", str(source), "--target-concept", "poutine", "--model-name", "Qwen/test",
            "--sae-checkpoint-id", "sae", "--hook-layer", "12", "--random-feature-id", "9",
            "--judge", "mock", "--repeats", "1", "-o", str(tmp_path / "run"),
        ],
    )
    assert result.exit_code == 0, result.output


def test_eval_manifest_records_snapshot_and_invariance_version(fixture_dir, tmp_path) -> None:
    # INV-TRACE / F6 (+ F2 provenance half): the manifest MUST record the
    # resolved judge snapshot and the invariance-model version in force.
    source = fixture_dir / "generations_sample.json"
    run_dir = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "eval", str(source), "--target-concept", "poutine", "--model-name", "Qwen/test",
            "--sae-checkpoint-id", "sae", "--hook-layer", "12", "--random-feature-id", "9",
            "--judge", "mock", "--repeats", "1", "-o", str(run_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    manifest = EvalRun.load(run_dir).manifest
    assert manifest.judge_snapshot
    assert manifest.invariance_version


def test_version_and_budget_preflight(fixture_dir, tmp_path) -> None:
    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    assert "Lodestar" in version.output
    estimate = runner.invoke(
        app,
        ["estimate", str(fixture_dir / "generations_sample.json"), "--repeats", "1", "--cache", str(tmp_path / "cache.sqlite")],
    )
    assert estimate.exit_code == 0, estimate.output
    assert "No API calls were made" in estimate.output
