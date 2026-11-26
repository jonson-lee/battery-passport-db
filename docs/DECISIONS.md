# IBA6151 Project Decisions

**Last updated:** 2026-11-06

## D-001 — Project direction

**Decision:** Build a battery passport and second-life eligibility leasing database for small energy-storage operators.  
**Status:** Accepted.  
**Reason:** It is novel enough for the presentation rubric while still offering a clear relational workflow involving assets, tests, assessments, assignments, contracts, maintenance, and lifecycle events.

## D-002 — Small and solid MVP

**Decision:** Limit the project to one end-to-end second-life workflow. The initial
approximately 10–12 core-business-table estimate is historical, not a current ceiling.  
**Status:** Workflow scope accepted; numerical estimate reopened on 2026-11-06
following user-confirmed instructor feedback that the entity set was insufficient.  
**Excluded:** manufacturing provenance, full vehicle telemetry, blockchain, real payments, cross-border logistics, and a full regulatory engine.  
**Reason:** The course rewards reliable database design and execution; excessive domain scope would weaken conceptual and logical depth.

## D-003 — Primary customer and roles

**Decision:** The principal customer is a small energy-storage operator or second-life battery company. Supporting roles are asset administrator, tester, operations staff, and auditor/compliance reviewer.  
**Status:** Accepted.

## D-004 — Hybrid data strategy

**Decision:** Use public experimental data for technical battery-unit and diagnostic records, and explicitly labelled synthetic data for organizations, packs, projects, leases, maintenance, transfer, return, and recycling/disposition events.  
**Status:** Accepted.  
**Rule:** Synthetic operational records must never be described as real company observations.

## D-005 — Primary technical data source

**Decision:** Use the public `BulyK47/battery-datasets` charge/discharge voltage-curve dataset as the primary technical source.  
**Status:** Accepted after successful local acquisition and validation.  
**Evidence:** 20 CSV files, 10 battery units, 60 curves, 703,657 non-null measurements, CC BY 4.0.  
**Reason:** It is directly downloadable without login, modest in size, documented, attributable, and closely connected to screening retired lithium-ion batteries.

## D-006 — Entity granularity and terminology

**Decision:** Model imported measured assets as `BatteryUnit`/cell-level records. Model battery-pack assembly and pack-level operations synthetically.  
**Status:** Accepted.  
**Reason:** The public source contains cell-level experimental curves; calling them observed enterprise packs would overstate the evidence.

## D-007 — Raw measurements versus core business schema

**Decision:** Store the high-volume timestamp-voltage points in a technical/staging table and store curve-level summaries in the core diagnostic tables.  
**Status:** Accepted as the implementation baseline.  
**Reason:** This supports import, aggregation, indexing, and data-quality demonstrations without allowing a 703,657-row measurement table to dominate the business ER model.

## D-008 — Eligibility claims

**Decision:** Eligibility will be represented as a transparent rule-based or tester-approved database decision: `eligible`, `conditional`, or `rejected`.  
**Status:** Accepted.  
**Boundary:** It is not a certified safety assessment and will not be presented as a universal electrochemical or regulatory standard.

## D-009 — Analytics boundary

**Decision:** Possible analysis is secondary to database design. Use descriptive summaries, quality checks, utilization views, lifecycle queries, and eligibility counts. Do not turn the project into a neural-network or model-comparison exercise.  
**Status:** Accepted.

## D-010 — Grill Me outcome

**Decision:** **Go.**  
**Date:** 2026-09-12.  
**Conditions:** Maintain strict public-versus-synthetic provenance; keep the real-data claim at cell level; include the detected quality warning; demonstrate one complete workflow before adding optional features.

## D-011 — External actions

**Decision:** Do not upload, publish, or submit project files or data to any external platform without explicit authorization.  
**Status:** Locked.

## D-012 — Implementation DBMS

**Decision:** Use PostgreSQL as the implementation database.  
**Status:** Accepted on 2026-09-12.  
**Course classification:** The implemented system is a centralized, multiuser workgroup, operational, relational database.  
**Reason:** PostgreSQL fits all four characteristics and supports the required client/server multiuser workflow, structured relational model, operational transactions, constraints, indexes, and views. The course classification justifies choosing a relational operational DBMS rather than a data warehouse, distributed NoSQL platform, or primarily personal/embedded database. It does not by itself distinguish PostgreSQL from MySQL: both fit the same course categories. PostgreSQL is preferred within that category because partial indexes, range types, and exclusion constraints make project-specific rules such as preventing overlapping active battery leases more direct and declarative. SQLite is retained only as a possible lightweight prototyping tool, not the submitted implementation database.

