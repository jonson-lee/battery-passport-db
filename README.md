# Battery Passport and Second-Life Eligibility Leasing Database

> A relational database design and implementation for small energy-storage operators.
> IBA6151 Database Management — group project. Implementation DBMS: **PostgreSQL**.
>
> 面向小型储能运营商的电池护照与二次利用资格租赁数据库设计。IBA6151《数据库管理》小组课程项目。

**Status (2026-11-26) | 当前状态** — Conceptual design and all five module data snapshots are complete.
The final integrated database (`data/final/IBA6151_Integrated.sqlite`) contains **27 tables, 14 views,
44 triggers and 59 indexes**. PostgreSQL implementation is the active engineering track; see the
[development plan, milestones and work division](docs/DEVELOPMENT_PLAN.md). The SQLite snapshots remain
the data-stage handover and the demo fallback if the PostgreSQL port misses its 2026-11-30 gate.

> 概念设计与五个板块的数据快照已完成，全组合库为 27 表 / 14 视图 / 44 触发器。PostgreSQL 实施是当前主线，
> 排期与分工见[开发计划](docs/DEVELOPMENT_PLAN.md)；SQLite 快照保留为数据阶段交接物与演示兜底。

---

## Overview | 项目概述

**EN** — Small energy-storage operators and second-life battery companies need a traceable system of
record that answers four linked questions: (1) what battery unit is this and where did its data come
from; (2) what diagnostic evidence is available and is the unit eligible for a proposed second-life
use; (3) which units or packs are assigned or leased to which storage project; (4) what maintenance,
return, transfer, and end-of-life events have occurred. The database supports these decisions; it does
not replace certified safety testing or regulatory approval.

**中文** — 小型储能运营商与梯次利用企业需要一套可追溯的系统记录，回答四个相互关联的问题：电池单元
身份与数据来源、诊断证据与二次利用资格、单元/电池组归属或租赁给哪个储能项目、以及维护/返还/转移/
报废等生命周期事件。数据库用于支撑上述决策，**不替代**认证安全测试或监管审批。

**Course-based classification | 课程口径分类:** centralized · multiuser workgroup · operational · relational.

---

## Data and evidence boundary | 数据与证据边界

