# Daily review log

Written by the daily review (`docs/daily-review.md`). Misses are forecast minus actual at 9pm, in °F.

| Date | Clean stretches | 9pm misses by lead time | Verdict | Values changed |
|---|---|---|---|---|
| 2026-11-15 (test run) | `skylights_and_windows` 9pm (11-14) to 7am (skylights closed 7:26am); `closed` 2pm to 9pm (closed since 1:52pm). Closed 8:11am to 1:51pm dropped: furnace ran in hours 9, 12 and 13, leaving 2 clean hours. No data file written (test run); closed-stretch values pulled again agree with `replay.py` and `more_stretches.py` to within 0.05. | None scored: the integration's forecast sensors have no history on 2026-11-15 (installed 2026-11-16). Bedroom at 9pm was 72.14. | HOLD: cut-over not recorded; 0 new clean days since 2026-11-16, need 5 | none |