## D-013 — Target group size

**Decision:** Form a five-person group. At the 2026-09-12 planning stage the project
had one member and planned to recruit four others. This is a historical recruitment note;
the 2026-10-15 local assignment document now records business-module claims.  
**Status:** Accepted on 2026-09-12.  
**Reason:** Official course materials require 5–6 persons per group; five members meet the requirement while keeping coordination manageable.

## D-014 — Business jurisdiction and entity-review sequence

**Decision:** Use mainland China as the business jurisdiction and review business
entities before deciding relationships and EER notation.

**Status:** Confirmed by the user on 2026-10-16.

**Boundary:** This does not establish a particular permitted storage application or
approve the proposed entity inventory. The existing cell-level public-data boundary
remains in force.

## D-015 — Recorded instructor feedback and module-4 ownership

**Recorded on:** 2026-11-06.  
**Confirmed by the user:** The user owns module 4 in the local five-person assignment.
The instructor said the entity set was insufficient. The consultation date and required
number were not specified; no item-by-item approval of candidate entities was supplied.

**Boundary:** This confirms the feedback and personal module, not the six-object proposal.
Personal identifiers remain outside repository documentation.

## D-016 — Document organization

**Action:** On 2026-11-06, organize superseded discussion entries under
`docs/archive/2026-10/` and their HTML/PDF exports under the sibling project
`output/archive/2026-10/`, with corrected editable links. Preserve source analysis,
the local assignment original, data audit, course rationale and existing project work.
No business files are deleted. The current entry is [module-4 requirements](2026-11-06_组包与维护需求说明.md).

## D-017 — Module-4 local conceptual draft

**Action on 2026-11-06:** Following the user's request to advance their assigned ER
diagram, prepare the [module-4 Chen ER/EER v0.1 review package](2026-11-06_第四板块ER建模说明.md):
core relationships, membership-change provenance, selected attributes, shared boundaries
and maintenance inheritance, plus editable draw.io and a conceptual dictionary.

**Status:** Local draft produced; no group/instructor acceptance is inferred.
Identifiers, cardinalities, time rules and shared interfaces remain proposals.
No logical schema, DDL, data import, external upload or submission is included.

**阅读与标注约定（2026-11-06 用户要求）：** 第四板块图稿采用中文名在前、英文标识在后的双语实体和属性标签，联系及说明统一用中文；配套建模说明也使用中文。此轮只调整呈现语言，不改变实体数量或模型规则。

2026-11-12 起，第四板块组内讨论用 Mermaid 代码块维护关系图。按共享实体的英文标识合并，待定接口及会议结论记录在工作稿中。[合图工作稿](diagrams/module4_2026-11-06/第四部分合图工作稿.md)

## Open decisions

- **2026-11-06 module-4 proposal:** Review the [new requirements](2026-11-06_组包与维护需求说明.md).
  Retain pack, membership and maintenance; propose actual assembly, pack inspection
  and business-use decisions. New entities, cardinalities, temporal rules and event
  inheritance remain proposals. Specification/configuration/work-order entities stay
  conditional. The old 12-object drawing is not the current module-4 model.

- **2026-10-16 entity review:** Review the
  [module-4 industry and entity analysis](archive/2026-10/2026-10-16_组包与维护业务实体分析.md),
  revised against LN3–LN5 to separate entities, attributes, relationships and
  associative structures. The earlier nine-core-candidate classification is
  withdrawn: IDs, history and future separate tables do not by themselves establish
  an entity type. The revised classifications remain modeling recommendations,
  not an accepted schema. Revisit the D-002 entity-count target where needed
  to preserve necessary business facts; the narrow workflow scope still applies.
- **2026-10-14 instructor-review proposal:** adopt 12 core entities by adding
  `AssessmentEvidence`; model `MaintenanceEvent` as a `LifecycleEvent` subtype.
  Organization roles, evidence requirements, temporal membership/lease rules,
  event targets, and maintenance transitions remain pending instructor confirmation.
  See [discussion draft](archive/2026-10/2026-10-14_教师讨论材料.md), R01–R12; no new accepted decision is implied.

- Final eligibility thresholds and whether the tester may override them.
- Confirm any changes to recorded module claims and the next group review date;
  names and student IDs are maintained outside the repository.
- Official presentation/report deadline to use when course documents conflict.
