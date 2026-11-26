# IBA6151 Next Actions

**Current status:** Implementation phase — see [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)  
**Last updated:** 2026-11-26

> 执行层面的排期、门禁、WBS 与分工已迁移到 [开发流程、里程碑与分工](DEVELOPMENT_PLAN.md)。
> 本文件保留需求边界与后续实施积压，不再作为排期依据。

## Current collaboration stage

The current five-person assignment covers business analysis, data collection,
label/rule definitions, and local ER/EER models only. Database implementation is
outside this assignment. Module claims are recorded in the local 2026-10-15
assignment document; the user confirmed module-4 ownership on 2026-11-06.
Personal identifiers remain outside the repository. The first-review date is unconfirmed.

1. Asset registration and provenance: Organization, BatteryUnit, LifecycleEvent.
2. Diagnostics and data quality: DiagnosticTest and the measurement-data boundary.
3. Use-specific eligibility: EligibilityAssessment and AssessmentEvidence.
4. Pack assembly and maintenance: BatteryPack, BatteryPackUnit, MaintenanceEvent;
   current proposal adds AssemblyJob, PackInspection and ServiceRelease, pending review.
5. Storage projects and leasing: StorageProject, LeaseContract, LeaseContractItem.

Each owner supplies a business flow, source inventory with samples and gaps,
local ER/EER model with cardinalities/optionality, and label/business-rule definitions.
Module 1 maintains shared asset/organization definitions and the generic event model;
module 2 hands diagnostic evidence to module 3; module 3 coordinates intended uses
with module 5 and eligibility meaning with module 4. Modules 4 and 5 coordinate pack
availability, maintenance, rental and return events with module 1. Merge the models
using one common scenario, preserving proposed versus instructor-confirmed rules.

The group-facing document is
[五人分工说明](../../output/docx/电池护照项目_五人分工说明_2026-10-15.docx).
The following implementation milestones remain the longer-term project backlog.

## Immediate priority

2026-11-12 晚间对接使用 [Mermaid 合图工作稿](diagrams/module4_2026-11-06/第四部分合图工作稿.md)。逐项核对①②③⑤提供的记录、引用标识和适用条件，现场记录结论并修改对应图源。

The user confirmed instructor feedback that the entity set was insufficient, without
a required count. Use the [2026-11-06 module-4 requirements](2026-11-06_组包与维护需求说明.md) as the current
entry. The earlier [entity analysis](archive/2026-10/2026-10-16_组包与维护业务实体分析.md) is preserved as
source research, not a finished schema. Mainland China and public-data cell granularity
remain the evidence boundary. Current work is requirements and local conceptual design.

1. Review the completed [local Chen ER/EER v0.1 draft](2026-11-06_第四板块ER建模说明.md):
   four views, editable draw.io, selected graphical attributes and a full conceptual dictionary.
   Retain pack, membership occurrence and actual maintenance; propose assembly work,
   pack inspection and business-use decisions. Do not count associative entities,
   subtypes and eventual tables as interchangeable. The draft is not group-approved.
2. Confirm application/product/scale with modules 3 and 5. Agree the intended-use references,
   member eligibility conditions, maintenance/leasing transitions and decision validity.
3. Coordinate shared identities/events with module 1 and pack-inspection evidence with
   module 2. Decide whether independent service decisions are required; specification,
   configuration and maintenance-work-order entities remain conditional.
4. Finish a source inventory and coherent synthetic assembly/maintenance examples.
   Preserve historical membership and locate every inspection/decision to its actual composition.
5. Use the v0.1 draft to resolve Q01–Q11, then revise identifiers, cardinalities,
   optionality and temporal rules. Explicitly finish ownership and eligibility-evidence
   interfaces, merge neighboring models, and record accepted/adjusted/deferred outcomes.
   No DDL is part of this assignment.

## Later implementation backlog

1. **Prepare the implementation platform.** PostgreSQL is locked; next verify whether it is already installed, select a supported local version, and document the repeatable setup without exposing credentials.
2. **Review the conceptual model.** The historical [2026-10-14 discussion draft](archive/2026-10/2026-10-14_教师讨论材料.md) supplies the initial full-group rules R01–R12. Reconcile them with the current module-4 requirements and neighboring modules; do not finalize the old twelve-object drawing unchanged. Record instructor/group accepted/adjusted/deferred outcomes, then finalize cardinalities, optionality and the data dictionary before DDL.
3. **Define the data-import boundary.** Map the 20 source CSV files into `BatteryUnit`, `DiagnosticTest`, and technical `DiagnosticMeasurement` staging records.
4. **Create curve summaries.** Derive transparent fields such as duration, start/end voltage, minimum/maximum voltage, observation count, and data-quality status.
5. **Specify eligibility rules.** Use a documented classroom rule plus tester approval; do not label it as certified safety screening.
6. **Design the logical schema.** Map the ER/EER model to relations, identify candidate keys, normalize to 3NF, and document functional dependencies where useful.
7. **Implement integrity controls.** At minimum prevent missing provenance, unassessed leasing, invalid lifecycle transitions, duplicate unit membership, and overlapping active leases.
8. **Generate synthetic operations.** Create small, coherent organization, pack, project, contract, maintenance, return, and disposition records with `data_origin = synthetic`.
9. **Build the demonstration queries.** Include asset traceability, eligibility inventory, project allocation, active leases, maintenance due, lifecycle history, utilization, and quality-warning queries.
10. **Prepare the English topic proposal.** Summarize context, novelty, scope, data feasibility, conceptual direction, expected implementation, and limitations.

## Recommended delivery sequence

### Milestone 1 — Requirements and conceptual design

- Actors, use cases, and business rules
- ER/EER diagram
- Data dictionary draft
- Public/synthetic provenance policy

### Milestone 2 — Logical design and implementation

- Relational schema and normalization notes
- PostgreSQL DDL
- Import/transform scripts
- Constraints, views, transactions, and indexes
- Synthetic data generator

### Milestone 3 — Verification and course deliverables

- SQL test cases and expected results
- Data-quality and integrity checks
- Representative analysis and discussion
- English final report
- Presentation deck and Q&A rehearsal
- Contribution evidence and role log

## Exit and revision conditions

- If the public dataset cannot be re-imported reproducibly, stop implementation and repair provenance/import before building presentation materials.
- If curve-only data cannot support a defensible automatic eligibility threshold, retain eligibility as a documented tester decision with data-quality evidence; do not invent a scientific model.
- If entity identification exceeds the original roughly twelve-entity target, review workflow scope, reuse and duplication before finalizing the model. Do not discard necessary business facts merely to preserve the initial count; the 2026-11-06 requirements and entity set remain proposals until reviewed.
- Optional analytics or additional datasets may begin only after the core database, constraints, and demonstration queries pass verification.

## Still needed from the group

- Confirm any changes to the recorded module claims and agree the first review/merge dates
- Keep member names and student IDs in the local assignment and contribution documents
- Record acceptance or revision of module-4 requirements Q01–Q11
- Instructor/LMS confirmation of the exact submission and presentation dates
