# Plan — Branch frame count = new segment again, plus a "receipt" line in the job log

Status: approved (plan mode, 2026-10-09); implemented 2026-10-10.

## Background

The latent support feature (commit `50fb43fce`, "Added latent save/decode and
branching to Wan, LongCat, LTX2, MiniMax H3", 2026-10-07) changed two things
at once:

1. *(intended)* the kept prefix of a branch job comes from the sidecar
   `*_latent.pt` file instead of a re-encode of the source video;
2. *(unannounced)* the window planner started reading the Frame Count box as
   the **total final video length** (`_remaining = request − kept − head_new`
   in `wgp.py`, Case A, both variants).

Before that commit, *Continue Video* with a cut was plain classic
continuation: Frame Count = the length of the **new segment**, the source
prefix on top of it. The latent feature's own helpers document the same
parameter that way (`shared/utils/latent_io.py`, `branch_head_window` and
`h3_branch_head_plan`: "the new segment the user asked for (the job's video
length, which excludes the verbatim kept prefix)"). Only the planner read it
as a total. Consequences: the same number in the same box produced a
different final length depending on whether the latent file was selected,
and mid-window cuts made the length hard to predict (the head window is
clamped to the containing window's natural tail, then the remainder is
re-planned from `request − kept − head_new`).

## Goal

Frame Count in a branch job means what it always meant in the classic
continuation:

    final video = kept + Frame Count

and the final length is never a guess: the job log prints the planned result
before the first window generates.

## Changes

### 1. Case A (cut inside a window) — `wgp.py`

Drop the `− kept_frames` term from the remaining-windows calculation, both
the frame-scheduler variant and the default-windows variant:

    _remaining = max(0, request − head_new)

The head window itself is unchanged: its new portion is already clamped to
`min(natural tail, request)` by the helpers (both already implement the
new-segment reading). The comments and the "contributes … new frames" log
lines are rewritten to match.

### 2. Case B (cut at a window end) — `wgp.py` (+ `_prepare_branch_prefix`)

- Remove the rejection "the requested new segment (…) is shorter than the
  carried window's decoded frames": under the new-segment reading it is
  wrong (a small request is fine). If the standard first window cannot hold
  the kept run, the existing fit check takes over and the run uses the
  usual fallback (fresh-encode head, kept region from the sidecar decode or
  the source video).
- Keep the head-window transform (the kept run re-frozen in the window's
  latent budget, overlap = the kept region's decoded length — what keeps the
  i2v anchor and the bit-identical sidecar working). Its new share stays
  the small sliver left in the budget.
- The tail windows are rebuilt to carry the whole request:
  `build_default_window_plan(request − head_new, …)` with the same
  parameters the Case A sub-plan uses (both the frame-scheduler and the
  default-windows variants; the non-sliding single-window variant keeps its
  current geometry).
- The frame scheduler's `predicted_total_frames` includes the kept region
  (as the Case A line already did).

MiniMax H3 needs no helper change: `h3_branch_head_plan` clamps the request
to the cut's committed tail (Case A) and does not use the request at all in
Case B — both already the new-segment reading.

### 3. The receipt line — job log, printed once, before the first window

One line, only for jobs with a kept prefix (continuation / branch /
fallback). The label is always `plan:` (colon, never a dash), lowercase
after the prefix. No square brackets: `[WanGP][H3]` / `[Video Metadata]` /
`[load_*]` are component (speaker) tags; this is a job-flow message, like
the other `From latent:` lines.

    From latent: plan: kept 65 (verbatim) + 80 new (2 window(s)) = 145 frames
    From latent: plan: kept 81 (from the latent file) + 81 new (2 window(s)) = 162 frames
    From video: plan: 210 source + 80 new (1 window(s)) = 290 frames

- `From latent:` when the kept region comes from the sidecar (bit-identical
  prefix latents, or the fresh kept-windows decode); `From video:` when it
  comes from the source video (classic continuation, including the
  latent-file fallback — whose reason is printed on the preceding line).
- Shape is fixed: kept part + new frames (window count) = total.

### 4. Docs and UI

- `docs/SETTINGS.md`, `video_length` row: in a continuation / branch job
  this is the new segment; final = kept + this.
- `docs/SETTINGS.md`, "Latent file support": new paragraph with the rule
  and the receipt-line examples.
- `docs/CHANGELOG.md`, the "From WanGP latent file" entry: add the length
  semantics so the feature's changelog matches the behavior.
- The *From WanGP latent file* checkbox tooltip: one sentence (frame count =
  new segment after the kept part; the job log prints the planned total).

## Not changed

- The kept region: bit-identical handling, sidecar writing, VAE / canvas
  checks, fallback rules.
- i2v / LTX2 / H3 conditioning on the kept part, the i2v anchor, the H3
  anchor-head (GAP-3) and two-phase mechanics.
- Classic continuation lengths (it gains the receipt line only).
- No new setting, no new UI field, no new prompt command.

## Verification

| Job | Box | Before | After |
| --- | --- | --- | --- |
| Wan 2.2 t2v branch, cut 65 of 210 | 81 | 81 frames (16 new) | 146 (65 + 16 + 65) |
| Wan 2.2 t2v branch, cut 81 of 162 | 81 | ~82 (~0 new) | 162 (81 + 81) |
| Wan 2.2 t2v classic continuation, 210 source | 81 | 290 | 290 (regression) |
| Wan 2.2 t2v branch, small request | 10 | 75 | 75 (head clamped; no change in this sub-case) |
| i2v / LTX2 / H3 branch (the earlier test jobs) | — | works | kept region bit-identical; total = kept + box |
| Fallback (latent file not usable) | 81 | classic behavior | unchanged + `From video:` receipt |

Run each: check the receipt line matches the actual final length, and diff
the kept region against the sidecar's own decode (must stay bit-identical).
Static checks: `python -m py_compile wgp.py shared/utils/latent_io.py`.