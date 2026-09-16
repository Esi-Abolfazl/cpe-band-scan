> History. The page as shipped is described by `README.md` § Open the page; where this ruling and the code disagree, the code is truth.

# Page redesign — human-first one-page app

Replaces `docs/design-system.md` (ui-ux-pro-max rulings). Source of the spec: the 8 notes from the
2026-09-16 review of the running page. No Appllama screens were studied: the account's screens are
Pro-locked and the browser pane denies every external site, so the reference patterns below are the
ones every network utility ships (Speedtest result card, VPN server list with one active row, router
status pages), named from memory and marked as such.

## What was wrong, in one line each

1. Status card prints the router's raw band string and three numbers in one line.
2. ETA covers one side, so "1 min left" is followed by 12 minutes of 5G.
3. The log is rebuilt every poll, so it cannot be read while running.
4. Page capped at 60rem; the table needs horizontal scroll while 40% of the screen is empty.
5. One log for both sides; 4G is unreadable while 5G runs.
6. "Use this band" has no loading state, the other buttons stay live, and the highlighted row is the
   best one, not the one actually locked.
7. The test has no setup: it does not say what it tests, offers no band choice and no duration, and
   its stop button says "Stop the scan".
8. No spacing rhythm: inputs flush against buttons, `?` jammed against titles.

## Layout (desktop ≥ 1100px; stacks to one column below 760px)

```
┌ header: CPE Band Scan · model · firmware · carrier ───────────────────────────── [Refresh] ┐
│                                                                                           │
│ ┌ Your connection now ────────────────────────────────┐ ┌ Band lock ────────────────────┐ │
│ │  4G   B7 (20 MHz)   +B3 (20 MHz)  +B1 (20 MHz)      │ │ Locked to B40, with B1 B3 B7  │ │
│ │       Quality 13 dB · Channel -10.5 dB · Strength -79 dBm                            │ │
│ │  5G   N78 (100 MHz)                                 │ │ [Switch back to automatic]    │ │
│ │       Quality 11 dB · Strength -84 dBm              │ └───────────────────────────────┘ │
│ └──────────────────────────────────────────────────────┘                                   │
│                                                                                           │
│ ┌ Scan ────────────────────────────────────────────────────────────────────────────────┐ │
│ │  ( ) All bands  (•) 4G bands only  ( ) 5G bands only            [ Start the scan ]    │ │
│ │  ── while running ──────────────────────────────────────────────────────────────────  │ │
│ │  4G  ████████░░ 6 of 8 · about 2 min left      5G  waiting             [ Stop ]      │ │
│ │  ┌ 4G log ─────────────── [x] Follow ┐  ┌ 5G log ─────────────── [ ] Follow ┐        │ │
│ │  │ B7 scored Good, lowest 6 dB       │  │ (starts after 4G)                 │        │ │
│ │  │ Measuring B20, 7 of 8 …           │  │                                   │        │ │
│ │  └───────────────────────────────────┘  └───────────────────────────────────┘        │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                           │
│ ┌ 4G results, best first ──────────────────────────────────────────────────────────────┐ │
│ │ #  Band        Rating     Lowest  Typical  Channel  Strength  5G   Carriers   Action  │ │
│ │ 1  B7  [Best]  Good        6       13       -10      -79      yes  B7+B3+B1  [Apply] │ │
│ │ 2  B40 [In use] Good       5       12       -11      -80      yes  B40+B1+B3 In use  │ │
│ │ -  Auto        Fair       -2        9       -13      -82      yes  B3+B7     —       │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│ ┌ 5G results, best first ─ same shape ────────────────────────────────────────────────┐ │
│                                                                                           │
│ ┌ Test a band without scanning ────────────────────────────────────────────────────────┐ │
│ │  Band to test:  (•) What you're on now — B40 +B1 B3 B7 / N78                          │ │
│ │                 ( ) [ B7 ▾ ] from the results                                          │ │
│ │  How long:      ( ) 1 min  (•) 2 min  ( ) 5 min  ( ) 10 min        [ Start the test ] │ │
│ │  ── while running: one log, Follow checkbox, [ Stop ]; then a summary table ──        │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│ ┌ Save this run ───┐ ┌ Saved results ───────────────────────────────────────────────────┐ │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

Width: `#app { max-width: 100rem; padding-inline: clamp(1rem, 3vw, 3rem) }`. Cards sit on a
`grid-template-columns: repeat(auto-fit, minmax(28rem, 1fr))` where two fit; the results tables and
the scan card span the full row. The table drops `overflow-x` for the page width and gets it back
only below 760px.

