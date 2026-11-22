"""Run pytest and update requirements traceability and execution evidence.

The test catalog maps specification IDs to existing pytest functions. All
parameterized executions matching a selector are included. Only observed JUnit
results may produce a Pass status; missing or skipped tests are not passes.

Usage from the repository root:
    python tools/generate_test_report.py

This script uses only the Python standard library (pytest is a test dependency).
"""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "docs" / "testing"
CATALOG = DOC_DIR / "test_mapping.json"


def git_revision():
    """Return the local commit hash when running inside a Git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ) if _git_available() else None
    return result.stdout.strip() if result and result.returncode == 0 else "Unavailable (source snapshot)"


def _git_available():
    """Check Git presence without making Git mandatory for report generation."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def junit_testcases(xml_path):
    """Return actual executed tests and their observed outcomes from JUnit XML."""
    document = ET.parse(xml_path)
    cases = []
    for node in document.iter("testcase"):
        class_name = node.attrib.get("classname", "")
        module_path = class_name.replace(".", "/") + ".py"
        node_id = f"{module_path}::{node.attrib['name']}"
        if node.find("failure") is not None or node.find("error") is not None:
            status = "Fail"
        elif node.find("skipped") is not None:
            status = "Skipped"
        else:
            status = "Pass"
        cases.append((node_id, status))
    return cases


def find_matches(selectors, executed):
    """Include each parameterized instance of every declared test selector."""
    matches = {}
    for selector in selectors:
        selected = [(name, status) for name, status in executed
                    if name == selector or name.startswith(selector + "[")]
        matches[selector] = selected
    return matches


def case_status(matches):
    """A case passes only when every mapped function ran and all instances passed."""
    values = list(matches.values())
    all_results = [status for instances in values for _, status in instances]
    if "Fail" in all_results:
        return "Fail"
    if not all_results:
        return "Not Run"
    if any(not instances for instances in values) or "Skipped" in all_results:
        return "Incomplete"
    return "Pass"


def test_link(selector):
    """Create a relative link from docs/testing to the real pytest source."""
    path, function = selector.split("::", 1)
    return f"[`{path}::{function}`](../../{path})"


def render_matrix(catalog, evidence):
    """Create the requirements-to-test traceability matrix with live results."""
    rows = [
        "# Requirements Traceability Matrix (RTM)",
        "",
        "**Document ID:** RTM-VP-001  ",
        "**Scope:** Selected acceptance cases for the software-only pump simulator  ",
        "**Source of mappings:** [test_mapping.json](test_mapping.json)  ",
        "**Test execution evidence:** [test_report.md](test_report.md)",
        "",
        "| Requirement | Test case | Existing automated tests | Result |",
        "| --- | --- | --- | --- |",
    ]
    for item in catalog["cases"]:
        d = evidence[item["id"]]
        linked = "<br>".join(test_link(s) for s in item["selectors"])
        # This is GitHub-flavored Markdown; <br> is used only in generated Markdown files.
        rows.append(
            f"| [{item['requirement']}](requirements.md) | "
            f"[{item['id']}](test_cases.md) — {item['title']} | "
            f"{linked} | **{d['status']}** ({d['runs']} runs) |"
        )
    rows.extend([
        "",
        "**Interpretation:** A `Pass` means all mapped pytest parameterizations "
        "executed successfully in the [recorded environment](test_report.md). "
        "Other tests in the complete suite may exercise additional behaviors; "
        "the RTM is deliberately not a claim of complete software, hardware, or safety coverage.",
        "",
    ])
    return "\n".join(rows)


