# Operator console (AERA PACS)

[← back to README](../README.md) · [한국어](operator-console.ko.md)

[`index.html`](../index.html) — a **single-file** frontend. Zero frameworks, build steps, or npm dependencies. Worklist, live console, and settings are all built from HTML + CSS + Vanilla JS (ES2020) + Canvas 2D. The gateway serves this file at `/`.

## Screen layout

```
Header (language toggle · camera status · clock · ⚙ settings)
├─ VIEW A  Worklist    — today's studies, sort/search/filter
├─ VIEW B  Study console — waveform · signal · LUT · recommendation · session controls · event stream · audit
└─ VIEW C  Settings     — server connection · camera · calibration · device info
```

## Live wiring (simulation → real backend)

The console's data layer consumes the **real backend**, not an in-browser simulation:

- **WebSocket** `/ws/v1/events` → handlers `onDepth` · `onResp` · `onRec` · `onSysErr` adapt each message into render calls
- **REST**: session start / cue·abort·manual·cough actions / approve / audit query & verify
- Backend state names and gating map 1:1 with the [gating doc](depth-and-gating.md), so on-screen transitions equal backend transitions

### Surface depth vs thickness

In live data `z` is the **absolute surface distance** (camera→chest, ≈800 mm) while thickness is `estimated_thickness_mm` (≈240 mm) — different values. Therefore:

- the waveform Y-axis auto-centres on the **signal's own midpoint** (a fixed baseline would push the trace off-screen)
- the signal panel shows surface depth (z) and estimated thickness separately
- LUT highlighting matches on **thickness**

### Recommendation de-dupe

While a hold is stable the backend re-emits a recommendation every frame with an incrementing `recommendation_id`. The console re-renders/logs only when the `(manual | kVp/mAs)` signature changes (avoiding spam), while `lastRecommendationId` always tracks the latest so the approval target stays valid.

## Waveform rendering (Canvas 2D)

A 260-sample ring buffer (`waveBuf`) is drawn as coloured segments by state (stable=green, unstable/timeout=amber, abort=red). Stable spans get a background highlight; the last point is a state-coloured dot. The canvas is scaled by `devicePixelRatio` for crisp rendering on HiDPI.

## Internationalisation (i18n)

- Korean/English dictionaries (`I18N`) + `data-i18n` / `data-i18n-html` / `data-i18n-ph` / `data-i18n-title` attributes
- language choice persisted to `localStorage`, restored on revisit
- functional strings (e.g. `sub_stable: d => …${d}ms…`) translate dynamic text too

## Settings page

- **Server connection**: edit and save the gateway origin (host:port, to `localStorage`) → live status/services/device info via `/health` · `/state`. Re-pointing at a different edge box immediately reconnects the WS/REST sources.
- **Camera**: `/devices` enumeration → per-serial selection & connection (see [Camera abstraction](camera-abstraction.md))
- **Calibration / device info**: empty-bed calibration, real backend status (connection · calibration · session)

The **Close** button (top-right ✕) returns to the previous view.

## Keyboard shortcuts

Active only in the study view (except Esc). Suppressed while an input field is focused:

| Key | Action |
|---|---|
| `S` | start / end session |
| `B` | breath-hold cue |
| `C` | trigger cough |
| `A` | approve recommendation |
| `Esc` | back to worklist (or close settings if open) |

## Local preview

Run `python3 smart-xray-assist/scripts/run_mvp.py` to bring up the backend + console together on `http://localhost:8080/`.

Related: [API & realtime](api-and-realtime.md) · [Exposure & safety](exposure-and-safety.md)