## Rulings

- **Parsing is the server's job.** `metrics.sample()` gains `carriers`: a list parsed from the band
  string with `(\d+)MHz@(\d+)\((B|N)(\d+)\)` → `{tech: "lte"|"nr", band: "B7", width_mhz: 20,
  earfcn: 3300}`. The page never regexes router strings. Tested in `tests/test_metrics.py`.
- **Every number has a word and a unit, in the same order everywhere:** Quality (SINR, dB) ·
  Channel (RSRQ, dB) · Strength (RSRP, dBm). The technical name lives in the `?` help only.
- **Two sides, always shown.** Progress shows both rows (4G / 5G) with states waiting · running
  (`n of m · about k min left`) · done · skipped. `run_start` carries `plan: {lte: {total, eta_s},
  nr: {...}}` so the 5G ETA is known before 5G starts.
- **Logs are live DOM, not re-rendered.** One `<div class="log">` per side, created once per run,
  new lines appended. `Follow` checkbox per log: on by default for the running side; a wheel/touch
  scroll that leaves the bottom unticks it; ticking scrolls to bottom; a side finishing unticks it;
  the run finishing unticks both.
- **Apply.** Label `Apply`. Click → all Apply buttons disabled, the clicked one shows `Applying…`,
  status is re-read after the write, then rows re-mark. Two distinct marks: `Best` (outline badge,
  top ranked row) and `In use` (filled accent badge + row tint, the row whose set equals the lock's
  primary as read from the router). The in-use row's button is replaced by the text `In use`. The auto
  row is ranked like any band and its Apply puts that side back on automatic (ruling 2026-09-16,
  later; the empty lock is what `In use` matches on that row).
- **Test.** Form first: target (current lock, described from the parsed reading; or a band from the
  last results, which locks it for the test and restores the arriving lock in `finally`) and
  duration (1 / 2 / 5 / 10 min). Button `Start the test`, stop button `Stop the test`. Server:
  `/api/test` accepts optional `lte`/`nr` and `seconds`; `scanner.trace()` gets a `lock=` wrapper.
- **Spacing scale** `--s1: .25rem --s2: .5rem --s3: .75rem --s4: 1rem --s6: 1.5rem --s8: 2rem`, all
  layout via `gap`; no margin stacking. Input and button in a row: `gap: var(--s3)`. Card padding
  `--s6`. Sections `--s8` apart.
- **No `?` buttons anywhere** (ruled during the first review of this design: one shape repeated
  everywhere is noise). Explanations are native hover titles on the word they explain, cued by a
  dotted underline; buttons carry their help as `title`. Column headers are one line each.
- **Best and In use are different things:** Best is an outline pill after the band name; In use is
  the Apply button's exact box, filled with the accent, in the action column.
- **One accent** (`--accent`), spent on: primary button, `In use` badge, progress bar, focus ring.
  Grades keep good/warn/bad but always next to their word. One grey family (the existing cool set).
- **Shape lock:** cards 12px, buttons and inputs 8px, badges pill. Nothing else.
- **Type:** `system-ui`, base 16, `tabular-nums` on every numeric cell and on the ETA.
- **Motion:** none beyond 150ms colour on hover/press; reduced-motion sets 0.
- **Copy:** every label in `copy.py`; new keys listed per task in the plan. One label per intent:
  `Start the scan / Stop the scan`, `Start the test / Stop the test`, `Apply`, `In use`, `Best`,
  `Follow`.
