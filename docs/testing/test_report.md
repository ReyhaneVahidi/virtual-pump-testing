# Test execution report

**Document ID:** TER-VP-001  
**Execution date (UTC):** 2026-11-22 10:20:14 UTC  
**Commit:** `f76c886`  
**Platform:** `Windows-10-10.0.26200-SP0`  
**Python:** `3.11.0`  
**Command:** `python tools/generate_test_report.py` (executes `python -m pytest -q --junitxml=<temporary file>`)  
**pytest exit code:** `0`

## Overall execution outcome

**97 passed, 0 failed, 0 skipped** (total **97** pytest executions).

- Requirement cases: **10 Pass**, **0 Fail**, **0 Incomplete**, **0 Not Run** out of 10.
- Unique pytest executions mapped to the selected cases: **50** of 97 in the full suite.
- This is **observed software test evidence**, not measurement from a physical pump.

## Test case execution results

| Test case | Requirement | Actual observed result | Status |
| --- | --- | --- | --- |
| [TC-001](test_cases.md) — Accept valid speed setpoints | [REQ-001](requirements.md) | 5/5 linked pytest executions passed | **Pass** |
| [TC-002](test_cases.md) — Reject invalid speed without modifying setpoint | [REQ-001](requirements.md) | 8/8 linked pytest executions passed | **Pass** |
| [TC-003](test_cases.md) — Start only with a configured speed | [REQ-002](requirements.md) | 4/4 linked pytest executions passed | **Pass** |
| [TC-004](test_cases.md) — Stop command and idempotent stop | [REQ-003](requirements.md) | 3/3 linked pytest executions passed | **Pass** |
| [TC-005](test_cases.md) — Sensor disconnection forces safe stop and blocks start | [REQ-004](requirements.md) | 4/4 linked pytest executions passed | **Pass** |
| [TC-006](test_cases.md) — Sensor recovery requires explicit restart | [REQ-004](requirements.md) | 3/3 linked pytest executions passed | **Pass** |
| [TC-007](test_cases.md) — Motor fault stop, latching, and reset interlocks | [REQ-005](requirements.md) | 6/6 linked pytest executions passed | **Pass** |
| [TC-008](test_cases.md) — RPM feedback thresholds and latched fault handling | [REQ-006](requirements.md) | 12/12 linked pytest executions passed | **Pass** |
| [TC-009](test_cases.md) — Traceable UTC event history for feedback faults | [REQ-007](requirements.md) | 3/3 linked pytest executions passed | **Pass** |
| [TC-010](test_cases.md) — API reports current operating and fault status | [REQ-008](requirements.md) | 4/4 linked pytest executions passed | **Pass** |

## Evidence and interpretation

- Actual results above are read from the JUnit XML produced by **this run**.
- `Pass`: all existing mapped test instances passed; `Fail`: at least one failed; `Incomplete`: test skipped or a selector did not match; `Not Run`: no mapped tests executed.
- The underlying pytest functions contain the detailed assertions for pump state, HTTP responses, fault codes, and event fields. Passing status means those assertions were satisfied, not that physical effects were observed.
- Evidence is specific to the recorded source revision and environment. Regenerate after code or dependency changes; check CI separately.

## How to reproduce

```powershell
python -m pip install -r requirements.txt
python tools/generate_test_report.py
```

The command updates this report and the RTM. Commit updated reports only after verifying they reflect the intended revision and run.
