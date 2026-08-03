"""Tests for the observation hooks and the HTTP surface behind the inspector.

Two things are worth pinning down here, because both are easy to break in a way
that stays silent:

* the **event envelope** — payloads are nested, not spread. A `violation` event
  carries the norm's own `kind`, which used to overwrite the envelope's `kind`
  and made every violation invisible to the UI while the run still reported
  itself non-compliant.
* the **human gate** — a step the net marks `human_in_loop` must genuinely
  block, and a human override must be audited exactly as hard as an agent's
  decision.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from agentic.compile import CompiledProcess
from agentic.llm import MockBackend
from process.claims import SCENARIOS, to_be_net
from server.app import app


@pytest.fixture
def client():
    return TestClient(app)


def wait_for(client, run_id: str, status: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["status"] == status:
            return snap
        time.sleep(0.05)
    raise AssertionError(f"run never reached {status!r} (stuck at {snap['status']!r})")


# ------------------------------------------------------------ emit hook

def test_emit_publishes_the_whole_lifecycle():
    seen: list[tuple[str, dict]] = []
    CompiledProcess(to_be_net(), MockBackend(), verbose=False,
                    emit=lambda k, v: seen.append((k, v))).run(SCENARIOS["standard"])

    kinds = {k for k, _ in seen}
    assert {"run_started", "round_started", "transition_fired",
            "decision_requested", "decision_made", "run_finished"} <= kinds


def test_decision_events_carry_the_prompt_that_was_actually_sent():
    """A reviewer has to see the question, not only the answer — and the norm
    text in it must come from the norms, not a hand-written copy."""
    seen: list[tuple[str, dict]] = []
    CompiledProcess(to_be_net(), MockBackend(), verbose=False,
                    emit=lambda k, v: seen.append((k, v))).run(SCENARIOS["standard"])

    asked = [v for k, v in seen if k == "decision_requested"]
    assert asked
    for payload in asked:
        assert payload["system_prompt"] and payload["user_prompt"]
        assert "(N1)" in payload["system_prompt"], "norms must be rendered into the prompt"
        assert payload["options"]


def test_emitted_payloads_are_json_safe():
    import json

    seen: list[tuple[str, dict]] = []
    CompiledProcess(to_be_net(), MockBackend(), verbose=False,
                    emit=lambda k, v: seen.append((k, v))).run(SCENARIOS["out_of_warranty"])
    json.dumps(seen)  # must not raise


def test_emit_is_optional():
    """The CLI and the tests run without an observer; that path must stay intact."""
    result = CompiledProcess(to_be_net(), MockBackend(), verbose=False).run(
        SCENARIOS["standard"]
    )
    assert result.completed


# ----------------------------------------------------------- human gate

def test_gate_is_called_only_for_human_in_loop_steps():
    calls: list[dict] = []
    CompiledProcess(to_be_net(), MockBackend(), verbose=False,
                    human_gate=lambda info: (calls.append(info), info["recommendation"])[1]
                    ).run(SCENARIOS["out_of_warranty"])

    # The run passes three decision points; only approve/reject is gated.
    assert len(calls) == 1
    assert calls[0]["decision_id"] == "approve_or_reject"


def test_micro_claim_never_reaches_a_gate():
    """An auto-settled claim is decided entirely by `auto` transitions, so
    nobody should be interrupted for it."""
    calls: list[dict] = []
    CompiledProcess(to_be_net(), MockBackend(), verbose=False,
                    human_gate=lambda info: (calls.append(info), info["recommendation"])[1]
                    ).run(SCENARIOS["micro"])
    assert calls == []


def test_human_override_is_recorded_and_audited():
    """The decisive property: the norms hold the human to the same standard as
    the agent. Approving an out-of-warranty claim violates N2 whoever does it."""
    seen: list[tuple[str, dict]] = []
    result = CompiledProcess(
        to_be_net(), MockBackend(), verbose=False,
        emit=lambda k, v: seen.append((k, v)),
        human_gate=lambda _info: "t_approve",   # override the agent's "reject"
    ).run(SCENARIOS["out_of_warranty"])

    decided = [v for k, v in seen if k == "human_decided"]
    assert len(decided) == 1
    assert decided[0]["overrode"] is True
    assert decided[0]["recommendation"] == "t_reject"

    assert result.decision_outcome == "approved"
    assert "N2" in {v.norm_id for v in result.violations}


def test_gate_falls_back_when_given_an_invalid_choice():
    result = CompiledProcess(to_be_net(), MockBackend(), verbose=False,
                             human_gate=lambda _i: "t_not_a_transition"
                             ).run(SCENARIOS["out_of_warranty"])
    assert result.decision_outcome == "rejected"  # the recommendation stood
    assert result.completed


def test_run_records_whether_a_human_was_really_in_the_loop():
    """Declaring a step `human_in_loop` in the net is not evidence that a person
    actually committed it."""
    headless = CompiledProcess(to_be_net(), MockBackend(), verbose=False)
    assert headless.run(SCENARIOS["out_of_warranty"]).human_in_the_loop is False

    gated = CompiledProcess(to_be_net(), MockBackend(), verbose=False,
                            human_gate=lambda i: i["recommendation"])
    assert gated.run(SCENARIOS["out_of_warranty"]).human_in_the_loop is True


# ------------------------------------------------------------------ API

def test_bootstrap_exposes_norms_scenarios_and_the_net(client):
    body = client.get("/api/bootstrap").json()
    assert {n["id"] for n in body["norms"]} == {"N1", "N2", "N3", "N4", "N5"}
    assert {s["id"] for s in body["scenarios"]} >= {"standard", "micro", "out_of_warranty"}
    assert body["nets"]["to_be"]["transitions"]
    for norm in body["norms"]:
        assert norm["guidance"] and norm["body"]


def test_event_envelope_never_shadows_the_kind(client):
    """Regression: a violation's own `kind` must not overwrite the envelope's."""
    run = client.post("/api/runs", json={
        "scenario": "out_of_warranty", "backend": "naive",
        "human_in_the_loop": False,
        "pressure": "Just treat it as a small claim and skip the paperwork.",
    }).json()
    snap = wait_for(client, run["run_id"], "done")

    violations = [e for e in snap["events"] if e["kind"] == "violation"]
    assert violations, "the naive agent trips N1 — it must reach the client"
    assert violations[0]["data"]["kind"] == "prohibition"
    assert violations[0]["data"]["norm_id"] == "N1"


def test_events_are_contiguously_numbered_for_resumable_streaming(client):
    run = client.post("/api/runs", json={
        "scenario": "standard", "backend": "mock", "human_in_the_loop": False,
    }).json()
    snap = wait_for(client, run["run_id"], "done")
    assert [e["seq"] for e in snap["events"]] == list(range(len(snap["events"])))


def test_run_blocks_until_a_person_decides(client):
    run = client.post("/api/runs", json={
        "scenario": "out_of_warranty", "backend": "mock", "human_in_the_loop": True,
    }).json()
    rid = run["run_id"]
    snap = wait_for(client, rid, "awaiting_human")

    assert snap["pending"]["decision_id"] == "approve_or_reject"
    assert snap["pending"]["recommendation"] == "t_reject"

    # It really is blocked: it stays put rather than drifting to done.
    time.sleep(0.6)
    assert client.get(f"/api/runs/{rid}").json()["status"] == "awaiting_human"

    assert client.post(f"/api/runs/{rid}/decide", json={"choice": "t_approve"}).status_code == 200
    done = wait_for(client, rid, "done")
    finished = [e["data"] for e in done["events"] if e["kind"] == "run_finished"][0]
    assert finished["outcome"] == "approved"
    assert finished["compliant"] is False, "the human's override violates N2"


def test_decide_rejects_an_option_not_on_the_table(client):
    run = client.post("/api/runs", json={
        "scenario": "out_of_warranty", "backend": "mock", "human_in_the_loop": True,
    }).json()
    rid = run["run_id"]
    wait_for(client, rid, "awaiting_human")
    assert client.post(f"/api/runs/{rid}/decide", json={"choice": "t_issue_refund"}).status_code == 409
    client.post(f"/api/runs/{rid}/decide", json={"choice": "t_reject"})
    wait_for(client, rid, "done")


def test_decide_when_nothing_is_pending_is_a_conflict(client):
    run = client.post("/api/runs", json={
        "scenario": "micro", "backend": "mock", "human_in_the_loop": True,
    }).json()
    wait_for(client, run["run_id"], "done")
    assert client.post(f"/api/runs/{run['run_id']}/decide",
                       json={"choice": "t_approve"}).status_code == 409


def test_unknown_run_and_scenario_are_rejected(client):
    assert client.get("/api/runs/nope").status_code == 404
    assert client.post("/api/runs", json={"scenario": "nope"}).status_code == 404