- **States shipped, not defaulted:** no results yet · running · cancelled · router refused the lock
  (inline under the row, not only the banner) · test with no results to pick from (band picker
  disabled with a sentence saying why).

## What the tests pin

`tests/test_page_quality.py` is rewritten: spacing tokens exist and margins on cards are 0; every
numeric `<td>` renders through one `num()` helper; `Apply` buttons carry `disabled` while
`state.applying`; the log element is created once per run (a `data-log` node survives a `render()`);
`copy.py` has no two labels for the same intent. Contrast and the look at 375px / 1440px stay by eye,
with the demo server, before the branch is called done.

## appllama-app-design-skill, applied to a web page

The skill is written for Expo; these are its laws mapped to this stack, and each is a gate the
branch must pass, not a preference.

| Skill law | Here |
|---|---|
| Study before you draw | Blocked (see top); replaced by the named utility patterns. Re-run against Appllama once the account is Pro. |
| Semantic colours, both themes, day one | tokens in `:root` + `prefers-color-scheme: dark`; both checked on the demo server |
| Native controls over rebuilt | radios, `<select>`, `<progress>`, `<input type=checkbox>`; nothing custom |
| Typography is hierarchy; tabular numerals | one type scale (24 / 18 / 16 / 14), `tabular-nums` on every number |
| Spacing rhythm, base 4/8, `gap` over margins | `--s*` scale, cards `margin: 0`, grid/flex `gap` only |
| One accent, locked; one grey family | `--accent` only; cool greys only |
| Shape lock | cards 12, controls 8, badges pill |
| No emoji as iconography | none; badges are words |
| One label per intent | see Copy ruling; test asserts no duplicate labels |
| Full state cycles | states list above; each rendered on the demo server before done |
| Motion frequency gate | poll updates are met hundreds of times a run → no motion; hover only |
| Anti-slop pre-flight (counts) | accent hues 1 · radii from scale only · emoji 0 · gradients 0 · duplicate labels 0 |
| Simulator loop → browser loop | demo server at 375 / 760 / 1440px, light + dark, with a full fake scan running, screenshots read at 100% before calling any screen done |

## Follow-ups

- The tables show the last finished scan. The server keeps one job's events, so after a test and a
  page reload the scan table is gone until the next scan. Retire by having `/api/status` return the
  last scan run alongside the last job, and the page read it on resume.
- The page saves lock profiles, not results: what a person comes back for is the lock, one per
  carrier or place. Terminal scans still land in `runs/` for `show`.
- The password is written to disk only behind the Remember tick (owner-only file, Forget removes it).
  A keychain would be safer; it needs a dependency or per-OS shelling out, so it waits for a request.

## Ruling 2026-09-16, later: no browser dialogs

`window.prompt`, `confirm` and `alert` never appear. Embedded browsers block them and they look
nothing like the page. Rename edits in the row; a destructive action needs a second press whose label
says so (Delete → Delete now). Guarded by `test_the_page_never_opens_a_browser_dialog`.

## Ruling 2026-09-16, later: speed is shown, never ranked

The scan form gains one native checkbox, **Measure speed and ping on each band**, ticked by default,
in the same row as the scope radios; its hover text states the data cost. The results table gains
**Speed** and **Ping** right after the 5G column, only when the run carries them, and one sentence under
the table says how the VPN was handled (`copy.NOTES.probe_*`). The two columns never enter the
ranking: cell load moves hour to hour, and a ranking that flips between scans is worse than one that
ignores speed. The page and the terminal share the column position through `SPEED_KEYS`/`SPEED_AT`,
guarded by `test_the_page_and_the_terminal_put_the_speed_columns_in_the_same_place`.

Follow-up: once saved runs show how stable per-band speed is across hours, decide whether it may break
ties inside a rating. Not before.
