# Daily review log

Written by the daily review (`docs/daily-review.md`). Misses are forecast minus actual at 9pm, in °F.

| Date | Clean stretches | 9pm misses by lead time | Verdict | Values changed |
|---|---|---|---|---|
| 2026-11-15 (test run) | `skylights_and_windows` 9pm (11-14) to 7am (skylights closed 7:26am); `closed` 2pm to 9pm (closed since 1:52pm). Closed 8:11am to 1:51pm dropped: furnace ran in hours 9, 12 and 13, leaving 2 clean hours. No data file written (test run); closed-stretch values pulled again agree with `replay.py` and `more_stretches.py` to within 0.05. | None scored: the integration's forecast sensors have no history on 2026-11-15 (installed 2026-11-16). Bedroom at 9pm was 72.14. | HOLD: cut-over not recorded; 0 new clean days since 2026-11-16, need 5 | none |
| 2026-11-16 | `closed` 11am to 7pm (bedroom window closed 9:27am, opened 7:11pm; skylights closed and fan off all day; AC off). Hours 9 and 10 dropped: furnace heating 9:51-10:07am. 9pm (11-15) to 9:27am matched no scenario (bedroom window open from 10:04pm with skylights closed), as did 7:11pm to 9pm. Written to `backtest/data/2026-11-16.json`. | None scored: no clean stretch reached 9pm (bedroom window opened 7:11pm with skylights closed). Bedroom at 9pm was 70.52. | HOLD: cut-over not recorded; 0 new clean days since 2026-11-16, need 5 | none |
