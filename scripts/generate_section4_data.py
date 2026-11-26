#!/usr/bin/env python3
"""Generate the Part 4 (pack assembly & maintenance) synthetic data for the
IBA6151 battery-passport database.

The generator is deterministic: fixed seed + fixed UUID namespace + fixed
simulation clock.  It reads the handed-over Part 3 integrated database
(data/Part3_Handover.zip -> section3_eligibility_整合库.sqlite), builds a
pack-assembly / inspection / service-release scenario on top of the existing
1,000 units and 1,000 eligibility assessments, and writes:

  data/section4_integrated.sqlite      23 tables: upstream 16 + Part 4 7 (+ views)
  data/section4_synthetic.sqlite       Part 4's own 7 tables only (merge extract)
  data/section4_lifecycle_event_addon.csv  rows added to the shared lifecycle_event
  data/section4_previews/*.csv         10-row previews + summary counts
  data/section4_preview.html           standalone data preview
  sql/section4_lifecycle_event_addon.sql   INSERT statements for the shared table

Usage:
    python scripts/generate_section4_data.py
    python scripts/generate_section4_data.py --seed 20261120 --skip-html
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import random
import shutil
import sqlite3
import sys
import uuid
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths and fixed constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
PART3_ZIP = DATA_DIR / "Part3_Handover.zip"
PART3_DIR = DATA_DIR / "part3_handover"
PART3_DB_NAME = "section3_eligibility_整合库.sqlite"
UPSTREAM_DB = PART3_DIR / PART3_DB_NAME

OUT_INTEGRATED = DATA_DIR / "section4_integrated.sqlite"
OUT_OWN = DATA_DIR / "section4_synthetic.sqlite"
OUT_ADDON_CSV = DATA_DIR / "section4_lifecycle_event_addon.csv"
OUT_ADDON_SQL = SQL_DIR / "section4_lifecycle_event_addon.sql"
OUT_PREVIEW_DIR = DATA_DIR / "section4_previews"
OUT_HTML = DATA_DIR / "section4_preview.html"

SCHEMA_SQL = SQL_DIR / "section4_schema.sql"
VIEWS_SQL = SQL_DIR / "section4_views.sql"

SEED = 20261120
UUID_NS = uuid.UUID("4f0f6a7e-2d2a-5c1c-9b4d-7a0d3e5f9c11")

TZ = "+08:00"
INITIAL_START = dt.datetime(2026, 11, 19, 19, 0, 0)     # after 18:00 assessments
MAINT_BASE = dt.datetime(2026, 11, 20, 6, 0, 0)
REINSTALL_JOB_START = dt.datetime(2026, 11, 20, 8, 30, 0)
IN_PROGRESS_START = dt.datetime(2026, 11, 20, 10, 30, 0)
SNAPSHOT = dt.datetime(2026, 11, 20, 11, 20, 0)          # data snapshot clock

# (purpose_id, number of packs, cells per pack). 638 of the 725 second-life
# units are assembled; the remaining 87 stay as the unassembled spare pool.
PACK_PLAN = [
    (1, 1, 4),
    (2, 4, 4),
    (3, 1, 2),
    (4, 10, 4),
    (5, 27, 4),
    (6, 70, 4),
    (7, 3, 4),
    (8, 20, 4),
    (9, 24, 4),
]

PURPOSE_MODEL = {
    1: "PV", 2: "WIND", 3: "GRID", 4: "CI", 5: "RES",
    6: "TELECOM", 7: "UPS", 8: "AGV", 9: "LIGHT",
}

# Maintenance target plan, expressed with the 1-based pack numbers produced by
# the purpose-by-purpose pack numbering above (P01:1, P02:2-5, P03:6,
# P04:7-16, P05:17-43, P06:44-113, P07:114-116, P08:117-136, P09:137-160).
REPLACEMENT_PACKS = [17, 18, 19, 20, 44, 45, 46, 47, 48, 114, 117, 118, 137, 138]
REMOVAL_ONLY_PACKS = [49, 50]
REINSTALL_PACK = 21
NO_CHANGE_PACKS = [7, 22, 51, 119, 139]
IN_PROGRESS_PACK = 8

PART4_TABLES = [
    "BATTERY_PACK",
    "BATTERY_PACK_UNIT",
    "ASSEMBLY_JOB",
    "MAINTENANCE_EVENT",
    "PACK_INSPECTION",
    "SERVICE_RELEASE",
    "SERVICE_RELEASE_INSPECTION",
]

INSERT_ORDER = [
    "BATTERY_PACK",
    "ASSEMBLY_JOB",
    "MAINTENANCE_EVENT",
    "BATTERY_PACK_UNIT",
    "PACK_INSPECTION",
    "SERVICE_RELEASE",
    "SERVICE_RELEASE_INSPECTION",
]

LIFECYCLE_COLUMNS = [
    "event_id", "battery_unit_id", "battery_pack_id", "actor_org_id",
    "from_owner_org_id", "to_owner_org_id", "lease_contract_item_id",
    "event_type", "occurred_at", "recorded_at", "evidence_ref", "data_origin",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def fmt(t: dt.datetime) -> str:
    """Part 4 timestamptz text format (Asia/Shanghai offset)."""
    return t.strftime("%Y-%m-%dT%H:%M:%S") + TZ


def fmt_naive(t: dt.datetime) -> str:
    """Format used by the pre-existing lifecycle_event rows (no offset)."""
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def minutes(n: int) -> dt.timedelta:
    return dt.timedelta(minutes=n)


def quote_sql(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def ensure_upstream() -> Path:
    """Extract the handed-over Part 3 database when needed."""
    if UPSTREAM_DB.exists():
        return UPSTREAM_DB
    if not PART3_ZIP.exists():
        raise SystemExit(
            f"缺少上游输入：{PART3_ZIP}\n"
            "请把第三部分交接的 Part3_Handover.zip 放到 data/ 下再运行。"
        )
    PART3_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PART3_ZIP) as zf:
        for info in zf.infolist():
            name = info.filename
            if "__MACOSX" in name or name.endswith(".DS_Store"):
                continue
            if not (info.flag_bits & 0x800):
                try:
                    name = name.encode("cp437").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            target = Path(name)
            if target.name != PART3_DB_NAME:
                continue
            dest = PART3_DIR / target.name
            with zf.open(info) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return dest
    raise SystemExit(f"压缩包内未找到 {PART3_DB_NAME}")


# ---------------------------------------------------------------------------
# Read the upstream snapshot
# ---------------------------------------------------------------------------
def load_upstream(db_path: Path):
    con = sqlite3.connect(str(db_path))
    try:
        orgs = {
            row[0]: {"name": row[1], "type": row[2]}
            for row in con.execute(
                "SELECT organization_id, name, organization_type FROM organization"
            )
        }
        eligible = {p: [] for p in range(1, 10)}
        unit_assessment = {}
        for assessment_id, unit_id, purpose_id, status in con.execute(
            """
            SELECT a.assessment_id, a.unit_id, a.final_purpose_id, a.status
            FROM ELIGIBILITY_ASSESSMENT a
            JOIN battery_unit u ON u.unit_id = a.unit_id
            WHERE a.status = 'final' AND a.final_purpose_id BETWEEN 1 AND 9
            ORDER BY a.final_purpose_id, u.unit_id
            """
        ):
            eligible[purpose_id].append((assessment_id, unit_id))
            unit_assessment[unit_id] = (assessment_id, purpose_id, status)
        unit_status = {
            row[0]: row[1]
            for row in con.execute("SELECT unit_id, registration_status FROM battery_unit")
        }
        events = con.execute("SELECT COUNT(*) FROM lifecycle_event").fetchone()[0]
        units = con.execute("SELECT COUNT(*) FROM battery_unit").fetchone()[0]
        assessments = con.execute(
            "SELECT COUNT(*) FROM ELIGIBILITY_ASSESSMENT"
        ).fetchone()[0]
    finally:
        con.close()
    return {
        "orgs": orgs,
        "eligible": eligible,
        "unit_assessment": unit_assessment,
        "unit_status": unit_status,
        "lifecycle_events": events,
        "battery_units": units,
        "assessments": assessments,
    }


# ---------------------------------------------------------------------------
# Scenario construction
# ---------------------------------------------------------------------------
def build_scenario(upstream, seed: int):
    rng = random.Random(seed)
    orgs = upstream["orgs"]
    eligible = upstream["eligible"]

    pack_ids = [o for o, v in orgs.items() if v["type"] == "operator"] + [
        o for o, v in orgs.items() if v["type"] == "lessor"
    ]
    operator_recycler = [o for o, v in orgs.items() if v["type"] == "operator"] + [
        o for o, v in orgs.items() if v["type"] == "recycler"
    ]
    labs = [o for o, v in orgs.items() if v["type"] == "laboratory"]
    assert len(labs) >= 2 and len(operator_recycler) >= 5 and len(pack_ids) >= 10

    packs = []
    spare = {}
    pack_no = 0
    for purpose, count, size in PACK_PLAN:
        pool = eligible[purpose]
        needed = count * size
        if len(pool) < needed:
            raise SystemExit(
                f"P{purpose:02d} 可用评估单元不足：需要 {needed}，实际 {len(pool)}"
            )
        for k in range(count):
            pack_no += 1
            members = pool[k * size:(k + 1) * size]
            model = f"SIM-LFP-{size}S1P-{size * 1.1:.1f}Ah"
            packs.append(
                {
                    "no": pack_no,
                    "pack_id": str(uuid.uuid5(UUID_NS, f"part4:pack:{pack_no:04d}")),
                    "pack_code": f"SIM-PACK-{pack_no:04d}",
                    "purpose": purpose,
                    "purpose_code": f"P{purpose:02d}",
                    "size": size,
                    "model": model,
                    "design": f"SIM-DESIGN-{PURPOSE_MODEL[purpose]}-{size}S1P-V1",
                    "nameplate": (
                        f"{size}S1P / {size * 3.3:.1f} V nominal / "
                        f"{size * 1.1:.1f} Ah / {size * 3.3 * size * 1.1:.1f} Wh"
                    ),
                    "original_members": [
                        {
                            "assessment_id": aid,
                            "unit_id": uid,
                            "position": f"SLOT-{j + 1:02d}",
                        }
                        for j, (aid, uid) in enumerate(members)
                    ],
                    "installs": [],
                    "initial_job": None,
                    "initial_ended": None,
                    "initial_release": None,
                    "latest_release": None,
                    "maintenance_type": None,
                    "final_status": None,
                    "status_reason": None,
                }
            )
        spare[purpose] = pool[needed:]

    by_no = {p["no"]: p for p in packs}

    lifecycle_rows = []
    maintenance_rows = []
    job_rows = []
    install_rows = []
    inspection_rows = []
    release_rows = []
    evidence_rows = []

    counters = {"pack_unit": 0, "job": 0, "maint": 0, "insp": 0, "rel": 0}

    def next_id(kind):
        counters[kind] += 1
        if kind == "pack_unit":
            return counters[kind]
        width = {"job": 4, "maint": 3, "insp": 5, "rel": 5}[kind]
        return counters[kind], width

    # ---- initial assembly jobs and installations -------------------------
    for i, pack in enumerate(packs):
        counters["job"] += 1
        job_code = f"SIM-JOB-{counters['job']:04d}"
        start = INITIAL_START + dt.timedelta(seconds=int(i * 144))  # 2.4 min apart
        duration = rng.randint(40, 70)
        end = start + minutes(duration)
        executor = operator_recycler[i % len(operator_recycler)]
        pack["initial_job"] = {
            "job_code": job_code,
            "pack_id": pack["pack_id"],
            "executor_org_id": executor,
            "maintenance_id": None,
            "job_type": "initial_assembly",
            "started_at": fmt(start),
            "ended_at": fmt(end),
            "process_summary": (
                f"Initial {pack['size']}S1P pack assembly from assessed LiFePO4 cells; "
                "busbar torque and insulation checked."
            ),
            "execution_result": "completed",
            "data_origin": "synthetic",
            "recorded_at": fmt(end + minutes(rng.randint(5, 15))),
            "source_ref": f"SIM-SRC-JOB-{counters['job']:04d}",
        }
        job_rows.append(pack["initial_job"])
        pack["initial_ended"] = end
        for member in pack["original_members"]:
            counters["pack_unit"] += 1
            install = {
                "pack_unit_id": counters["pack_unit"],
                "pack_id": pack["pack_id"],
                "unit_id": member["unit_id"],
                "occurrence_no": 1,
                "assessment_id": member["assessment_id"],
                "position_code": member["position"],
                "joined_at": fmt(end),
                "removed_at": None,
                "join_reason": "initial_assembly",
                "remove_reason": None,
                "join_order": None,
                "remove_order": None,
                "added_by_job_code": job_code,
                "added_by_maintenance_id": None,
                "removed_by_job_code": None,
                "removed_by_maintenance_id": None,
                "source_missing_reason": None,
                "data_origin": "synthetic",
                "recorded_at": fmt(end + minutes(rng.randint(3, 12))),
                "source_ref": f"SIM-SRC-INST-{counters['pack_unit']:05d}",
            }
            pack["installs"].append(install)
            member["install"] = install
            install_rows.append(install)

    # ---- classify the initial inspection outcome -------------------------
    target_nos = set(
        REPLACEMENT_PACKS + REMOVAL_ONLY_PACKS + [REINSTALL_PACK]
        + NO_CHANGE_PACKS + [IN_PROGRESS_PACK]
    )
    non_target = [p["no"] for p in packs if p["no"] not in target_nos]
    rng.shuffle(non_target)
    pending_nos = set(non_target[:4])
    fail_nos = set(non_target[4:7])
    observed_nos = set(non_target[7:16])
    initial_category = {}
    for pack in packs:
        n = pack["no"]
        if n in pending_nos:
            initial_category[n] = "pending"
        elif n in fail_nos:
            initial_category[n] = "fail"
        elif n in observed_nos:
            initial_category[n] = "observed"
        else:
            initial_category[n] = "pass"

    # ---- initial inspections and service releases ------------------------
    basis_version = "eligibility_demo_20261119_v1"
    method_ref = "SIM-PACK-INSPECTION-SOP"
    method_version = "pack_inspection_20261120_v1"

    for pack in packs:
        category = initial_category[pack["no"]]
        end = pack["initial_ended"]
        if category == "pending":
            counters["rel"] += 1
            decided = end + minutes(rng.randint(150, 260))
            release = {
                "release_code": f"SIM-REL-{counters['rel']:05d}",
                "pack_id": pack["pack_id"],
                "responsible_org_id": pack_ids[(pack["no"] - 1) % len(pack_ids)],
                "purpose_id": pack["purpose"],
                "purpose_basis_version": basis_version,
                "decided_at": fmt(decided),
                "composition_as_of": fmt(end),
                "composition_order": None,
                "decision_result": "deferred",
                "decision_reason": (
                    f"No pack-level inspection is on file for the {pack['size']}S1P "
                    f"composition intended for {pack['purpose_code']}; use decision deferred."
                ),
                "use_restrictions": None,
                "missing_evidence_reason": (
                    "Pack-level inspection and report have not been completed for this composition."
                ),
                "data_origin": "synthetic",
                "recorded_at": fmt(decided + minutes(rng.randint(5, 15))),
                "source_ref": f"SIM-SRC-REL-{counters['rel']:05d}",
            }
            release_rows.append(release)
            pack["latest_release"] = release
            continue

        counters["insp"] += 1
        inspection_code = f"SIM-INSP-{counters['insp']:05d}"
        inspected = end + minutes(rng.randint(20, 80))
        if category == "fail":
            result = "fail"
            observation = (
                "Group-level acceptance check failed on insulation resistance and "
                "cell balance; the pack is not released for service."
            )
        elif category == "observed":
            result = "pass_with_observation"
            observation = (
                "Acceptance check passed with a cell-balance observation; "
                "restricted use recommended until the first duty cycle review."
            )
        else:
            result = "pass"
            observation = (
                "Group-level acceptance check passed: voltage, insulation and "
                "cell-balance observations are within the classroom demo limits."
            )
        inspection = {
            "inspection_code": inspection_code,
            "pack_id": pack["pack_id"],
            "inspector_org_id": labs[counters["insp"] % len(labs)],
            "triggered_by_job_code": pack["initial_job"]["job_code"],
            "triggered_by_maintenance_id": None,
            "inspected_at": fmt(inspected),
            "composition_as_of": fmt(end),
            "composition_order": None,
            "method_ref": method_ref,
            "method_version": method_version,
            "observation_summary": observation,
            "inspection_result": result,
            "report_ref": f"SIM-INSP-REPORT-{inspection_code[-5:]}",
            "requirements_snapshot_or_ref": (
                f"{pack['design']} + {basis_version} + {method_version}"
            ),
            "data_origin": "synthetic",
            "recorded_at": fmt(inspected + minutes(rng.randint(8, 20))),
            "source_ref": f"SIM-SRC-INSP-{counters['insp']:05d}",
        }
        inspection_rows.append(inspection)

        counters["rel"] += 1
        decided = inspected + minutes(rng.randint(10, 35))
        if result == "fail":
            decision = "rejected"
            reason = (
                f"Pack inspection {inspection_code} failed; release for "
                f"{pack['purpose_code']} is refused until rework and re-inspection."
            )
            restrictions = None
            missing = None
        elif result == "pass_with_observation":
            decision = "allowed"
            reason = (
                f"Inspection {inspection_code} passed with an observation; release for "
                f"{pack['purpose_code']} is allowed under the documented restriction."
            )
            restrictions = (
                "Restricted to the assessed duty; review cell balance after the first "
                "30 operating cycles and re-inspect before unrestricted release."
            )
            missing = None
        else:
            decision = "allowed"
            reason = (
                f"Inspection {inspection_code} passed for {pack['purpose_code']}; the "
                f"composition matches assessment basis {basis_version}."
            )
            restrictions = None
            missing = None
        release = {
            "release_code": f"SIM-REL-{counters['rel']:05d}",
            "pack_id": pack["pack_id"],
            "responsible_org_id": pack_ids[(pack["no"] + 3) % len(pack_ids)],
            "purpose_id": pack["purpose"],
            "purpose_basis_version": basis_version,
            "decided_at": fmt(decided),
            "composition_as_of": fmt(end),
            "composition_order": None,
            "decision_result": decision,
            "decision_reason": reason,
            "use_restrictions": restrictions,
            "missing_evidence_reason": missing,
            "data_origin": "synthetic",
            "recorded_at": fmt(decided + minutes(rng.randint(5, 20))),
            "source_ref": f"SIM-SRC-REL-{counters['rel']:05d}",
        }
        release_rows.append(release)
        evidence_rows.append(
            (release["release_code"], inspection_code)
        )
        if pack["initial_release"] is None:
            pack["initial_release"] = release
        pack["latest_release"] = release

    # ---- maintenance: shared parent events and Part 4 detail -------------
    def add_maintenance(pack, mtype, problem, action, execution_result, start):
        counters["maint"] += 1
        maintenance_id = str(
            uuid.uuid5(UUID_NS, f"part4:maintenance:{counters['maint']:03d}")
        )
        actor = operator_recycler[(pack["no"] + counters["maint"]) % len(operator_recycler)]
        parent = {
            "event_id": maintenance_id,
            "battery_unit_id": None,
            "battery_pack_id": pack["pack_id"],
            "actor_org_id": actor,
            "from_owner_org_id": None,
            "to_owner_org_id": None,
            "lease_contract_item_id": None,
            "event_type": "maintenance",
            "occurred_at": fmt_naive(start),
            "recorded_at": fmt_naive(start + minutes(rng.randint(8, 20))),
            "evidence_ref": f"SIM-EVID-MAINT-{counters['maint']:03d}",
            "data_origin": "synthetic",
        }
        lifecycle_rows.append(parent)
        detail = {
            "maintenance_id": maintenance_id,
            "maintenance_type": mtype,
            "problem_summary": problem,
            "action_summary": action,
            "execution_result": execution_result,
        }
        maintenance_rows.append(detail)
        return maintenance_id, actor

    def add_job(pack, job_type, start, duration, executor, maintenance_id, summary):
        counters["job"] += 1
        job_code = f"SIM-JOB-{counters['job']:04d}"
        end = start + minutes(duration)
        job = {
            "job_code": job_code,
            "pack_id": pack["pack_id"],
            "executor_org_id": executor,
            "maintenance_id": maintenance_id,
            "job_type": job_type,
            "started_at": fmt(start),
            "ended_at": fmt(end),
            "process_summary": summary,
            "execution_result": "completed",
            "data_origin": "synthetic",
            "recorded_at": fmt(end + minutes(rng.randint(5, 15))),
            "source_ref": f"SIM-SRC-JOB-{counters['job']:04d}",
        }
        job_rows.append(job)
        return job, end

    def add_install(pack, member, joined, join_reason, job_code=None,
                    maintenance_id=None, occurrence=1):
        counters["pack_unit"] += 1
        install = {
            "pack_unit_id": counters["pack_unit"],
            "pack_id": pack["pack_id"],
            "unit_id": member["unit_id"],
            "occurrence_no": occurrence,
            "assessment_id": member["assessment_id"],
            "position_code": member["position"],
            "joined_at": fmt(joined),
            "removed_at": None,
            "join_reason": join_reason,
            "remove_reason": None,
            "join_order": None,
            "remove_order": None,
            "added_by_job_code": job_code,
            "added_by_maintenance_id": maintenance_id,
            "removed_by_job_code": None,
            "removed_by_maintenance_id": None,
            "source_missing_reason": None,
            "data_origin": "synthetic",
            "recorded_at": fmt(joined + minutes(rng.randint(3, 12))),
            "source_ref": f"SIM-SRC-INST-{counters['pack_unit']:05d}",
        }
        pack["installs"].append(install)
        install_rows.append(install)
        return install

    def add_inspection(pack, inspected, composition_as_of, result, observation,
                       triggered_job=None, triggered_maintenance=None):
        counters["insp"] += 1
        inspection_code = f"SIM-INSP-{counters['insp']:05d}"
        inspection = {
            "inspection_code": inspection_code,
            "pack_id": pack["pack_id"],
            "inspector_org_id": labs[counters["insp"] % len(labs)],
            "triggered_by_job_code": triggered_job,
            "triggered_by_maintenance_id": triggered_maintenance,
            "inspected_at": fmt(inspected),
            "composition_as_of": fmt(composition_as_of),
            "composition_order": None,
            "method_ref": method_ref,
            "method_version": method_version,
            "observation_summary": observation,
            "inspection_result": result,
            "report_ref": f"SIM-INSP-REPORT-{inspection_code[-5:]}",
            "requirements_snapshot_or_ref": (
                f"{pack['design']} + {basis_version} + {method_version}"
            ),
            "data_origin": "synthetic",
            "recorded_at": fmt(inspected + minutes(rng.randint(8, 20))),
            "source_ref": f"SIM-SRC-INSP-{counters['insp']:05d}",
        }
        inspection_rows.append(inspection)
        return inspection

    def add_release(pack, inspection, decided, decision, reason,
                    restrictions=None, missing=None, composition_as_of=None):
        counters["rel"] += 1
        release = {
            "release_code": f"SIM-REL-{counters['rel']:05d}",
            "pack_id": pack["pack_id"],
            "responsible_org_id": pack_ids[(pack["no"] + counters["rel"]) % len(pack_ids)],
            "purpose_id": pack["purpose"],
            "purpose_basis_version": basis_version,
            "decided_at": fmt(decided),
            "composition_as_of": composition_as_of,
            "composition_order": None,
            "decision_result": decision,
            "decision_reason": reason,
            "use_restrictions": restrictions,
            "missing_evidence_reason": missing,
            "data_origin": "synthetic",
            "recorded_at": fmt(decided + minutes(rng.randint(5, 20))),
            "source_ref": f"SIM-SRC-REL-{counters['rel']:05d}",
        }
        release_rows.append(release)
        if inspection is not None:
            evidence_rows.append((release["release_code"], inspection["inspection_code"]))
        pack["latest_release"] = release
        return release

    def active_install(pack, position):
        for install in pack["installs"]:
            if install["position_code"] == position and install["removed_at"] is None:
                return install
        raise AssertionError(f"no active install at {position}")

    def free_spare(purpose):
        if not spare[purpose]:
            raise SystemExit(f"P{purpose:02d} 备件池已耗尽")
        return spare[purpose].pop(0)

    # replacement packs: reassembly job under maintenance replaces one cell
    replacement_details = []
    maint_slots = []
    for pack_no in REPLACEMENT_PACKS:
        pack = by_no[pack_no]
        maint_slots.append(("replacement", pack))
    for pack_no in REMOVAL_ONLY_PACKS:
        maint_slots.append(("removal", by_no[pack_no]))
    for pack_no in NO_CHANGE_PACKS:
        maint_slots.append(("no_change", by_no[pack_no]))

    for k, (kind, pack) in enumerate(maint_slots):
        start = MAINT_BASE + minutes(7 * k)
        slot = f"SLOT-{rng.randint(1, pack['size']):02d}"
        old = active_install(pack, slot)
        if kind == "replacement":
            replacement = free_spare(pack["purpose"])
            maintenance_id, actor = add_maintenance(
                pack,
                "component_replacement",
                f"Cell balance drift observed at {slot}; cell replacement required.",
                f"Remove the cell at {slot} and install a qualified replacement cell; "
                "re-torque and re-check insulation.",
                "completed",
                start,
            )
            job, end = add_job(
                pack,
                "reassembly",
                start + minutes(10),
                rng.randint(45, 65),
                actor,
                maintenance_id,
                f"Reassembly under maintenance {maintenance_id[-8:]}: replace cell at {slot}.",
            )
            old["removed_at"] = fmt(end)
            old["remove_reason"] = "replaced_after_fault"
            old["removed_by_job_code"] = job["job_code"]
            new_install = add_install(
                pack,
                {
                    "unit_id": replacement[1],
                    "assessment_id": replacement[0],
                    "position": slot,
                },
                end,
                "replacement_after_fault",
                job_code=job["job_code"],
            )
            inspected = end + minutes(rng.randint(15, 35))
            inspection = add_inspection(
                pack,
                inspected,
                end,
                "pass",
                "Post-replacement acceptance check passed; the new cell matches the "
                "assessment basis and pack balance is restored.",
                triggered_job=job["job_code"],
            )
            restricted = len(replacement_details) < 3
            release = add_release(
                pack,
                inspection,
                inspected + minutes(rng.randint(10, 25)),
                "allowed",
                (
                    f"Inspection {inspection['inspection_code']} passed on the replaced "
                    f"composition; release for {pack['purpose_code']} is allowed."
                ),
                restrictions=(
                    "Restricted to the assessed duty; monitor the replaced cell for the "
                    "first 30 cycles and re-inspect before unrestricted release."
                    if restricted else None
                ),
                composition_as_of=fmt(end),
            )
            replacement_details.append(
                {
                    "pack": pack,
                    "maintenance_id": maintenance_id,
                    "job_code": job["job_code"],
                    "removed_install": old,
                    "new_install": new_install,
                    "inspection": inspection,
                    "release": release,
                    "restricted": restricted,
                }
            )
        elif kind == "removal":
            maintenance_id, actor = add_maintenance(
                pack,
                "fault_repair",
                f"Faulty cell detected at {slot}; the cell is removed from service.",
                f"Remove the faulty cell at {slot} and quarantine it for diagnosis; "
                "no replacement is available in this scenario.",
                "completed",
                start,
            )
            removed_at = start + minutes(45)
            old["removed_at"] = fmt(removed_at)
            old["remove_reason"] = "removed_faulty_no_replacement"
            old["removed_by_maintenance_id"] = maintenance_id
            pack["removal_only"] = True
            inspected = removed_at + minutes(rng.randint(20, 40))
            inspection = add_inspection(
                pack,
                inspected,
                removed_at,
                "pass_with_observation",
                f"Composition re-checked after removing the cell at {slot}: the pack now "
                f"has {pack['size'] - 1} cells and no longer meets the {pack['size']}S1P design.",
                triggered_maintenance=maintenance_id,
            )
            add_release(
                pack,
                inspection,
                inspected + minutes(rng.randint(10, 25)),
                "rejected",
                (
                    f"Composition after maintenance has {pack['size'] - 1} cells, below the "
                    f"{pack['size']}S1P design requirement for {pack['purpose_code']}; "
                    "release is refused."
                ),
                composition_as_of=fmt(removed_at),
            )
        elif kind == "no_change":
            maintenance_id, actor = add_maintenance(
                pack,
                "periodic_service",
                "Scheduled periodic service; no cell replacement is required.",
                "Clean terminals, check torque and insulation, and record a no-change service.",
                "completed",
                start,
            )
            if len([x for x in maintenance_rows if x["maintenance_type"] == "periodic_service"]) <= 2:
                inspected = start + minutes(rng.randint(50, 70))
                inspection = add_inspection(
                    pack,
                    inspected,
                    pack["initial_ended"],
                    "pass",
                    "Post-service check passed; the composition is unchanged since initial assembly.",
                    triggered_maintenance=maintenance_id,
                )
                add_release(
                    pack,
                    inspection,
                    inspected + minutes(rng.randint(10, 20)),
                    "allowed",
                    f"Post-service inspection {inspection['inspection_code']} passed; "
                    f"release for {pack['purpose_code']} is reconfirmed.",
                    composition_as_of=fmt(pack["initial_ended"]),
                )

    # reinstall case: maintenance removes a cell, a later standalone reassembly
    # job re-installs the same repaired cell (occurrence_no = 2).
    pack = by_no[REINSTALL_PACK]
    slot = "SLOT-02"
    old = active_install(pack, slot)
    maintenance_id, actor = add_maintenance(
        pack,
        "fault_repair",
        f"Cell at {slot} shows a connection fault and is removed for repair.",
        f"Remove the cell at {slot} and send it for repair; reinstall after return.",
        "completed",
        MAINT_BASE - minutes(20),
    )
    removed_at = MAINT_BASE + minutes(10)
    old["removed_at"] = fmt(removed_at)
    old["remove_reason"] = "removed_for_repair"
    old["removed_by_maintenance_id"] = maintenance_id
    reinstall_job, reinstall_end = add_job(
        pack,
        "reassembly",
        REINSTALL_JOB_START,
        rng.randint(30, 40),
        actor,
        None,
        f"Standalone reassembly: reinstall the repaired cell at {slot}.",
    )
    reinstall_member = {
        "unit_id": old["unit_id"],
        "assessment_id": old["assessment_id"],
        "position": slot,
    }
    add_install(
        pack,
        reinstall_member,
        reinstall_end,
        "reinstalled_after_repair",
        job_code=reinstall_job["job_code"],
        occurrence=2,
    )
    inspected = reinstall_end + minutes(rng.randint(20, 30))
    inspection = add_inspection(
        pack,
        inspected,
        reinstall_end,
        "pass",
        "Post-reinstallation acceptance check passed; the repaired cell is back in service.",
        triggered_job=reinstall_job["job_code"],
    )
    add_release(
        pack,
        inspection,
        inspected + minutes(rng.randint(10, 20)),
        "allowed",
        f"Reinstalled composition inspected as {inspection['inspection_code']}; "
        f"release for {pack['purpose_code']} is allowed.",
        composition_as_of=fmt(reinstall_end),
    )

    # in-progress maintenance at the snapshot: no member change is recorded yet
    pack = by_no[IN_PROGRESS_PACK]
    add_maintenance(
        pack,
        "fault_diagnosis",
        "Cell balance alarm reported during routine monitoring.",
        "Diagnosis in progress; no member change has been recorded at the data snapshot.",
        None,
        IN_PROGRESS_START,
    )
    pack["in_progress"] = True

    # ---- final pack statuses ---------------------------------------------
    for pack in packs:
        if pack.get("in_progress"):
            pack["final_status"] = "in_maintenance"
            pack["status_reason"] = (
                "Fault diagnosis is in progress at the data snapshot; no release applies "
                "to the current composition."
            )
            continue
        latest = pack["latest_release"]
        if latest is None:
            raise AssertionError(f"pack {pack['pack_no'] if 'pack_no' in pack else pack['no']} has no release")
        decision = latest["decision_result"]
        if decision == "deferred":
            pack["final_status"] = "pending_inspection"
            pack["status_reason"] = None
        elif decision == "allowed":
            if latest["use_restrictions"]:
                pack["final_status"] = "restricted"
                pack["status_reason"] = (
                    f"Release {latest['release_code']} carries use restrictions: "
                    "review before unrestricted service."
                )
            else:
                pack["final_status"] = "available"
                pack["status_reason"] = None
        elif decision == "rejected":
            if pack.get("removal_only"):
                if pack["no"] % 2 == 0:
                    pack["final_status"] = "retired"
                    pack["status_reason"] = (
                        "A cell was removed without replacement; the pack cannot meet its "
                        "purpose design and is retired from service."
                    )
                else:
                    pack["final_status"] = "restricted"
                    pack["status_reason"] = (
                        "Composition is below the purpose design after a removed cell; "
                        "restricted pending rework."
                    )
            elif pack["no"] == REMOVAL_ONLY_PACKS[1] or (
                pack["no"] in fail_nos and pack["no"] % 3 == 0
            ):
                pack["final_status"] = "retired"
                pack["status_reason"] = (
                    "Inspection failed and the pack is retired from the assessed service."
                )
            else:
                pack["final_status"] = "restricted"
                pack["status_reason"] = (
                    "Inspection failed; release is refused pending rework and re-inspection."
                )
        else:
            raise AssertionError(f"unknown decision {decision}")

    # ---- pack table rows --------------------------------------------------
    pack_rows = []
    for pack in packs:
        pack_rows.append(
            {
                "pack_id": pack["pack_id"],
                "pack_code": pack["pack_code"],
                "model_name": pack["model"],
                "formed_at": fmt(pack["initial_ended"]),
                "design_requirements": pack["design"],
                "nameplate_ratings": pack["nameplate"],
                "business_status": pack["final_status"],
                "status_reason": pack["status_reason"],
                "data_origin": "synthetic",
                "recorded_at": fmt(pack["initial_ended"] + minutes(10)),
                "source_ref": f"SIM-SRC-PACK-{pack['no']:04d}",
            }
        )

    data = {
        "BATTERY_PACK": pack_rows,
        "ASSEMBLY_JOB": job_rows,
        "MAINTENANCE_EVENT": maintenance_rows,
        "BATTERY_PACK_UNIT": install_rows,
        "PACK_INSPECTION": inspection_rows,
        "SERVICE_RELEASE": release_rows,
        "SERVICE_RELEASE_INSPECTION": [
            {"release_code": r, "inspection_code": i} for r, i in evidence_rows
        ],
        "lifecycle_event": lifecycle_rows,
    }

    context = {
        "packs": packs,
        "spare": spare,
        "initial_category": initial_category,
        "replacement_details": replacement_details,
        "pending_nos": pending_nos,
        "fail_nos": fail_nos,
        "observed_nos": observed_nos,
        "basis_version": basis_version,
        "method_version": method_version,
    }
    return data, context


# ---------------------------------------------------------------------------
# Validation of the generated data (before / after writing the DB)
# ---------------------------------------------------------------------------
def assert_timeline(rows, snapshot=SNAPSHOT):
    for table, columns in {
        "BATTERY_PACK": ["formed_at", "recorded_at"],
        "ASSEMBLY_JOB": ["started_at", "ended_at", "recorded_at"],
        "BATTERY_PACK_UNIT": ["joined_at", "removed_at", "recorded_at"],
        "PACK_INSPECTION": ["inspected_at", "composition_as_of", "recorded_at"],
        "SERVICE_RELEASE": ["decided_at", "composition_as_of", "recorded_at"],
    }.items():
        for row in rows[table]:
            for column in columns:
                value = row[column]
                if value is None:
                    continue
                if column == "removed_at" and value is None:
                    continue
                text = value
                if len(text) == 25 and text.endswith(TZ):
                    text = text[:19]
                if dt.datetime.fromisoformat(text) > snapshot:
                    raise AssertionError(
                        f"{table}.{column} after snapshot: {row[column]} > {fmt(snapshot)}"
                    )


def in_memory_checks(data, upstream, context):
    packs = context["packs"]
    if len(packs) != 160:
        raise AssertionError(f"expected 160 packs, got {len(packs)}")
    expected = {
        "BATTERY_PACK": 160,
        "BATTERY_PACK_UNIT": 653,
        "ASSEMBLY_JOB": 175,
        "MAINTENANCE_EVENT": 23,
        "PACK_INSPECTION": 175,
        "SERVICE_RELEASE": 179,
        "SERVICE_RELEASE_INSPECTION": 175,
        "lifecycle_event": 23,
    }
    for table, count in expected.items():
        actual = len(data[table])
        if actual != count:
            raise AssertionError(f"{table}: expected {count} rows, got {actual}")

    # unit uniqueness: a unit may appear in two install rows only when the
    # first one has been removed before the second one starts (reinstall case).
    by_unit = {}
    for row in data["BATTERY_PACK_UNIT"]:
        by_unit.setdefault(row["unit_id"], []).append(row)
    for unit_id, rows in by_unit.items():
        ordered = sorted(rows, key=lambda r: r["joined_at"])
        for prev, nxt in zip(ordered, ordered[1:]):
            if prev["removed_at"] is None or prev["removed_at"] > nxt["joined_at"]:
                raise AssertionError(f"overlapping installs for unit {unit_id}")
    reinstalled = [
        u for u, rows in by_unit.items()
        if len(rows) > 1 and any(r["occurrence_no"] > 1 for r in rows)
    ]
    if len(reinstalled) != 1:
        raise AssertionError(f"expected 1 reinstalled unit, got {len(reinstalled)}")

    # position uniqueness within a pack
    seen = {}
    for row in data["BATTERY_PACK_UNIT"]:
        key = (row["pack_id"], row["position_code"])
        for other in seen.get(key, []):
            if (row["joined_at"] < (other["removed_at"] or "9999")
                    and (row["removed_at"] or "9999") > other["joined_at"]):
                raise AssertionError(f"overlapping position {key}")
        seen.setdefault(key, []).append(row)

    # every install must point to a final second-life assessment
    for row in data["BATTERY_PACK_UNIT"]:
        info = upstream["unit_assessment"].get(row["unit_id"])
        if not info:
            raise AssertionError(f"unit {row['unit_id']} has no second-life assessment")
        aid, purpose, status = info
        if row["assessment_id"] != aid:
            raise AssertionError("install assessment mismatch")
        if status != "final" or not 1 <= purpose <= 9:
            raise AssertionError("install assessment is not assembly-usable")
        pack = next(p for p in packs if p["pack_id"] == row["pack_id"])
        if purpose != pack["purpose"]:
            raise AssertionError(
                f"pack {pack['pack_code']} mixes purpose {purpose} vs {pack['purpose']}"
            )

    # allowed releases must have evidence with the same pack/composition
    releases = {r["release_code"]: r for r in data["SERVICE_RELEASE"]}
    evidence = data["SERVICE_RELEASE_INSPECTION"]
    inspections = {i["inspection_code"]: i for i in data["PACK_INSPECTION"]}
    linked = {}
    for e in evidence:
        linked.setdefault(e["release_code"], []).append(inspections[e["inspection_code"]])
    for release in data["SERVICE_RELEASE"]:
        if release["decision_result"] == "allowed":
            if not linked.get(release["release_code"]):
                raise AssertionError(
                    f"allowed release without evidence: {release['release_code']}"
                )
            for inspection in linked[release["release_code"]]:
                if inspection["pack_id"] != release["pack_id"]:
                    raise AssertionError("evidence pack mismatch")
                if inspection["composition_as_of"] != release["composition_as_of"]:
                    raise AssertionError("evidence composition mismatch")
                if inspection["inspection_result"] not in ("pass", "pass_with_observation"):
                    raise AssertionError("allowed release relies on a failed inspection")
        if release["decision_result"] == "deferred":
            if not release["missing_evidence_reason"]:
                raise AssertionError("deferred release without missing reason")

    assert_timeline(data)
    print("[ok] in-memory checks passed")


# ---------------------------------------------------------------------------
# Writing the SQLite databases
# ---------------------------------------------------------------------------
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


def insert_rows(con, table, rows):
    if not rows:
        return
    columns = COLUMNS[table]
    placeholders = ",".join(["?"] * len(columns))
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
    con.executemany(sql, [tuple(row[c] for c in columns) for row in rows])


def write_integrated(data, seed: int):
    ensure_upstream()
    if OUT_INTEGRATED.exists():
        OUT_INTEGRATED.unlink()
    shutil.copy2(UPSTREAM_DB, OUT_INTEGRATED)
    con = sqlite3.connect(str(OUT_INTEGRATED))
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
        # Pack rows must exist before the shared lifecycle_event trigger fires.
        insert_rows(con, "BATTERY_PACK", data["BATTERY_PACK"])
        lifecycle_columns = LIFECYCLE_COLUMNS
        placeholders = ",".join(["?"] * len(lifecycle_columns))
        con.executemany(
            f"INSERT INTO lifecycle_event ({','.join(lifecycle_columns)}) "
            f"VALUES ({placeholders})",
            [tuple(row[c] for c in lifecycle_columns) for row in data["lifecycle_event"]],
        )
        insert_rows(con, "MAINTENANCE_EVENT", data["MAINTENANCE_EVENT"])
        insert_rows(con, "ASSEMBLY_JOB", data["ASSEMBLY_JOB"])
        insert_rows(con, "BATTERY_PACK_UNIT", data["BATTERY_PACK_UNIT"])
        insert_rows(con, "PACK_INSPECTION", data["PACK_INSPECTION"])
        insert_rows(con, "SERVICE_RELEASE", data["SERVICE_RELEASE"])
        insert_rows(
            con, "SERVICE_RELEASE_INSPECTION", data["SERVICE_RELEASE_INSPECTION"]
        )
        con.executescript(VIEWS_SQL.read_text(encoding="utf-8"))
        con.commit()
        run_db_checks(con, data)
        con.execute("VACUUM")
    finally:
        con.close()
    print(f"[ok] wrote {OUT_INTEGRATED.relative_to(ROOT)}")


def run_db_checks(con, data):
    fk = list(con.execute("PRAGMA foreign_key_check"))
    if fk:
        raise AssertionError(f"foreign_key_check found {len(fk)} rows: {fk[:5]}")
    expected = {table: len(rows) for table, rows in data.items() if table in COLUMNS}
    for table, count in expected.items():
        actual = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if actual != count:
            raise AssertionError(f"{table}: DB has {actual}, expected {count}")

    checks = {
        "pack rows missing purpose": """
            SELECT COUNT(*) FROM BATTERY_PACK p
            WHERE NOT EXISTS (SELECT 1 FROM SERVICE_RELEASE r WHERE r.pack_id = p.pack_id)
        """,
        "install assessment not final/usable": """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
            WHERE a.status <> 'final' OR a.final_purpose_id NOT BETWEEN 1 AND 9
               OR a.unit_id <> pu.unit_id
        """,
        "install unit in wrong-purpose pack": """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
            JOIN SERVICE_RELEASE r ON r.pack_id = pu.pack_id
            WHERE a.final_purpose_id <> r.purpose_id
        """,
        "allowed release without evidence": """
            SELECT COUNT(*) FROM V_PART4_ALLOWED_RELEASE_WITHOUT_EVIDENCE
        """,
        "deferred release without reason": """
            SELECT COUNT(*) FROM V_PART4_DEFERRED_RELEASE_WITHOUT_REASON
        """,
        "inspection composition empty": """
            SELECT COUNT(*) FROM V_PART4_INSPECTION_EMPTY_COMPOSITION
        """,
        "pack mixed purpose": """
            SELECT COUNT(*) FROM V_PART4_PACK_MIXED_PURPOSE
        """,
        "job maintenance different pack": """
            SELECT COUNT(*) FROM ASSEMBLY_JOB j
            JOIN MAINTENANCE_EVENT m ON m.maintenance_id = j.maintenance_id
            JOIN lifecycle_event e ON e.event_id = m.maintenance_id
            WHERE j.maintenance_id IS NOT NULL AND e.battery_pack_id <> j.pack_id
        """,
        "inspection trigger different pack": """
            SELECT COUNT(*) FROM PACK_INSPECTION i
            LEFT JOIN ASSEMBLY_JOB j ON j.job_code = i.triggered_by_job_code
            LEFT JOIN MAINTENANCE_EVENT m ON m.maintenance_id = i.triggered_by_maintenance_id
            LEFT JOIN lifecycle_event e ON e.event_id = m.maintenance_id
            WHERE (i.triggered_by_job_code IS NOT NULL AND j.pack_id <> i.pack_id)
               OR (i.triggered_by_maintenance_id IS NOT NULL AND e.battery_pack_id <> i.pack_id)
        """,
        "maintenance parent not pack maintenance": """
            SELECT COUNT(*) FROM MAINTENANCE_EVENT m
            JOIN lifecycle_event e ON e.event_id = m.maintenance_id
            WHERE e.event_type <> 'maintenance' OR e.battery_pack_id IS NULL
               OR e.battery_unit_id IS NOT NULL OR e.actor_org_id IS NULL
        """,
        "unit with overlapping active installs": """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT a
            JOIN BATTERY_PACK_UNIT b
              ON a.unit_id = b.unit_id AND a.pack_unit_id < b.pack_unit_id
            WHERE a.joined_at < COALESCE(b.removed_at, '9999-12-31T23:59:59+08:00')
              AND COALESCE(a.removed_at, '9999-12-31T23:59:59+08:00') > b.joined_at
        """,
        "draft or recycling units installed": """
            SELECT COUNT(*) FROM BATTERY_PACK_UNIT pu
            JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
            WHERE a.status <> 'final' OR a.final_purpose_id NOT BETWEEN 1 AND 9
        """,
    }
    for label, sql in checks.items():
        value = con.execute(sql).fetchone()[0]
        if value:
            raise AssertionError(f"check failed [{label}]: {value} rows")
    print("[ok] integrated database checks passed")


def write_own_db():
    if OUT_OWN.exists():
        OUT_OWN.unlink()
    shutil.copy2(OUT_INTEGRATED, OUT_OWN)
    con = sqlite3.connect(str(OUT_OWN))
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        views = [
            name
            for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'view'"
            )
        ]
        for name in views:
            con.execute(f'DROP VIEW IF EXISTS "{name}"')
        tables = [
            name
            for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            if not name.startswith("sqlite_")
        ]
        for name in tables:
            if name not in PART4_TABLES:
                con.execute(f'DROP TABLE IF EXISTS "{name}"')
        con.commit()
        remaining = [
            name
            for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        if sorted(remaining) != sorted(PART4_TABLES):
            raise AssertionError(f"unexpected tables in own DB: {remaining}")
        fk = list(con.execute("PRAGMA foreign_key_check"))
        expected_missing = {
            "battery_unit", "organization", "ELIGIBILITY_ASSESSMENT",
            "USE_PURPOSE", "lifecycle_event",
        }
        bad = [row for row in fk if row[2] not in expected_missing]
        if bad:
            raise AssertionError(f"unexpected FK violations in own DB: {bad[:5]}")
        con.execute("VACUUM")
    finally:
        con.close()
    print(f"[ok] wrote {OUT_OWN.relative_to(ROOT)} (7 Part 4 tables)")


def write_addon(data):
    rows = sorted(data["lifecycle_event"], key=lambda r: (r["occurred_at"], r["event_id"]))
    with open(OUT_ADDON_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(LIFECYCLE_COLUMNS)
        for row in rows:
            writer.writerow(["" if row[c] is None else row[c] for c in LIFECYCLE_COLUMNS])
    lines = [
        "-- 第四板块新增的共享生命周期事件（维护子类型）。",
        "-- 合库时在含第①板块 lifecycle_event 表的数据库中执行。",
        "BEGIN TRANSACTION;",
    ]
    for row in rows:
        values = ",".join(quote_sql(row[c]) for c in LIFECYCLE_COLUMNS)
        lines.append(
            f"INSERT INTO lifecycle_event ({','.join(LIFECYCLE_COLUMNS)}) VALUES ({values});"
        )
    lines.append("COMMIT;")
    OUT_ADDON_SQL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[ok] wrote {OUT_ADDON_CSV.relative_to(ROOT)} and {OUT_ADDON_SQL.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Previews (CSV + standalone HTML)
# ---------------------------------------------------------------------------
PREVIEW_ORDER = {
    "BATTERY_PACK": "ORDER BY pack_code",
    "BATTERY_PACK_UNIT": "ORDER BY pack_unit_id",
    "ASSEMBLY_JOB": "ORDER BY job_code",
    "MAINTENANCE_EVENT": "ORDER BY rowid",
    "PACK_INSPECTION": "ORDER BY inspection_code",
    "SERVICE_RELEASE": "ORDER BY release_code",
    "SERVICE_RELEASE_INSPECTION": "ORDER BY release_code, inspection_code",
}


def display(value):
    if value is None:
        return "NULL"
    return str(value)


def write_previews(con):
    OUT_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    previews = {}
    for table in PART4_TABLES:
        columns = COLUMNS[table]
        rows = con.execute(
            f"SELECT {','.join(columns)} FROM {table} {PREVIEW_ORDER[table]} LIMIT 10"
        ).fetchall()
        previews[table] = (columns, rows)
        with open(
            OUT_PREVIEW_DIR / f"{table}_10_rows.csv", "w", newline="", encoding="utf-8-sig"
        ) as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([display(v) for v in row])

    lifecycle_rows = con.execute(
        f"SELECT {','.join(LIFECYCLE_COLUMNS)} FROM lifecycle_event "
        "WHERE event_type = 'maintenance' ORDER BY occurred_at LIMIT 10"
    ).fetchall()
    with open(
        OUT_PREVIEW_DIR / "lifecycle_event_part4_addon_10_rows.csv",
        "w", newline="", encoding="utf-8-sig",
    ) as fh:
        writer = csv.writer(fh)
        writer.writerow(LIFECYCLE_COLUMNS)
        for row in lifecycle_rows:
            writer.writerow([display(v) for v in row])

    previews["LIFECYCLE"] = (LIFECYCLE_COLUMNS, lifecycle_rows)
    stats = {
        "BATTERY_PACK": con.execute("SELECT COUNT(*) FROM BATTERY_PACK").fetchone()[0],
        "BATTERY_PACK_UNIT": con.execute("SELECT COUNT(*) FROM BATTERY_PACK_UNIT").fetchone()[0],
        "ASSEMBLY_JOB": con.execute("SELECT COUNT(*) FROM ASSEMBLY_JOB").fetchone()[0],
        "MAINTENANCE_EVENT": con.execute("SELECT COUNT(*) FROM MAINTENANCE_EVENT").fetchone()[0],
        "PACK_INSPECTION": con.execute("SELECT COUNT(*) FROM PACK_INSPECTION").fetchone()[0],
        "SERVICE_RELEASE": con.execute("SELECT COUNT(*) FROM SERVICE_RELEASE").fetchone()[0],
        "SERVICE_RELEASE_INSPECTION": con.execute(
            "SELECT COUNT(*) FROM SERVICE_RELEASE_INSPECTION"
        ).fetchone()[0],
        "lifecycle_event_addon": con.execute(
            "SELECT COUNT(*) FROM lifecycle_event WHERE event_type = 'maintenance'"
        ).fetchone()[0],
    }
    status_rows = con.execute(
        "SELECT business_status, COUNT(*) FROM BATTERY_PACK GROUP BY 1 ORDER BY 1"
    ).fetchall()
    decision_rows = con.execute(
        "SELECT decision_result, COUNT(*) FROM SERVICE_RELEASE GROUP BY 1 ORDER BY 1"
    ).fetchall()
    purpose_rows = con.execute(
        """
        SELECT a.final_purpose_id,
               COUNT(DISTINCT p.pack_id) AS packs,
               COUNT(DISTINCT pu.unit_id) AS units
        FROM BATTERY_PACK p
        JOIN BATTERY_PACK_UNIT pu ON pu.pack_id = p.pack_id
        JOIN ELIGIBILITY_ASSESSMENT a ON a.assessment_id = pu.assessment_id
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    with open(
        OUT_PREVIEW_DIR / "summary_counts.csv", "w", newline="", encoding="utf-8-sig"
    ) as fh:
        writer = csv.writer(fh)
        writer.writerow(["item", "value", "count"])
        for table, count in stats.items():
            writer.writerow(["table", table, count])
        for status, count in status_rows:
            writer.writerow(["BATTERY_PACK.business_status", status, count])
        for decision, count in decision_rows:
            writer.writerow(["SERVICE_RELEASE.decision_result", decision, count])
        for purpose, packs, units in purpose_rows:
            writer.writerow([f"P{purpose:02d}", "packs", packs])
            writer.writerow([f"P{purpose:02d}", "distinct_units_ever_installed", units])

    write_html(previews, stats, status_rows, decision_rows, purpose_rows)
    print(f"[ok] wrote {OUT_PREVIEW_DIR.relative_to(ROOT)} and {OUT_HTML.relative_to(ROOT)}")


