"""UT-GATE-001 — dZ/dt: correct stable/unstable classification.
UT-GATE-002 — d2Z/dt2: cough spike detected, normal breathing not
(verification-validation.md).

Gating is driven directly with synthetic z samples on a fixed 33ms cadence so
the classification is deterministic (no camera/sleep timing jitter)."""

from __future__ import annotations

import math

from xray_assist.gating.respiration import GatingConfig, RespirationGating

DEV, SESS = "edge-001", "sess_test"
DT = 33  # ms per frame (~30fps)


def _gate() -> RespirationGating:
    g = RespirationGating(GatingConfig(), DEV, SESS)
    g.start_tracking()
    return g


def _drive(g: RespirationGating, z_of_t, n: int, t0: int = 0):
    """Feed n frames; returns list of (state, signal, gating) message dicts."""
    out = []
    for i in range(n):
        t = t0 + i * DT
        m = g.update(z_mm=z_of_t(t), valid_pixel_ratio=0.95, now_ms=t).to_message()
        out.append(m)
    return out


# --- UT-GATE-001 : dZ/dt stable / unstable -----------------------------------

def test_steady_signal_reaches_stable_breath_hold():
    g = _gate()
    msgs = _drive(g, lambda t: 880.0, n=80)   # perfectly held surface
    states = {m["state"] for m in msgs}
    assert "stable_breath_hold" in states
    last = msgs[-1]
    assert last["state"] == "stable_breath_hold"
    assert last["gating"]["ready_to_capture"] is True
    assert abs(last["signal"]["dz_dt_mm_s"]) < GatingConfig().stable_dz_dt_threshold_mm_s


def test_moving_signal_is_not_stable():
    # continuous breathing (8mm amp, 4s period) never holds -> dz/dt stays high,
    # never reaches stable_breath_hold within the window
    g = _gate()
    msgs = _drive(g, lambda t: 880.0 + 8.0 * math.sin(2 * math.pi * t / 4000.0), n=60)
    assert all(m["state"] != "stable_breath_hold" for m in msgs)
    # velocity exceeds the stable threshold somewhere in the cycle
    assert max(abs(m["signal"]["dz_dt_mm_s"]) for m in msgs) > \
        GatingConfig().stable_dz_dt_threshold_mm_s


# --- UT-GATE-002 : d2Z/dt2 cough vs normal breathing -------------------------

def test_normal_breathing_does_not_trigger_cough_abort():
    g = _gate()
    msgs = _drive(g, lambda t: 880.0 + 8.0 * math.sin(2 * math.pi * t / 4000.0), n=120)
    assert all(not m["gating"]["abort"] for m in msgs)
    assert all(m["state"] != "abort" for m in msgs)
    # d2Z/dt2 of a normal breath stays under the cough threshold
    post_warmup = msgs[GatingConfig().warmup_frames + 2:]
    assert max(abs(m["signal"]["d2z_dt2_mm_s2"]) for m in post_warmup) < \
        GatingConfig().cough_abort_d2z_threshold_mm_s2


def test_cough_spike_triggers_abort():
    g = _gate()
    # warm up + settle on a steady surface, then a sharp +30mm jerk (a cough)
    def z(t):
        frame = t // DT
        return 880.0 + (30.0 if frame in (40, 41) else 0.0)
    msgs = _drive(g, z, n=60)
    assert any(m["gating"]["abort"] for m in msgs)
    assert g.state == "abort"
    peak = max(abs(m["signal"]["d2z_dt2_mm_s2"]) for m in msgs)
    assert peak > GatingConfig().cough_abort_d2z_threshold_mm_s2


def test_warmup_suppresses_initial_transient():
    # the very first frames (EMA not converged) must not spuriously abort
    g = _gate()
    msgs = _drive(g, lambda t: 880.0, n=GatingConfig().warmup_frames)
    assert all(not m["gating"]["abort"] for m in msgs)
