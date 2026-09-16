# Battery Passport and Second-Life Eligibility Leasing Database

> A relational database design and implementation for small energy-storage operators.
> IBA6151 Database Management — group project. Implementation DBMS: **PostgreSQL**.
>
> 面向小型储能运营商的电池护照与二次利用资格租赁数据库设计。IBA6151《数据库管理》小组课程项目。

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
data/
  README.md                              # provenance, license, coverage
  raw/                                   # public curves (git-ignored, local only)
docs/
  PROJECT_CONTEXT.md                     # scope, users, MVP boundary
  DBMS_CLASSIFICATION.md                 # course classification rationale
  DATA_AUDIT.md                          # acquisition and quality checks
  DECISIONS.md                           # locked design decisions
  NEXT.md                                # next actions and milestone sequence
scripts/
  validate_public_battery_data.py        # reproducible dataset validator
```

---

## Design and MVP scope | 设计与 MVP 范围

- **Core model (~10–12 tables):** `Organization`, `BatteryUnit`, `DiagnosticTest`,
  `EligibilityAssessment`, `BatteryPack`, `BatteryPackUnit`, `StorageProject`, `LeaseContract`,
  `LeaseContractItem`, `MaintenanceEvent`, `LifecycleEvent`.
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
