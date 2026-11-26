# TV5 Week 1 Test Plan

## Scope

Verify the RED/IR fixture shape and the TV1 processing function using the five supplied simulated cases, plus invalid-input cases. These are software tests on synthetic data; they do not validate a MAX30102 sensor or clinical measurement accuracy.

## Test cases

| ID | Input | Expected result |
|---|---|---|
| TC01 | Clean 60 bpm, 100 Hz, 400 samples/channel | Valid; HR within 2 bpm of target |
| TC02 | Clean 75 bpm, 100 Hz, 400 samples/channel | Valid; HR within 2 bpm of target |
| TC03 | Clean 90 bpm, 100 Hz, 400 samples/channel | Valid; HR within 2 bpm of target |
| TC04 | Noisy 75 bpm fixture | Match saved validity/error code; if valid, HR within 3 bpm |
| TC05 | No Finger fixture | Invalid; error code 1; HR/SpO2 sentinel values are 0 |
| TC06 | RED and IR both zero | Invalid; error code 1 (no finger / insufficient DC) |
| TC07 | Empty, short, or unequal channel arrays | Invalid; no exception |
| TC08 | NaN sample or invalid sampling rate | Invalid; no exception |
| TC09 | Fixture structure | Five cases, fs=100, 400 finite values in each RED/IR channel |
| TC10 | Wokwi firmware JSON files in the sibling project | Five files parse; sample counts and HR/no-finger expectations pass |

## Run

From this member repository folder:

```powershell
python -m pip install -r tests/requirements-test.txt
python -m unittest discover -s tests -v
```

`matplotlib` is not needed for tests. It is only needed for the optional plotting/demo section when running `signal_processing/ppg_algorithm.py` directly.

## SpO2 interpretation

The processing function currently applies a polynomial approximation and reports its output in a field named `spo2`. No sensor-specific calibration or synchronized reference validation is supplied here. Treat these values as simulated/demo output only; do not claim SpO2 accuracy or medical validity. For no-signal cases, the function returns `is_valid=false` and zero sentinels; downstream code must honor `is_valid` and never display those zeros as measurements.
