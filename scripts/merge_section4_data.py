#!/usr/bin/env python3
"""Merge the Part 4 handover package into a database that already contains
the Part 1-3 shared tables (organization / battery_unit / lifecycle_event /
ELIGIBILITY_ASSESSMENT / USE_PURPOSE ...).

This is the supported path for the group's final merge: start from the
authoritative Part 1-3 integration database, then run this helper.  It does
NOT copy or overwrite upstream rows; it only creates and fills the seven Part 4
tables and appends 23 maintenance rows to the shared lifecycle_event table.

Usage (from the extracted Part4_Handover folder):
    cp section3_eligibility_整合库.sqlite full_1_4.sqlite
    python scripts/merge_section4_data.py --target full_1_4.sqlite

Or from the project repository:
    python scripts/merge_section4_data.py --target /tmp/full_1_4.sqlite \
        --package-dir .

The package directory may be either the extracted handover folder (all files
side by side) or the project repository (files under data/ and sql/); the helper
searches the package root, data/ and sql/.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

PART4_TABLES = [
    "BATTERY_PACK",
    "BATTERY_PACK_UNIT",
    "ASSEMBLY_JOB",
    "MAINTENANCE_EVENT",
    "PACK_INSPECTION",
    "SERVICE_RELEASE",
    "SERVICE_RELEASE_INSPECTION",
]
# FK-safe import order: packs first, then shared events, then details/children.
IMPORT_ORDER = [
    "BATTERY_PACK",
    "MAINTENANCE_EVENT",
    "ASSEMBLY_JOB",
    "BATTERY_PACK_UNIT",
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
LIFECYCLE_COLUMNS = [
    "event_id", "battery_unit_id", "battery_pack_id", "actor_org_id",
    "from_owner_org_id", "to_owner_org_id", "lease_contract_item_id",
    "event_type", "occurred_at", "recorded_at", "evidence_ref", "data_origin",
]
COLUMNS = {
    "BATTERY_PACK": [
        "pack_id", "pack_code", "model_name", "formed_at", "design_requirements",
        "nameplate_ratings", "business_status", "status_reason", "data_origin",
        "recorded_at", "source_ref",
    ],
    "BATTERY_PACK_UNIT": [
        "pack_unit_id", "pack_id", "unit_id", "occurrence_no", "assessment_id",
        "position_code", "joined_at", "removed_at", "join_reason", "remove_reason",
        "join_order", "remove_order", "added_by_job_code", "added_by_maintenance_id",
        "removed_by_job_code", "removed_by_maintenance_id", "source_missing_reason",
        "data_origin", "recorded_at", "source_ref",
    ],
    "ASSEMBLY_JOB": [
        "job_code", "pack_id", "executor_org_id", "maintenance_id", "job_type",
        "started_at", "ended_at", "process_summary", "execution_result",
        "data_origin", "recorded_at", "source_ref",
    ],
    "MAINTENANCE_EVENT": [
        "maintenance_id", "maintenance_type", "problem_summary", "action_summary",
        "execution_result",
    ],
    "PACK_INSPECTION": [
        "inspection_code", "pack_id", "inspector_org_id", "triggered_by_job_code",
        "triggered_by_maintenance_id", "inspected_at", "composition_as_of",
        "composition_order", "method_ref", "method_version", "observation_summary",
        "inspection_result", "report_ref", "requirements_snapshot_or_ref",
        "data_origin", "recorded_at", "source_ref",
    ],
    "SERVICE_RELEASE": [
        "release_code", "pack_id", "responsible_org_id", "purpose_id",
        "purpose_basis_version", "decided_at", "composition_as_of", "composition_order",
        "decision_result", "decision_reason", "use_restrictions",
        "missing_evidence_reason", "data_origin", "recorded_at", "source_ref",
    ],
    "SERVICE_RELEASE_INSPECTION": ["release_code", "inspection_code"],
}


def find_file(package_dir: Path, name: str) -> Path:
    for candidate in (package_dir / name, package_dir / "data" / name,
                      package_dir / "sql" / name):
        if candidate.exists():
            return candidate
    raise SystemExit(
        f"数据包中找不到 {name}；请用 --package-dir 指向解压后的 Part4_Handover 根目录。"
    )


def table_names(con: sqlite3.Connection) -> set[str]:
    return {
        name for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ) if not name.startswith("sqlite_")
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True,
                        help="包含第 1-3 板块表的整合库；会直接在其上创建并导入第四板块")
    parser.add_argument("--package-dir", default=str(Path(__file__).resolve().parent.parent),
                        help="数据包根目录（默认脚本上级目录）")
    args = parser.parse_args(argv)

    target = Path(args.target)
    package_dir = Path(args.package_dir)
    if not target.exists():
        raise SystemExit(f"目标数据库不存在：{target}")

    own_db = find_file(package_dir, "section4_synthetic.sqlite")
    schema_sql = find_file(package_dir, "section4_schema.sql")
    views_sql = find_file(package_dir, "section4_views.sql")
    addon_csv = find_file(package_dir, "section4_lifecycle_event_addon.csv")

    con = sqlite3.connect(str(target))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        existing = table_names(con)
        missing_upstream = set(UPSTREAM_TABLES) - existing
        if missing_upstream:
            raise SystemExit(
                "目标库缺少第 1-3 板块共享表，不能合并："
                + ", ".join(sorted(missing_upstream))
            )
        already = [t for t in PART4_TABLES if t in existing]
        if already:
            raise SystemExit(
                "目标库已经包含第四板块表，请换一份干净的上游整合库："
                + ", ".join(already)
            )

        up_before = {
            table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in UPSTREAM_TABLES
        }
        lifecycle_before = up_before["lifecycle_event"]

        con.executescript(schema_sql.read_text(encoding="utf-8"))

        # 1) BATTERY_PACK first, because the shared lifecycle trigger needs it.
        con.execute("ATTACH DATABASE ? AS s4", (str(own_db),))
        cols = COLUMNS["BATTERY_PACK"]
        con.execute(
            f"INSERT INTO BATTERY_PACK ({','.join(cols)}) "
            f"SELECT {','.join(cols)} FROM s4.BATTERY_PACK"
        )

        # 2) Append the 23 shared maintenance events.
        with open(addon_csv, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            addon_rows = [
                [None if (row[c] == "" or row[c] == "NULL") else row[c]
                 for c in LIFECYCLE_COLUMNS]
                for row in reader
            ]
        con.executemany(
            f"INSERT INTO lifecycle_event ({','.join(LIFECYCLE_COLUMNS)}) "
            f"VALUES ({','.join(['?'] * len(LIFECYCLE_COLUMNS))})",
            addon_rows,
        )

        # 3) Remaining Part 4 tables in FK-safe order.
        for table in IMPORT_ORDER[1:]:
            cols = COLUMNS[table]
            con.execute(
                f"INSERT INTO {table} ({','.join(cols)}) "
                f"SELECT {','.join(cols)} FROM s4.{table}"
            )
        con.commit()
        con.execute("DETACH DATABASE s4")

        # 4) Query/audit views.
        con.executescript(views_sql.read_text(encoding="utf-8"))
        con.commit()

        # ---- post-merge verification -------------------------------------
        fk = list(con.execute("PRAGMA foreign_key_check"))
        if fk:
            raise SystemExit(f"合并后 foreign_key_check 失败：{fk[:5]}")
        expected_counts = {
            "BATTERY_PACK": 160, "BATTERY_PACK_UNIT": 653,
            "ASSEMBLY_JOB": 175, "MAINTENANCE_EVENT": 23,
            "PACK_INSPECTION": 175, "SERVICE_RELEASE": 179,
            "SERVICE_RELEASE_INSPECTION": 175,
        }
        for table in PART4_TABLES:
            actual = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if actual != {
                "BATTERY_PACK": 160, "BATTERY_PACK_UNIT": 653,
                "ASSEMBLY_JOB": 175, "MAINTENANCE_EVENT": 23,
                "PACK_INSPECTION": 175, "SERVICE_RELEASE": 179,
                "SERVICE_RELEASE_INSPECTION": 175,
            }[table]:
                raise SystemExit(f"{table} 合并后行数异常：{actual}")
        lifecycle_after = con.execute(
            "SELECT COUNT(*) FROM lifecycle_event"
        ).fetchone()[0]
        if lifecycle_after != lifecycle_before + 23:
            raise SystemExit(
                f"lifecycle_event 追加异常：{lifecycle_before} -> {lifecycle_after}"
            )
        for table in UPSTREAM_TABLES:
            if table == "lifecycle_event":
                continue
            after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if after != up_before[table]:
                raise SystemExit(
                    f"上游表 {table} 行数被改变：{up_before[table]} -> {after}"
                )
        audit_views = [
            "V_PART4_ALLOWED_RELEASE_WITHOUT_EVIDENCE",
            "V_PART4_DEFERRED_RELEASE_WITHOUT_REASON",
            "V_PART4_INSPECTION_EMPTY_COMPOSITION",
            "V_PART4_PACK_MIXED_PURPOSE",
        ]
        for view in audit_views:
            n = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
            if n:
                raise SystemExit(f"审计视图 {view} 非空：{n} 行")
        print("[ok] merged Part 4 into target database")
        print(f"     target           : {target}")
        print(f"     part4 tables     : {len(PART4_TABLES)}")
        print(f"     lifecycle_event  : {lifecycle_before} + 23 = {lifecycle_after}")
        print("     foreign_key_check: 0 violations")
        print("     audit views      : all empty")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
