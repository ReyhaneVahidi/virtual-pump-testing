# Requirements-based test specifications

**Document ID:** TCS-VP-001  
**Test level:** Unit and API integration, software-only  
**Execution evidence:** [test_report.md](test_report.md)  
**Test mappings:** [test_mapping.json](test_mapping.json)

These ten structured cases map already implemented pytest tests to requirements. **Expected results** are specified here; the **actual result and Pass/Fail** are recorded by executing `python tools/generate_test_report.py` and are not assumed in advance.

## TC-001 — Accept valid speed setpoints

| Field | Specification |
| --- | --- |
| Requirement | REQ-001 |
| Preconditions | New pump, stopped, sensor connected, no faults |
| Steps | 1. Set speed to `1 RPM`. 2. Repeat with `150 RPM` through the API. 3. Set speed to `300 RPM`. 4. Read the resulting setpoint. |
| Expected result | Values in the inclusive allowed range are accepted; returned and stored setpoints equal the requested values; API returns HTTP 200. |
| Actual result | See TC-001 in [test report](test_report.md). |
| Status | Recorded at execution (Pass/Fail/Not Run). |

## TC-002 — Reject invalid speeds without changing state

| Field | Specification |
| --- | --- |
| Requirement | REQ-001 |
| Preconditions | New pump; for the preservation check, set a valid speed of `120 RPM` first |
| Steps | 1. Submit `0`, `301`, and negative RPM through the relevant unit/API interfaces. 2. Submit a noninteger value (`fast`) through the API. 3. Verify stored speed after rejection. |
| Expected result | Out-of-range integer values are rejected (`ValueError` in core, HTTP 400 in API). Noninteger route gives HTTP 422. A rejected command does not overwrite a previous valid setting. |
| Actual result | See TC-002 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-003 — Start only with a configured speed

| Field | Specification |
| --- | --- |
| Requirement | REQ-002 |
| Preconditions | New pump, no faults, stopped |
| Steps | 1. Request start with no configured speed. 2. Verify rejection and stopped state. 3. Set a valid speed. 4. Request start again. |
| Expected result | First start is rejected (core `RuntimeError`, API HTTP 409); pump remains stopped. After valid configuration, start succeeds and `running=True`. |
| Actual result | See TC-003 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-004 — Stop behavior is repeatable

| Field | Specification |
| --- | --- |
| Requirement | REQ-003 |
| Preconditions | Running pump with a valid speed; additionally test an already stopped pump |
| Steps | 1. Issue stop. 2. Check operating state. 3. Issue stop again. |
| Expected result | Both stop operations complete successfully and `running=False`; the API returns HTTP 200. |
| Actual result | See TC-004 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-005 — Critical simulated sensor disconnection

| Field | Specification |
| --- | --- |
| Requirement | REQ-004 |
| Preconditions | Pump running at `120 RPM` or `150 RPM` with sensor connected |
| Steps | 1. Inject sensor disconnection. 2. Inspect sensor, measured RPM, and running state. 3. Attempt to start while disconnected. |
| Expected result | `sensor_connected=False`, `running=False`, `measured_rpm=None`; restart is rejected (HTTP 409 in API). |
| Actual result | See TC-005 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-006 — Controlled sensor reconnection

| Field | Specification |
| --- | --- |
| Requirement | REQ-004 |
| Preconditions | Pump has a valid speed but is stopped following sensor disconnection |
| Steps | 1. Reconnect the sensor. 2. Inspect running state. 3. Send explicit start command. |
| Expected result | Sensor reconnects but `running=False` until a separate start; after start, `running=True`. |
| Actual result | See TC-006 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-007 — Motor-fault stop, latch, and recovery

| Field | Specification |
| --- | --- |
| Requirement | REQ-005 |
| Preconditions | Pump configured to a valid speed; test running and faulted states |
| Steps | 1. Inject motor fault. 2. Verify stop and latched fault. 3. Attempt to start. 4. Reset motor fault. 5. Confirm no automatic restart. 6. Explicitly start. 7. Separately verify that an active sensor fault still blocks starting. |
| Expected result | Motor fault forces `running=False`, `motor_fault_active=True`; start is rejected while fault active (API HTTP 409). Reset does not auto-start. Other fault interlocks remain effective. |
| Actual result | See TC-007 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-008 — Inject RPM feedback and detect anomalies

| Field | Specification |
| --- | --- |
| Requirement | REQ-006 |
| Preconditions | Pump running at commanded speed `150 RPM`, no faults |
| Steps | 1. Submit `120`, `150`, and `180 RPM` (valid boundary/nominal values). 2. In separate fresh runs inject `0`, `119`, `181 RPM`, and other abnormal samples. 3. Verify fault code and stopped state. 4. Attempt restart before fault reset; then reset and explicitly restart. |
| Expected result | `120–180 RPM` inclusive produces no fault; `0` produces `BLOCKED`; `119` produces `UNDERSPEED`; `181` produces `OVERSPEED`. Abnormal feedback latches fault, stops pump, and requires reset plus explicit restart. |
| Actual result | See TC-008 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-009 — Fault event traceability

| Field | Specification |
| --- | --- |
| Requirement | REQ-007 |
| Preconditions | Fresh pump with no events; API available through in-memory test client |
| Steps | 1. Set `150 RPM`; start. 2. Inject feedback of `0 RPM`. 3. Read event history through `GET /events`. 4. Inspect event ordering, timestamp, fault details, and limiting behavior. |
| Expected result | Sequential event IDs; UTC timestamps; a `feedback_fault_detected` event with `fault_code=BLOCKED`; `/events` returns recorded items in order and respects requested limit. |
| Actual result | See TC-009 in [test report](test_report.md). |
| Status | Recorded at execution. |

## TC-010 — Report current state through API

| Field | Specification |
| --- | --- |
| Requirement | REQ-008 |
| Preconditions | New pump; additional scenarios set speed and inject sensor or motor fault |
| Steps | 1. Call `GET /status` on initial pump. 2. Set speed/start and query status. 3. Inject sensor/motor fault in isolated API instances. 4. Query status again. |
| Expected result | API returns six specified fields with values reflecting initial, running, and faulted states; HTTP 200. |
| Actual result | See TC-010 in [test report](test_report.md). |
| Status | Recorded at execution. |

## Execution policy

- Every case must have its mapped pytest function(s) discovered and executed to receive **Pass**.
- Any failing/error result yields **Fail**; skipped or missing mapped tests are reported as **Incomplete** or **Not Run**, never as Pass.
- Re-execute after functional code changes; retain a report with **date, environment, and commit ID** for reproducibility.
- The report documents software-model behavior only; it does not demonstrate testing of physical hardware or clinical safety.