def render_report(catalog, evidence, executed, exit_code, when_utc):
    """Generate a dated test report using results actually observed by pytest."""
    counts = Counter(result for _, result in executed)
    case_counts = Counter(item["status"] for item in evidence.values())
    unique_mapped = set()
    for info in evidence.values():
        unique_mapped.update(info["matched_ids"])
    summary = (
        f"**{counts['Pass']} passed, {counts['Fail']} failed, "
        f"{counts['Skipped']} skipped** (total **{len(executed)}** pytest executions)"
    )
    lines = [
        "# Test execution report",
        "",
        "**Document ID:** TER-VP-001  ",
        f"**Execution date (UTC):** {when_utc}  ",
        f"**Commit:** `{git_revision()}`  ",
        f"**Platform:** `{platform.platform()}`  ",
        f"**Python:** `{platform.python_version()}`  ",
        "**Command:** `python tools/generate_test_report.py` "
        "(executes `python -m pytest -q --junitxml=<temporary file>`)  ",
        f"**pytest exit code:** `{exit_code}`",
        "",
        "## Overall execution outcome",
        "",
        summary + ".",
        "",
        f"- Requirement cases: **{case_counts['Pass']} Pass**, "
        f"**{case_counts['Fail']} Fail**, "
        f"**{case_counts['Incomplete']} Incomplete**, "
        f"**{case_counts['Not Run']} Not Run** out of {len(catalog['cases'])}.",
        f"- Unique pytest executions mapped to the selected cases: "
        f"**{len(unique_mapped)}** of {len(executed)} in the full suite.",
        "- This is **observed software test evidence**, not measurement from a physical pump.",
        "",
        "## Test case execution results",
        "",
        "| Test case | Requirement | Actual observed result | Status |",
        "| --- | --- | --- | --- |",
    ]
    for item in catalog["cases"]:
        info = evidence[item["id"]]
        actual = (f"{info['passed']}/{info['runs']} linked pytest executions passed"
                  if info["runs"] else "No matching executed tests")
        if info["missing"]:
            actual += f"; {info['missing']} unmapped/missing selector(s)"
        if info["failed"]:
            actual += f"; {info['failed']} failed"
        if info["skipped"]:
            actual += f"; {info['skipped']} skipped"
        lines.append(
            f"| [{item['id']}](test_cases.md) — {item['title']} | "
            f"[{item['requirement']}](requirements.md) | {actual} | **{info['status']}** |"
        )
    lines.extend([
        "",
        "## Evidence and interpretation",
        "",
        "- Actual results above are read from the JUnit XML produced by **this run**.",
        "- `Pass`: all existing mapped test instances passed; `Fail`: at least one failed; "
        "`Incomplete`: test skipped or a selector did not match; `Not Run`: no mapped tests executed.",
        "- The underlying pytest functions contain the detailed assertions for "
        "pump state, HTTP responses, fault codes, and event fields. Passing status "
        "means those assertions were satisfied, not that physical effects were observed.",
        "- Evidence is specific to the recorded source revision and environment. "
        "Regenerate after code or dependency changes; check CI separately.",
        "",
        "## How to reproduce",
        "",
        "```powershell",
        "python -m pip install -r requirements.txt",
        "python tools/generate_test_report.py",
        "```",
        "",
        "The command updates this report and the RTM. Commit updated reports "
        "only after verifying they reflect the intended revision and run.",
        "",
    ])
    return "\n".join(lines)


def main():
    """Run full tests, validate trace links, and write the two evidence files."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="pump_validation_") as working_dir:
        xml_path = Path(working_dir) / "test_results.xml"
        command = [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml_path}"]
        result = subprocess.run(command, cwd=ROOT, check=False)
        if not xml_path.is_file():
            print("No JUnit XML was produced; report not updated.", file=sys.stderr)
            return 2
        executed = junit_testcases(xml_path)

    evidence = {}
    for item in catalog["cases"]:
        matches = find_matches(item["selectors"], executed)
        flattened = [x for group in matches.values() for x in group]
        evidence[item["id"]] = {
            "status": case_status(matches),
            "runs": len(flattened),
            "passed": sum(status == "Pass" for _, status in flattened),
            "failed": sum(status == "Fail" for _, status in flattened),
            "skipped": sum(status == "Skipped" for _, status in flattened),
            "missing": sum(len(group) == 0 for group in matches.values()),
            "matched_ids": [name for name, _ in flattened],
        }

    when_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    (DOC_DIR / "traceability_matrix.md").write_text(
        render_matrix(catalog, evidence), encoding="utf-8"
    )
    (DOC_DIR / "test_report.md").write_text(
        render_report(catalog, evidence, executed, result.returncode, when_utc),
        encoding="utf-8",
    )
    print("\nUpdated docs/testing/traceability_matrix.md and docs/testing/test_report.md")
    return 0 if result.returncode == 0 and all(
        entry["status"] == "Pass" for entry in evidence.values()
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
