"""CLI tests: worker explains the in-process architecture (DESIGN.md A2).

The ``worker`` subcommand must never be a "not implemented" stub: LeadForge
runs research jobs in-process via FastAPI BackgroundTasks, so the command
explains why no separate worker process exists.
"""

from leadforge.cli import main


def test_worker_explains_in_process_architecture(capsys):
    assert main(["worker"]) == 0
    out = capsys.readouterr().out
    assert "BackgroundTasks" in out
    assert "not implemented" not in out.lower()


def test_worker_mentions_serve_and_run_demo(capsys):
    main(["worker"])
    out = capsys.readouterr().out
    assert "serve" in out
    assert "run-demo" in out