- **Primary public dataset:** *Battery Characterization Datasets — Charge/Discharge Voltage Curves*
  (<https://github.com/BulyK47/battery-datasets>), license **CC BY 4.0**.
- **Verified coverage:** 10 LiFePO4 battery units (`BATT_001`–`BATT_010`), 20 CSV files
  (10 charge + 10 discharge), 60 timestamp–voltage curves, 703,657 non-null measurement pairs.
- **Provenance:** imported records are cell/unit-level measurements, not real enterprise pack
  telemetry. Pack assembly, assignment, leasing, maintenance, transfer, and recycling events are
  **synthetic** and must carry `data_origin = synthetic`.
- **Raw data is not committed.** See `data/README.md` and `docs/DATA_AUDIT.md`.

> 公开数据为电芯级充放电电压曲线（CC BY 4.0）；机组装配、租赁、运维等操作数据为合成数据并标注
> `data_origin = synthetic`；原始数据不入库，详见 `data/README.md` 与 `docs/DATA_AUDIT.md`。

---

## Repository structure | 仓库结构

```
.
├── README.md                     # this file
├── requirements.txt
├── .env.example                  # connection template (no credentials)
├── docs/
│   ├── DEVELOPMENT_PLAN.md       # workflow, milestones, gates, work division
│   ├── README.md                 # document index
│   ├── PROJECT_CONTEXT.md        # scope, users, MVP boundary
│   ├── DBMS_CLASSIFICATION.md    # course classification and DBMS rationale
│   ├── DATA_AUDIT.md             # acquisition and quality checks
│   ├── DECISIONS.md              # locked design decisions
│   ├── NEXT.md                   # requirements and implementation backlog
│   ├── 2026-11-*.md              # module-4 ER, requirements, relational, data notes
│   ├── diagrams/                 # module-4 ER/EER sources and merge draft
│   └── archive/2026-10/          # historical discussion and source analysis
├── sql/
│   ├── section4_*.sql            # SQLite data-stage DDL, views, event add-on
│   └── postgres/                 # PostgreSQL implementation (see plan)
├── scripts/
│   ├── validate_public_battery_data.py
│   ├── generate_section4_data.py
│   ├── validate_section4_data.py
│   └── merge_section4_data.py
└── data/
    ├── README.md                 # provenance, license, snapshots
    ├── raw/                      # public curves (git-ignored, local only)
    ├── section1|2|4_*.sqlite     # module data snapshots
    ├── section4_previews/        # per-table 10-row previews
    └── final/                    # integrated 27-table database + ERD + system report
```

---

## Design and MVP scope | 设计与 MVP 范围

- **Historical starting model (entity count under review):** `Organization`, `BatteryUnit`, `DiagnosticTest`,
  `EligibilityAssessment`, `BatteryPack`, `BatteryPackUnit`, `StorageProject`, `LeaseContract`,
  `LeaseContractItem`, `MaintenanceEvent`, `LifecycleEvent`.
- **2026-10-14 proposal (pending instructor review):** add `AssessmentEvidence` for
  a 12-entity model and treat `MaintenanceEvent` as a `LifecycleEvent` subtype.
  See [教师讨论材料：ER/EER 草图与待确认规则](docs/archive/2026-10/2026-10-14_教师讨论材料.md).
- **2026-10-16 historical review:** mainland China is the confirmed business jurisdiction.
  Identify entities before relationships and EER; the original entity count is a
  scope target, not proof of business completeness. See
  [历史组包与维护业务实体分析](docs/archive/2026-10/2026-10-16_组包与维护业务实体分析.md)
  for industry sources and the LN3–LN5 review of entities, attributes, relationships
  and associative structures. The earlier blanket nine-core-candidate classification
  is withdrawn. The revised inventory has not replaced the draft schema.
- **2026-11-06 current module-4 proposal:** the user confirmed instructor feedback that
  the entity set was insufficient; the meeting date and a required count were not specified.
  [组包与维护需求说明](docs/2026-11-06_组包与维护需求说明.md) proposes retaining pack, membership and maintenance,
  and adding actual assembly work, pack inspection and a business-use decision. These are
  six business-object categories including an associative entity and a proposed event subtype,
  not six ordinary entities or an approved project-wide count. Specification, configuration
  and work orders remain conditional. See [文档索引](docs/README.md) for current and historical sources.
- **2026-11-06 module-4 conceptual draft:** [Chen ER/EER v0.1 and dictionary](docs/2026-11-06_第四板块ER建模说明.md)
  now provide four diagram views and editable draw.io. Source XOR, temporal composition,
  inspection evidence and maintenance inheritance are explicit review proposals;
  cross-module ownership and eligibility-evidence links still need merge review.
- **High-volume measurements:** loaded into a technical/staging table (e.g. `DiagnosticMeasurement`)
  and summarized into `DiagnosticTest`.
- **Design flow:** requirement analysis → ER/EER → logical mapping to 3NF → PostgreSQL DDL with keys,
  FKs, checks, uniqueness, and documented indexes → reproducible import with provenance → demo
  queries and at least one transaction/concurrency scenario.
- **Out of scope:** blockchain, real payments/ROI, cross-border supply-chain optimization, a full
  compliance engine, or ML-heavy battery prognosis.

---

## Setup and reproducibility | 环境与复现

```powershell
python -m pip install -r requirements.txt
python .\scripts\validate_public_battery_data.py
# optional compact output (summary only)
python .\scripts\validate_public_battery_data.py --summary-only
```

The validator is read-only over the source CSVs and prints a JSON report. By default it reads
`data/raw/battery_charge_discharge_curves/csv/`; pass another directory as the first argument to
override.

> 验证脚本只读源数据并输出 JSON 报告，默认读取 `data/raw/battery_charge_discharge_curves/csv/`。

---

## Milestones | 里程碑

1. **Requirements & conceptual design** — actors, use cases, business rules, ER/EER, data dictionary,
   public/synthetic provenance policy.
2. **Logical design & implementation** — relational schema, normalization notes, PostgreSQL DDL,
   import/transform scripts, constraints/views/transactions/indexes, synthetic data generator.
3. **Verification & deliverables** — SQL test cases, integrity and data-quality checks, representative
   analysis, English report, presentation deck.

> Execution-level dates, gates, task breakdown and ownership: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)
> (frozen 2026-11-26; PostgreSQL gate on 2026-11-30, code freeze on 2026-12-06).

---

## Limitations | 局限

- The public measurements are cell-level, not real pack-level operating records.
- Synthetic records must never be presented as real company observations.
- Eligibility rules are classroom demonstration rules, not certified safety determinations.
- Conclusions concern database traceability and workflow support, not commercial performance.

> 公开数据为电芯级测量；合成记录不得当作真实企业数据；资格规则为课堂演示规则，非认证安全判定。

---

## Team | 团队

Group coursework project. Member names and student IDs are intentionally omitted from this repository;
the focus is on the project itself.

> 小组课程项目。为保护隐私，仓库不包含成员姓名与学号，内容仅聚焦项目本身。

## Acknowledgements | 致谢

Battery Characterization Datasets (CC BY 4.0, BulyK47/battery-datasets); built for the IBA6151 course.
