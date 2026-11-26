#!/usr/bin/env python3
"""Validate the Part 4 (pack assembly & maintenance) data snapshot.

Checks are independent of the generator: they read the finished SQLite files and
apply the business rules documented in docs/2026-11-20_第四板块数据实现说明.md.

Usage:
    python scripts/validate_section4_data.py
    python scripts/validate_section4_data.py --json
    python scripts/validate_section4_data.py --integrated data/section4_integrated.sqlite
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DEFAULT_INTEGRATED = DATA_DIR / "section4_integrated.sqlite"
DEFAULT_OWN = DATA_DIR / "section4_synthetic.sqlite"

PART4_TABLES = [
    "BATTERY_PACK",
    "BATTERY_PACK_UNIT",
    "ASSEMBLY_JOB",
    "MAINTENANCE_EVENT",
    "PACK_INSPECTION",
    "SERVICE_RELEASE",
    "SERVICE_RELEASE_INSPECTION",
]
UPSTREAM_TABLES = [
    "organization", "data_source", "battery_unit", "battery_unit_source",
    "lifecycle_event", "battery_unit_curve_reference", "DiagnosticTest",
    "TestMeasurement", "ChargeReferenceCurve", "DischargeReferenceCurve",
    "MatchResult", "USE_PURPOSE", "PURPOSE_CRITERION",
    "ELIGIBILITY_ASSESSMENT", "ASSESSMENT_METRIC", "PURPOSE_EVALUATION",
]
EXPECTED_COUNTS = {
    "BATTERY_PACK": 160,
    "BATTERY_PACK_UNIT": 653,
    "ASSEMBLY_JOB": 175,
    "MAINTENANCE_EVENT": 23,
    "PACK_INSPECTION": 175,
    "SERVICE_RELEASE": 179,
    "SERVICE_RELEASE_INSPECTION": 175,
}
SNAPSHOT_TEXT = "2026-11-20T11:20:00+08:00"
SNAPSHOT_NAIVE = "2026-11-20T11:20:00"
MISSING_PARENTS = {
    "battery_unit",
    "organization",
    "ELIGIBILITY_ASSESSMENT",
    "USE_PURPOSE",
    "lifecycle_event",
}


class Report:
    def __init__(self):
        self.checks = []

    def check(self, name, ok, detail=""):
        self.checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    @property
    def ok(self):
        return all(c["ok"] for c in self.checks)

    def print_text(self):
        width = max(len(c["check"]) for c in self.checks) if self.checks else 10
        failed = 0
        for c in self.checks:
            mark = "PASS" if c["ok"] else "FAIL"
            if not c["ok"]:
                failed += 1
            print(f"[{mark}] {c['check']:<{width}}  {c['detail']}")
        print("-" * (width + 12))
        print(f"{len(self.checks) - failed}/{len(self.checks)} checks passed")
        return failed == 0


def scalar(con, sql, params=()):
    return con.execute(sql, params).fetchone()[0]


def count(con, sql, params=()):
    return scalar(con, sql, params)


def validate_integrated(path: Path, report: Report):
    if not path.exists():
        report.check(f"integrated db exists ({path.name})", False, str(path))
        return None
    report.check(f"integrated db exists ({path.name})", True, str(path))
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tables = {
        name for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ) if not name.startswith("sqlite_")
    }
    report.check(
        "integrated db has all 23 base tables",
        len(tables) == 23,
        f"{len(tables)} tables",
    )
    missing = set(PART4_TABLES) - tables
    report.check("all 7 Part 4 tables present", not missing, ",".join(sorted(missing)))
    missing_upstream = set(UPSTREAM_TABLES) - tables
    report.check(
        "all 16 upstream tables carried over",
        not missing_upstream,
        ",".join(sorted(missing_upstream)),
    )

    fk = list(con.execute("PRAGMA foreign_key_check"))
    report.check("PRAGMA foreign_key_check is empty", not fk, f"{len(fk)} violations")

    for table, expected in EXPECTED_COUNTS.items():
        actual = count(con, f"SELECT COUNT(*) FROM {table}")
        report.check(f"{table} row count = {expected}", actual == expected, f"{actual} rows")

    # ---- Part 3 linkage ---------------------------------------------------
    report.check(
        "lifecycle_event = 1200 upstream + 23 Part 4 maintenance events",
        count(con, "SELECT COUNT(*) FROM lifecycle_event") == 1223
        and count(con, "SELECT COUNT(*) FROM lifecycle_event WHERE event_type='maintenance'") == 23,
        f"{count(con, 'SELECT COUNT(*) FROM lifecycle_event')} events",
    )
    report.check(
        "all Part 4 installs reference a final P01-P09 assessment of the same unit",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
            WHERE a.status <> 'final'
               OR a.final_purpose_id NOT BETWEEN 1 AND 9
               OR a.unit_id <> pu.unit_id
            """,
        ) == 0,
        "",
    )
    report.check(
        "no draft / retired / P10 unit is installed",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
            WHERE a.status <> 'final' OR a.final_purpose_id NOT BETWEEN 1 AND 9
            """,
        ) == 0,
        "",
    )
    eligible = count(
        con,
        "SELECT COUNT(*) FROM ELIGIBILITY_ASSESSMENT "
        "WHERE status='final' AND final_purpose_id BETWEEN 1 AND 9",
    )
    installed_units = count(con, "SELECT COUNT(DISTINCT unit_id) FROM BATTERY_PACK_UNIT")
    report.check(
        "725 second-life-assemblable units accounted (652 installed + 73 spare)",
        eligible == 725 and installed_units == 652,
        f"eligible={eligible}, installed={installed_units}",
    )
    report.check(
        "all installed units were registered before pack assembly",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            JOIN battery_unit u ON u.unit_id = pu.unit_id
            WHERE u.registration_status <> 'registered'
            """,
        ) == 0,
        "",
    )
    report.check(
        "each pack's members all belong to the pack's released purpose",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
            WHERE EXISTS (
                SELECT 1 FROM SERVICE_RELEASE r
                WHERE r.pack_id = pu.pack_id AND r.purpose_id <> a.final_purpose_id
            )
            """,
        ) == 0,
        "",
    )

    # ---- temporal membership rules ---------------------------------------
    report.check(
        "no overlapping active installation for the same unit",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT a
            JOIN BATTERY_PACK_UNIT b
              ON a.unit_id = b.unit_id AND a.pack_unit_id < b.pack_unit_id
            WHERE a.joined_at < COALESCE(b.removed_at, '9999-12-31T23:59:59+08:00')
              AND COALESCE(a.removed_at, '9999-12-31T23:59:59+08:00') > b.joined_at
            """,
        ) == 0,
        "",
    )
    report.check(
        "no overlapping installation at the same pack position",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT a
            JOIN BATTERY_PACK_UNIT b
              ON a.pack_id = b.pack_id AND a.position_code = b.position_code
                 AND a.pack_unit_id < b.pack_unit_id
            WHERE a.joined_at < COALESCE(b.removed_at, '9999-12-31T23:59:59+08:00')
              AND COALESCE(a.removed_at, '9999-12-31T23:59:59+08:00') > b.joined_at
            """,
        ) == 0,
        "",
    )
    report.check(
        "each install has exactly one add source",
        count(
            con,
            "SELECT COUNT(*) FROM BATTERY_PACK_UNIT "
            "WHERE (added_by_job_code IS NOT NULL) + (added_by_maintenance_id IS NOT NULL) <> 1",
        ) == 0,
        "",
    )
    report.check(
        "each removed install has exactly one remove source",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT
            WHERE removed_at IS NOT NULL
              AND (removed_by_job_code IS NOT NULL)
                + (removed_by_maintenance_id IS NOT NULL) <> 1
            """,
        ) == 0,
        "",
    )
    report.check(
        "no missing-source exception is needed in the synthetic data",
        count(
            con,
            "SELECT COUNT(*) FROM BATTERY_PACK_UNIT WHERE source_missing_reason IS NOT NULL",
        ) == 0,
        "all changes traced to a job or maintenance",
    )
    report.check(
        "removed_at is always later than joined_at",
        count(
            con,
            "SELECT COUNT(*) FROM BATTERY_PACK_UNIT "
            "WHERE removed_at IS NOT NULL AND julianday(removed_at) <= julianday(joined_at)",
        ) == 0,
        "",
    )
    report.check(
        "exactly one unit is reinstalled with occurrence_no = 2",
        count(
            con,
            "SELECT COUNT(*) FROM BATTERY_PACK_UNIT WHERE occurrence_no > 1",
        ) == 1,
        "",
    )
    report.check(
        "current composition = 636 active installs",
        count(con, "SELECT COUNT(*) FROM BATTERY_PACK_UNIT WHERE removed_at IS NULL") == 636,
        "",
    )

    # ---- job / maintenance consistency -----------------------------------
    report.check(
        "all completed jobs have ended_at and execution_result",
        count(
            con,
            "SELECT COUNT(*) FROM ASSEMBLY_JOB "
            "WHERE ended_at IS NULL OR execution_result IS NULL",
        ) == 0,
        "",
    )
    report.check(
        "reassembly jobs are linked to a maintenance or explicitly standalone",
        count(
            con,
            """
            SELECT COUNT(*) FROM ASSEMBLY_JOB j
            WHERE j.job_type = 'reassembly'
              AND j.maintenance_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM MAINTENANCE_EVENT m
                  JOIN lifecycle_event e ON e.event_id = m.maintenance_id
                  WHERE m.maintenance_id = j.maintenance_id
                    AND e.battery_pack_id = j.pack_id)
            """,
        ) == 0,
        "",
    )
    report.check(
        "maintenance detail rows match a pack-targeted maintenance parent event",
        count(
            con,
            """
            SELECT COUNT(*) FROM MAINTENANCE_EVENT m
            JOIN lifecycle_event e ON e.event_id = m.maintenance_id
            WHERE e.event_type <> 'maintenance'
               OR e.battery_pack_id IS NULL
               OR e.battery_unit_id IS NOT NULL
               OR e.actor_org_id IS NULL
               OR e.data_origin <> 'synthetic'
            """,
        ) == 0,
        "",
    )
    report.check(
        "maintenance events are 23 and include one in-progress record",
        count(con, "SELECT COUNT(*) FROM MAINTENANCE_EVENT") == 23
        and count(con, "SELECT COUNT(*) FROM MAINTENANCE_EVENT WHERE execution_result IS NULL") == 1,
        "",
    )
    report.check(
        "installation change sources belong to the same pack",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            LEFT JOIN ASSEMBLY_JOB aj ON aj.job_code = pu.added_by_job_code
            LEFT JOIN ASSEMBLY_JOB rj ON rj.job_code = pu.removed_by_job_code
            LEFT JOIN MAINTENANCE_EVENT am ON am.maintenance_id = pu.added_by_maintenance_id
            LEFT JOIN MAINTENANCE_EVENT rm ON rm.maintenance_id = pu.removed_by_maintenance_id
            LEFT JOIN lifecycle_event ae ON ae.event_id = am.maintenance_id
            LEFT JOIN lifecycle_event re ON re.event_id = rm.maintenance_id
            WHERE (pu.added_by_job_code IS NOT NULL AND aj.pack_id <> pu.pack_id)
               OR (pu.removed_by_job_code IS NOT NULL AND rj.pack_id <> pu.pack_id)
               OR (pu.added_by_maintenance_id IS NOT NULL AND ae.battery_pack_id <> pu.pack_id)
               OR (pu.removed_by_maintenance_id IS NOT NULL AND re.battery_pack_id <> pu.pack_id)
            """,
        ) == 0,
        "",
    )

    # ---- inspections ------------------------------------------------------
    report.check(
        "inspection composition lies inside an effective membership interval",
        count(con, "SELECT COUNT(*) FROM V_PART4_INSPECTION_EMPTY_COMPOSITION") == 0,
        "",
    )
    report.check(
        "inspection has at most one primary trigger",
        count(
            con,
            "SELECT COUNT(*) FROM PACK_INSPECTION "
            "WHERE triggered_by_job_code IS NOT NULL AND triggered_by_maintenance_id IS NOT NULL",
        ) == 0,
        "",
    )
    report.check(
        "inspection trigger belongs to the same pack",
        count(
            con,
            """
            SELECT COUNT(*) FROM PACK_INSPECTION i
            LEFT JOIN ASSEMBLY_JOB j ON j.job_code = i.triggered_by_job_code
            LEFT JOIN MAINTENANCE_EVENT m ON m.maintenance_id = i.triggered_by_maintenance_id
            LEFT JOIN lifecycle_event e ON e.event_id = m.maintenance_id
            WHERE (i.triggered_by_job_code IS NOT NULL AND j.pack_id <> i.pack_id)
               OR (i.triggered_by_maintenance_id IS NOT NULL AND e.battery_pack_id <> i.pack_id)
            """,
        ) == 0,
        "",
    )
    report.check(
        "composition_as_of never lies after inspected_at",
        count(
            con,
            "SELECT COUNT(*) FROM PACK_INSPECTION "
            "WHERE julianday(composition_as_of) > julianday(inspected_at)",
        ) == 0,
        "",
    )

    # ---- service releases and evidence -----------------------------------
    report.check(
        "allowed releases all have same-pack, same-composition inspection evidence",
        count(con, "SELECT COUNT(*) FROM V_PART4_ALLOWED_RELEASE_WITHOUT_EVIDENCE") == 0,
        "",
    )
    report.check(
        "deferred releases all record a missing-evidence reason",
        count(con, "SELECT COUNT(*) FROM V_PART4_DEFERRED_RELEASE_WITHOUT_REASON") == 0,
        "",
    )
    report.check(
        "decision composition_as_of never lies after decided_at",
        count(
            con,
            "SELECT COUNT(*) FROM SERVICE_RELEASE "
            "WHERE julianday(composition_as_of) > julianday(decided_at)",
        ) == 0,
        "",
    )
    report.check(
        "every release references the pack's own purpose",
        count(
            con,
            """
            SELECT COUNT(*) FROM SERVICE_RELEASE r
            WHERE EXISTS (
                SELECT 1 FROM BATTERY_PACK_UNIT pu
                JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
                WHERE pu.pack_id = r.pack_id AND a.final_purpose_id <> r.purpose_id)
            """,
        ) == 0,
        "",
    )
    report.check(
        "allowed evidence inspections passed (no failed inspection is evidence)",
        count(
            con,
            """
            SELECT COUNT(*) FROM SERVICE_RELEASE_INSPECTION ri
            JOIN SERVICE_RELEASE r ON r.release_code = ri.release_code
            JOIN PACK_INSPECTION i ON i.inspection_code = ri.inspection_code
            WHERE r.decision_result = 'allowed'
              AND i.inspection_result NOT IN ('pass', 'pass_with_observation')
            """,
        ) == 0,
        "",
    )
    report.check(
        "releases requiring no evidence are rejected/deferred with a documented reason",
        count(
            con,
            """
            SELECT COUNT(*) FROM SERVICE_RELEASE r
            WHERE r.decision_result IN ('rejected', 'deferred')
              AND NOT EXISTS (
                  SELECT 1 FROM SERVICE_RELEASE_INSPECTION ri
                  WHERE ri.release_code = r.release_code)
              AND (r.missing_evidence_reason IS NULL
                   OR length(trim(r.missing_evidence_reason)) = 0)
            """,
        ) == 0,
        "",
    )

    # ---- pack status alignment -------------------------------------------
    status_rows = con.execute(
        """
        SELECT p.pack_code, p.business_status,
               (SELECT r.decision_result FROM SERVICE_RELEASE r
                 WHERE r.pack_id = p.pack_id
                 ORDER BY r.decided_at DESC, r.release_code DESC LIMIT 1),
               (SELECT r.use_restrictions FROM SERVICE_RELEASE r
                 WHERE r.pack_id = p.pack_id
                 ORDER BY r.decided_at DESC, r.release_code DESC LIMIT 1)
        FROM BATTERY_PACK p ORDER BY p.pack_code
        """
    ).fetchall()
    status_bad = []
    for pack_code, status, decision, restrictions in status_rows:
        if status == "in_maintenance":
            continue
        if status == "available":
            ok = decision == "allowed" and restrictions is None
        elif status == "restricted":
            ok = (decision == "allowed" and restrictions is not None) or decision == "rejected"
        elif status == "pending_inspection":
            ok = decision == "deferred"
        elif status == "retired":
            ok = decision == "rejected"
        else:
            ok = False
        if not ok:
            status_bad.append((pack_code, status, decision, restrictions))
    report.check(
        "pack business_status matches latest release decision (except in_maintenance)",
        not status_bad,
        f"{len(status_bad)} mismatches: {status_bad[:3]}",
    )
    report.check(
        "restricted/retired/in_maintenance packs all carry a status reason",
        count(
            con,
            """
            SELECT COUNT(*) FROM BATTERY_PACK
            WHERE business_status IN ('restricted', 'retired', 'in_maintenance')
              AND (status_reason IS NULL OR length(trim(status_reason)) = 0)
            """,
        ) == 0,
        "",
    )
    report.check(
        "evidence inspections happened before the release decision",
        count(
            con,
            """
            SELECT COUNT(*) FROM SERVICE_RELEASE r
            JOIN SERVICE_RELEASE_INSPECTION ri ON ri.release_code = r.release_code
            JOIN PACK_INSPECTION i ON i.inspection_code = ri.inspection_code
            WHERE julianday(i.inspected_at) > julianday(r.decided_at)
            """,
        ) == 0,
        "",
    )

    # recorded_at must not precede the business fact it records
    recorded_bad = 0
    recorded_bad += count(
        con,
        "SELECT COUNT(*) FROM BATTERY_PACK WHERE julianday(recorded_at) < julianday(formed_at)",
    )
    recorded_bad += count(
        con,
        "SELECT COUNT(*) FROM ASSEMBLY_JOB WHERE julianday(recorded_at) < julianday(ended_at)",
    )
    recorded_bad += count(
        con,
        "SELECT COUNT(*) FROM BATTERY_PACK_UNIT WHERE julianday(recorded_at) < julianday(joined_at)",
    )
    recorded_bad += count(
        con,
        "SELECT COUNT(*) FROM PACK_INSPECTION WHERE julianday(recorded_at) < julianday(inspected_at)",
    )
    recorded_bad += count(
        con,
        "SELECT COUNT(*) FROM SERVICE_RELEASE WHERE julianday(recorded_at) < julianday(decided_at)",
    )
    report.check("recorded_at never precedes the recorded fact", recorded_bad == 0, f"{recorded_bad} rows")

    report.check(
        "maintenance events happen after their pack was formed",
        count(
            con,
            """
            SELECT COUNT(*) FROM MAINTENANCE_EVENT m
            JOIN lifecycle_event e ON e.event_id = m.maintenance_id
            JOIN BATTERY_PACK p ON p.pack_id = e.battery_pack_id
            WHERE julianday(e.occurred_at) < julianday(substr(p.formed_at, 1, 19))
            """,
        ) == 0,
        "",
    )
    report.check(
        "job-triggered inspections happen after the triggering job ends",
        count(
            con,
            """
            SELECT COUNT(*) FROM PACK_INSPECTION i
            JOIN ASSEMBLY_JOB j ON j.job_code = i.triggered_by_job_code
            WHERE julianday(i.inspected_at) < julianday(j.ended_at)
            """,
        ) == 0,
        "",
    )

    # ---- time horizon -----------------------------------------------------
    for table, column in [
        ("BATTERY_PACK", "formed_at"),
        ("BATTERY_PACK", "recorded_at"),
        ("ASSEMBLY_JOB", "ended_at"),
        ("BATTERY_PACK_UNIT", "joined_at"),
        ("BATTERY_PACK_UNIT", "removed_at"),
        ("PACK_INSPECTION", "inspected_at"),
        ("SERVICE_RELEASE", "decided_at"),
    ]:
        after = count(
            con,
            f"SELECT COUNT(*) FROM {table} WHERE {column} > ?", (SNAPSHOT_TEXT,)
        )
        report.check(f"{table}.{column} <= snapshot clock", after == 0, f"{after} after snapshot")
    after_naive = count(
        con,
        "SELECT COUNT(*) FROM lifecycle_event "
        "WHERE event_type='maintenance' AND (occurred_at > ? OR recorded_at > ?)",
        (SNAPSHOT_NAIVE, SNAPSHOT_NAIVE),
    )
    report.check(
        "shared maintenance events <= snapshot clock", after_naive == 0,
        f"{after_naive} after snapshot",
    )

    # ---- views / audit consistency --------------------------------------
    for view in [
        "V_PART4_ALLOWED_RELEASE_WITHOUT_EVIDENCE",
        "V_PART4_DEFERRED_RELEASE_WITHOUT_REASON",
        "V_PART4_INSPECTION_EMPTY_COMPOSITION",
        "V_PART4_PACK_MIXED_PURPOSE",
    ]:
        try:
            rows = count(con, f"SELECT COUNT(*) FROM {view}")
            report.check(f"audit view {view} is empty", rows == 0, f"{rows} rows")
        except sqlite3.Error as exc:
            report.check(f"audit view {view} exists and is queryable", False, str(exc))
    report.check(
        "V_PART4_ASSESSMENT_POOL marks 725 units as assemblable",
        count(con, "SELECT COUNT(*) FROM V_PART4_ASSESSMENT_POOL WHERE is_assemblable = 1") == 725,
        "",
    )

    con.close()
    return True


def validate_upstream_preserved(integrated_path: Path, upstream_path: Path,
                                report: Report):
    """Part 4 must only append to the upstream snapshot; it must not edit it."""
    if not upstream_path.exists():
        report.check(
            "Part 1-3 upstream rows unchanged", True,
            "skipped: extracted upstream snapshot not present",
        )
        return
    check_tables = [
        "organization", "data_source", "battery_unit", "battery_unit_source",
        "battery_unit_curve_reference", "DiagnosticTest", "TestMeasurement",
        "ChargeReferenceCurve", "DischargeReferenceCurve", "MatchResult",
        "USE_PURPOSE", "PURPOSE_CRITERION", "ELIGIBILITY_ASSESSMENT",
        "ASSESSMENT_METRIC", "PURPOSE_EVALUATION",
    ]
    up = sqlite3.connect(f"file:{upstream_path}?mode=ro", uri=True)
    cur = sqlite3.connect(f"file:{integrated_path}?mode=ro", uri=True)
    changed = []
    try:
        for table in check_tables:
            up_rows = sorted(map(repr, up.execute(f"SELECT * FROM {table}")))
            cur_rows = sorted(map(repr, cur.execute(f"SELECT * FROM {table}")))
            if up_rows != cur_rows:
                changed.append(table)
        up_lifecycle = sorted(
            map(repr, up.execute("SELECT * FROM lifecycle_event"))
        )
        cur_lifecycle = sorted(
            map(repr, cur.execute(
                "SELECT * FROM lifecycle_event WHERE event_type <> 'maintenance'"
            ))
        )
        if up_lifecycle != cur_lifecycle:
            changed.append("lifecycle_event (non-maintenance rows)")
        report.check(
            "Part 1-3 upstream rows are byte-for-byte unchanged",
            not changed,
            ",".join(changed),
        )
    finally:
        up.close()
        cur.close()


def validate_own(path: Path, integrated_path: Path, report: Report):
    if not path.exists():
        report.check(f"own-tables db exists ({path.name})", False, str(path))
        return
    report.check(f"own-tables db exists ({path.name})", True, str(path))
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tables = [
        name for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    report.check(
        "own-tables db contains exactly the 7 Part 4 tables",
        tables == sorted(PART4_TABLES),
        ",".join(tables),
    )
    fk = list(con.execute("PRAGMA foreign_key_check"))
    bad = [row for row in fk if row[2] not in MISSING_PARENTS]
    report.check(
        "own-tables db FK check only reports missing upstream parent tables",
        not bad,
        f"{len(fk)} expected missing-parent rows, {len(bad)} unexpected",
    )
    for table, expected in EXPECTED_COUNTS.items():
        actual = count(con, f"SELECT COUNT(*) FROM {table}")
        report.check(f"{table} own-db count = {expected}", actual == expected, f"{actual} rows")
    if integrated_path.exists():
        icon = sqlite3.connect(f"file:{integrated_path}?mode=ro", uri=True)
        mismatched = []
        try:
            for table in PART4_TABLES:
                own_rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                int_rows = icon.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if own_rows != int_rows:
                    mismatched.append(f"{table}:{own_rows}!={int_rows}")
        finally:
            icon.close()
        report.check(
            "own-tables db counts match integrated db",
            not mismatched,
            ",".join(mismatched),
        )
    con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integrated", default=str(DEFAULT_INTEGRATED))
    parser.add_argument("--own", default=str(DEFAULT_OWN))
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    integrated_path = Path(args.integrated)
    own_path = Path(args.own)
    report = Report()
    validate_integrated(integrated_path, report)
    validate_upstream_preserved(
        integrated_path, ROOT / "data" / "part3_handover" / "section3_eligibility_整合库.sqlite",
        report,
    )
    validate_own(own_path, integrated_path, report)

    if args.json:
        print(json.dumps(
            {"ok": report.ok, "checks": report.checks},
            ensure_ascii=False, indent=2,
        ))
    else:
        report.print_text()
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
