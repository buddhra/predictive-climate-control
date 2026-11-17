# Findings, 2026-11-15: the closed forecast runs cool in fall evenings

## Summary

In fall, the closed-house forecast predicts the bedroom will peak around 1–2pm and then cool 0.6–0.9 °F per hour. In reality the bedroom keeps rising until 7–9pm and then barely cools. The 9pm forecast lands 2–3 °F low. Because the heat budget and the skylight guards read that number, the furnace heats on days that don't need it.

## Evidence

Closed stretches with the furnace and AC off, from hourly statistics:

| Day | Outside high (house sensor) | Closed stretch | Bedroom |
|---|---|---|---|
| Nov 7 | 73 °F | 11:13am–9pm | 66.7 → 71.0 °F, peak 8–9pm |
| Nov 8 | 73 °F | 11:15am–5:47pm | 68.0 → 71.1 °F, then 72.1 °F by 11pm with skylights open |
| Nov 10 | 77 °F | 10:45am–7:05pm | 69.4 → 73.2 °F, peak 7–8pm |
| Nov 11 | 76 °F | 11:23am–5:15pm | 70.3 → 72.5 °F, peak 72.9 °F at 6–8pm |
| Nov 15 | 66 °F | 1:52pm on | 71.2 → 72.1 °F, peak 6–8pm |

Other points:

- Nov 7: the night-before closed forecast said 68.3 °F at 9pm; actual was about 71.0 °F.
- Nov 15, 7pm–8:15pm, closed, outside about 10 °F cooler: the bedroom lost about 0.1 °F per hour. The forecast assumed about 0.9 °F per hour.
- Nov 15: the heat budget heated at noon toward a forecast 67.1 °F at 9pm; the room was 72 °F at 8pm. The furnace ran that morning and around midday (the 54 minutes first reported here came from an unreliable signal; see `findings-2026-11-17.md`), so Nov 15 before 1:17pm is not clean data.

All five days were sunny or hazy and 66–77 °F. There is no cold, cloudy closed day in the data.

## Causes found in the formula

1. **Outdoor coupling is too strong for a closed house.** `alpha_o = 0.05` came from summer overnight cooling, largely with windows open. On a fall evening with a 15 °F gap to the weather entity's temperature, that term alone removes about 0.7 °F per hour.
2. **The mass term has the wrong sign in the evening.** The "mass" is a running average of the air, so while the room is rising it sits below the air and pulls the forecast down, when the real structure is giving heat back.
3. **Solar gain ends too early.** The floor term is centred on 11am and is zero by 5pm. The bedroom gains until 7–9pm.
4. **The weather entity disagrees with the house's outside sensor.** Examples: Nov 10 at 2pm, 82 °F vs 77 °F; Nov 10 at 7pm, 60 °F vs 70 °F; Nov 15 at 8pm, 56.5 °F vs 62 °F. The house sensor looks sheltered and lagged. The forecast can only use the weather entity.

## Replay

`python3 backtest/replay.py` free-runs the closed formula over three stretches using each hour's recorded weather values.

| Stretch | Current formula at end | Actual | Miss |
|---|---|---|---|
| Nov 7, noon → 9pm | 68.6 °F | 71.0 °F | −2.4 °F |
| Nov 10, 11am → 7pm | 73.0 °F | 73.0 °F | 0.0 °F (1.7 °F warm at 3–4pm) |
| Nov 15, 3pm → 7pm | 70.0 °F | 72.1 °F | −2.1 °F |

Total squared error: 30.7 over 21 hourly points.

- Lowering `alpha_o` alone does not fix it: the evening miss shrinks on Nov 15 but grows on Nov 7 and Nov 10.
- Best grid fit: `alpha_o = 0.01`, no mass-to-air term, solar floor 0.5 centred on 2pm. Every hour lands within 0.9 °F; squared error 3.0.

## Status of the candidate

**Hypothesis only. Do not deploy.** It is four numbers fitted to 21 points on three mild, sunny days. Still needed:

- More closed stretches, including a cold cloudy day and a summer day.
- An overnight check. The open scenarios share the 0.05 base, so if closed gets its own lower rate, their venting amounts must rise by the difference to keep the overnight fits that already work.
- A decision on whether a shifted solar floor is the right shape, or whether a real mass state should carry the evening gain.

## Automation issues found the same day (not model problems)

- After 7pm on cool evenings the thermostat sits in heat mode at the night setpoint, and the skylight rule blocks on heat *mode*, so skylights cannot auto-open even when the furnace is idle.
- Skylights stayed open from the evening of Nov 11 to the morning of Nov 15. Nothing closes them while the closed forecast peak is between 67 and 71 °F unless downstairs drops under its floor, and no heat can run while they are open.
- The after-7pm and night heat branches re-send mode and setpoint every 15 minutes.
- Evening, night, and away heat are gated by `binary_sensor.forecast_cool`, whose definition has not been located.
- The 8pm "open the windows" message quotes the skylights + windows forecast even when the skylights are closed.
