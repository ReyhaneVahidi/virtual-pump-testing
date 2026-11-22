# Software requirements — Virtual Laboratory Pump

**Document ID:** SRS-VP-001  
**Scope:** Software-only laboratory pump simulation and its REST API  
**Origin:** Portfolio requirements derived from the implemented simulator behavior and its existing automated tests; **not** supplied by Siemens, a client, or a medical-device standard.

## Purpose and conventions

This document describes eight **testable software requirements**. They apply to the deterministic simulation, not a physical motor, real sensor, or certified safety system.

- **SHALL** states behavior the implementation must satisfy.
- **1–300 RPM** refers to the commanded speed; **0–1000 RPM** is the separate allowable range for injected feedback values.
- Faults and detection are **simulated**; detection occurs only when the caller submits a feedback reading.
- **Safe stop** means the simulator sets `running` to `False`. It does **not** establish physical motor disconnection or a medical-device safety guarantee.
- Requirements are verified by the linked cases in [test_cases.md](test_cases.md) and [traceability_matrix.md](traceability_matrix.md).

| ID | Requirement (verifiable statement) | Verification cases |
| --- | --- | --- |
| **REQ-001** | The system SHALL accept integer commanded speeds in the inclusive range **1–300 RPM**. It SHALL reject out-of-range values without changing the prior speed. The API SHALL return HTTP **400** for out-of-range integer values and **422** for invalid noninteger path values. | TC-001, TC-002 |
| **REQ-002** | The pump SHALL start when a valid speed is configured and no fault interlock is active. A start request with no speed configured SHALL be rejected, keep `running=False`, and produce HTTP **409** through the API. | TC-003 |
| **REQ-003** | A stop command SHALL set `running=False`. Repeating a stop command while already stopped SHALL succeed without causing operation to resume. | TC-004 |
| **REQ-004** | A simulated sensor disconnection SHALL immediately set `running=False`, mark the sensor disconnected, invalidate the RPM reading, and reject starts while disconnected (HTTP **409** at the API). Reconnection SHALL NOT restart the pump; an explicit start is required. | TC-005, TC-006 |
| **REQ-005** | A simulated motor failure SHALL stop operation, latch the motor-fault state, and block further starts (HTTP **409** at the API) until reset. Reset SHALL NOT automatically restart. Reset of one fault SHALL NOT override a separate active interlock. | TC-007 |
| **REQ-006** | When running, feedback injection SHALL classify `0 RPM` as `BLOCKED`, readings strictly below **80%** of commanded speed as `UNDERSPEED`, and readings strictly above **120%** as `OVERSPEED`. Boundary values (80% and 120%) SHALL be accepted. A detected feedback fault SHALL latch, stop operation, and require explicit reset and restart. | TC-008 |
| **REQ-007** | A detected RPM feedback fault SHALL be recorded in the in-memory event history with a sequential event ID, UTC timestamp, and fault code. The API SHALL expose event records through `GET /events`. | TC-009 |
| **REQ-008** | `GET /status` SHALL report the current `speed`, `measured_rpm`, `running`, `sensor_connected`, `motor_fault_active`, and `feedback_fault_code` fields, reflecting the simulated operating state. | TC-010 |

## Boundaries and risks

- The 20% deviation tolerance is an **illustrative configuration**, not a validated technical specification.
- There is **no** physical actuator, sensor sampling loop, persistent event database, hard real-time guarantee, or regulatory safety certification.
- Requirements are retrospective portfolio documentation of implemented functions; they demonstrate *requirements-to-test traceability*, not independent customer requirements elicitation.

## Verification approach

Unit tests exercise the `Pump` class; API integration tests use FastAPI's in-memory `TestClient`. The full suite includes tests beyond the selected acceptance cases. [test_report.md](test_report.md) records an executed test run, while [traceability_matrix.md](traceability_matrix.md) maps each requirement to test evidence.