def write_html(previews, stats, status_rows, decision_rows, purpose_rows):
    css = """
    body{font:15px/1.6 system-ui,-apple-system,sans-serif;margin:0;background:#f4f6fa;color:#17253b}
    main{max-width:1450px;margin:auto;padding:32px}
    h1{font-size:30px;margin:0}h2{font-size:21px;color:#204b79;margin-top:0}
    section,.intro{background:white;border:1px solid #dbe2ec;border-radius:10px;padding:20px;margin:22px 0}
    .scroll{overflow:auto;max-height:620px}
    table{border-collapse:collapse;font-size:13px;width:max-content;min-width:100%}
    th,td{border:1px solid #dbe2ec;padding:8px 10px;text-align:left;vertical-align:top;
          min-width:110px;max-width:360px;overflow-wrap:anywhere}
    th{background:#edf3fa;position:sticky;top:0;white-space:nowrap}
    td{white-space:pre-wrap}tr:nth-child(even){background:#f8fafc}
    .null{color:#6c7380;font-style:italic}
    nav{line-height:2.1}small{color:#657188}
    .badge{display:inline-block;background:#edf3fa;border-radius:6px;padding:1px 7px;margin:0 6px 6px 0}
    """
    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Part 4 数据预览</title><style>", css, "</style><main>",
        "<h1>Part 4 · 组包与维护管理：七张自有表</h1>",
        "<p>SQLite 数据快照与逐表 10 行预览 · 模拟时间线截至 2026-11-20 11:20 (+08:00)</p>",
        "<div class='intro'>",
        "<p><strong>范围说明：Part 4 新增 7 张表。整合库共 23 张表，另 16 张属于 Part 1–3 上游；"
        "另提供只含 Part 4 七张表的合库提取文件与 <code>lifecycle_event</code> 增量 CSV。</p>",
        "<p>160 个电池组由第③板块 <code>status='final'</code> 且最终用途为 P01–P09 的 725 个单元中的 "
        "638 个组装而成，87 个合格单元保留为未组装备件池；250 个 draft 评估单元和 25 个 P10 拆解回收"
        "单元未参与组包。所有 Part 4 业务记录均为 <code>data_origin='synthetic'</code>。</p>",
        "<p>NULL 表示数据库空值。所有预览直接从成品库按主键导出，完整保留字段与内容。</p>",
        "<nav>",
    ]
    nav = ["<a href='#summary'>数据概览</a>"]
    for table in PART4_TABLES:
        nav.append(f" · <a href='#{table}'>{table}</a>")
    nav.append(" · <a href='#LIFECYCLE'>lifecycle_event 增量</a>")
    parts.extend(nav)
    parts.append("</nav></div>")

    # summary
    parts.append("<section id='summary'><h2>数据概览</h2><div class='scroll'><table>")
    parts.append("<thead><tr><th>对象</th><th>行数</th></tr></thead><tbody>")
    labels = {
        "BATTERY_PACK": "电池组 BATTERY_PACK",
        "BATTERY_PACK_UNIT": "成员安装 BATTERY_PACK_UNIT",
        "ASSEMBLY_JOB": "组装作业 ASSEMBLY_JOB",
        "MAINTENANCE_EVENT": "维护事件 MAINTENANCE_EVENT",
        "PACK_INSPECTION": "组级检查 PACK_INSPECTION",
        "SERVICE_RELEASE": "使用决定 SERVICE_RELEASE",
        "SERVICE_RELEASE_INSPECTION": "决定检查证据 SERVICE_RELEASE_INSPECTION",
        "lifecycle_event_addon": "共享事件增量 lifecycle_event",
    }
    for key, value in stats.items():
        parts.append(f"<tr><td>{labels.get(key, key)}</td><td>{value}</td></tr>")
    parts.append("</tbody></table></div>")
    parts.append("<p><strong>电池组业务状态：</strong>")
    parts.extend(f"<span class='badge'>{s} {c}</span>" for s, c in status_rows)
    parts.append("</p><p><strong>使用决定结果：</strong>")
    parts.extend(f"<span class='badge'>{d} {c}</span>" for d, c in decision_rows)
    parts.append("</p><div class='scroll'><table><thead><tr><th>用途</th><th>电池组数</th>"
                 "<th>已安装的不同单元数</th></tr></thead><tbody>")
    for purpose, packs, units in purpose_rows:
        parts.append(f"<tr><td>P{purpose:02d}</td><td>{packs}</td><td>{units}</td></tr>")
    parts.append("</tbody></table></div></section>")

    def render_table(table_id, title, columns, rows):
        out = [f"<section id='{table_id}'><h2>{title}</h2><div class='scroll'><table>"]
        out.append("<thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in columns) + "</tr></thead><tbody>")
        for row in rows:
            cells = []
            for value in row:
                if value is None:
                    cells.append("<td class='null'>NULL</td>")
                else:
                    cells.append(f"<td>{html.escape(str(value))}</td>")
            out.append("<tr>" + "".join(cells) + "</tr>")
        out.append("</tbody></table></div></section>")
        return "".join(out)

    for table in PART4_TABLES:
        columns, rows = previews[table]
        parts.append(render_table(table, f"{table} · 前 10 行", columns, rows))
    parts.append(render_table(
        "LIFECYCLE",
        "lifecycle_event 第四板块增量 · 前 10 行",
        LIFECYCLE_COLUMNS,
        previews["LIFECYCLE"],
    ))
    parts.append(
        "<section><h2>说明</h2><p>数据由 <code>scripts/generate_section4_data.py</code> "
        "在第三部分整合库之上确定性生成；完整字段、业务规则、校验结果与合库步骤见 "
        "<code>docs/2026-11-20_第四板块数据实现说明.md</code>。合成数据仅用于课程演示，"
        "不代表真实企业运行事实，也不是认证安全判定。</p></section>"
    )
    parts.append("</main></html>")
    OUT_HTML.write_text("".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED,
                        help="random seed (default: %(default)s)")
    parser.add_argument("--skip-html", action="store_true",
                        help="skip the standalone HTML preview")
    args = parser.parse_args(argv)

    upstream_path = ensure_upstream()
    print(f"[..] upstream: {upstream_path.relative_to(ROOT)}")
    upstream = load_upstream(upstream_path)

    usable = sum(len(v) for v in upstream["eligible"].values())
    print(
        f"[..] upstream: {upstream['battery_units']} units, "
        f"{upstream['assessments']} assessments, "
        f"{upstream['lifecycle_events']} lifecycle events, "
        f"{usable} second-life-assemblable units"
    )
    data, context = build_scenario(upstream, args.seed)
    in_memory_checks(data, upstream, context)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_integrated(data, args.seed)
    write_own_db()
    write_addon(data)
    con = sqlite3.connect(str(OUT_INTEGRATED))
    try:
        if args.skip_html:
            OUT_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        else:
            write_previews(con)
    finally:
        con.close()

    summary = {
        "integrated_db": str(OUT_INTEGRATED.relative_to(ROOT)),
        "own_tables_db": str(OUT_OWN.relative_to(ROOT)),
        "tables": {k: len(v) for k, v in data.items() if k in COLUMNS},
        "lifecycle_event_addon": len(data["lifecycle_event"]),
        "foreign_key_check": "ok",
        "seed": args.seed,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
