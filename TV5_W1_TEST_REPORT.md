# TV5 Week 1 Test Report

## Summary

The supplied five RED/IR fixtures and five firmware JSON files in the sibling Wokwi project were exercised through `process_ppg`. Eight automated test methods passed, covering clean target rates, fixture structure, noisy input, no-finger/zero channels, short or mismatched arrays, non-finite samples, and invalid sampling rates.

## Results

| Case | Expected | Actual | Result |
|---|---|---|---|
| Clean 60 bpm | Valid; HR 58–62 bpm | 59.6 bpm; valid; err 0 | PASS |
| Clean 75 bpm | Valid; HR 73–77 bpm | 74.8 bpm; valid; err 0 | PASS |
| Clean 90 bpm | Valid; HR 88–92 bpm | 89.8 bpm; valid; err 0 | PASS |
| Noisy 75 bpm | Saved expected validity/error; HR within 3 bpm if valid | 74.5 bpm; valid; err 0 | PASS |
| No Finger | Invalid; err 1 | HR 0.0; SpO2 0.0; invalid; err 1 | PASS |
| RED=0 and IR=0 | Invalid; no crash | Invalid; err 1 | PASS |
| Empty/short/mismatched arrays | Invalid; no crash | Invalid; no crash | PASS |
| NaN sample / fs=0 | Invalid; no crash | Invalid; no crash | PASS |

## Automated run

Command: `python -m unittest discover -s tests -v`

Result: **8 tests passed**.

## Defect addressed

Before tests, malformed short or mismatched buffers could reach the filter and raise an exception. `process_ppg` now rejects sampling rates at or below the filter's Nyquist requirement, unequal/short buffers, non-numeric inputs, and non-finite values with `is_valid=false`, error code 2. The plotting-only dependency is now imported only when the script is run directly, so the processing module and tests do not require matplotlib.

## Limits and handoff

- Fixtures are synthetic and do not represent human measurements or a physical MAX30102.
- Reported SpO2 values come from an unverified approximation. They are demo values only, not validated estimates.
- The Wokwi firmware's `NO_FINGER` generation is static configuration and exports a JSON fixture; it is not a sensor-quality measurement.
- Next integration check: rerun these tests against the exact firmware-generated JSON fixtures and retain the Serial Monitor evidence in the team log.
