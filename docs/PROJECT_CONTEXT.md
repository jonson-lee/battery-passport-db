# IBA6151 Group Project Context

**Status:** Go — topic and evidence boundary locked  
**Last updated:** 2026-11-06
**Course:** IBA6151 Database Management, Fall 2026

**Implementation DBMS:** PostgreSQL

**Course-based database classification:** Centralized, multiuser workgroup, operational, relational database

## Working title

**Battery Passport and Second-Life Eligibility Leasing System for Small Energy-Storage Operators**

## Course fit

The project is a relational database design and implementation project. It will explicitly cover the five areas required by the course:

1. business context and requirement analysis;
2. conceptual design using ER/EER models;
3. logical design and relational mapping;
4. database implementation, constraints, transactions, and indexing;
5. discussion of data use and possible analysis.

Novelty will come from the second-life battery passport and eligibility-leasing workflow. The project will remain small enough to demonstrate one complete, reliable database workflow rather than becoming a broad battery-industry platform.

## Database classification from Lecture 1

Lecture 1 classifies databases by number of users, location, and type of use, and separately distinguishes database models. Under that framework, the proposed system is:

| Course dimension | Selected type | Project justification |
|---|---|---|
| Number of users | Multiuser - workgroup database | Asset administrators, testers, operations staff, operators, and auditors use the same database. The bounded small-operator context is a workgroup rather than an enterprise-wide deployment. |
| Location | Centralized database | The MVP uses one logical PostgreSQL database instance as the system of record. Multiple clients do not make the data distributed. |
| Type of use | Operational database | The core workload records current assets, assessments, assignments, leases, maintenance, returns, and lifecycle events. Analytical summaries are secondary. |
| Data model | Relational database model | The domain has stable structured entities, primary/foreign-key relationships, many-to-many bridge tables, and integrity constraints. |

The MVP is not a data warehouse, distributed database, cloud database, or NoSQL system. Those are possible future architectures, not requirements for the present business problem.

## Business problem

Small energy-storage operators and second-life battery companies need to answer four linked questions:

1. What battery unit is this, and where did its data come from?
2. What diagnostic evidence is available, and is the unit eligible for a proposed second-life use?
3. Which units or assembled packs are currently assigned or leased to which storage project?
4. What maintenance, return, transfer, and end-of-life events have occurred?

The database will provide a traceable system of record for those decisions. It will not claim to replace certified safety testing or regulatory approval.

## Primary users

- Asset administrator: registers organizations, battery units, and packs.
- Laboratory tester: imports diagnostic results and records data-quality flags.
- Operations staff: assigns eligible assets, creates leases, and records maintenance or return events.
- Small energy-storage operator: views allocated assets and contract status.
- Auditor/compliance reviewer: inspects provenance, assessments, and lifecycle history.

## Locked MVP scope

The MVP will support:

- organization and battery-unit registration;
- import of public charge/discharge diagnostic curves;
- diagnostic summaries and explicit data-quality flags;
- eligibility decisions of `eligible`, `conditional`, or `rejected`;
- synthetic pack assembly from battery units;
- assignment of packs to a small energy-storage project;
- lease creation and status tracking;
- maintenance, return, transfer, and disposition events;
- an auditable lifecycle-event history.

The MVP will not include:

- manufacturing raw-material provenance;
- vehicle telemetry ingestion;
- blockchain or distributed ledgers;
- real payments, profitability, or ROI calculations;
- cross-border supply-chain optimization;
- a full China/EU compliance engine;
- a machine-learning-heavy battery prognosis product.

## Proposed relational boundary

The initial business-model draft targeted approximately 10–12 tables:

- `Organization`
- `BatteryUnit`
- `DiagnosticTest`
- `EligibilityAssessment`
- `BatteryPack`
- `BatteryPackUnit`
- `StorageProject`
- `LeaseContract`
- `LeaseContractItem`
- `MaintenanceEvent`
- `LifecycleEvent`

**2026-10-14 conceptual-design proposal (pending instructor review):** Add
`AssessmentEvidence` as the twelfth core entity to link assessments and diagnostic tests.
Model `MaintenanceEvent` as a partial subtype of `LifecycleEvent`, with a shared event key.
The proposed cardinalities, optionality, organization roles, asset-target XOR, and
state-dependent requirements are documented in
[the instructor discussion draft](archive/2026-10/2026-10-14_教师讨论材料.md), rules R01–R12.
These are recommendations, not approved business rules or implemented constraints.

**2026-10-16 business-analysis update:** The user confirmed mainland China as the
business jurisdiction and requested entity identification from industry workflows
before deciding relationships or EER notation. The
[pack assembly and maintenance entity analysis](archive/2026-10/2026-10-16_组包与维护业务实体分析.md)
has been reviewed against LN3–LN5 to distinguish entities, attributes, relationships
and associative structures. The earlier blanket classification of nine core entity
candidates is withdrawn. Pack identity and actual maintenance records remain entity
candidates; membership is reviewed as an attributed relationship/associative entity.
Specifications, configurations, jobs, inspections, release decisions and work orders
require separate requirement and classification checks. This is not an accepted
schema or a completed relationship model. The earlier entity-count target must
not remove necessary business facts. The existing `BatteryUnit` cell-level evidence
boundary remains in force. Mainland application eligibility requires a specific
product/use/scale review against current requirements; “small energy storage” alone
does not establish a permitted use. See the analysis for the verified 2026 policy
changes and source boundaries.

**2026-11-06 current module-4 requirements proposal:** The user confirmed ownership
of module 4 against the local assignment document and reported instructor feedback that
the entity set was insufficient. No consultation date, required count, or item-by-item
approval was provided. The [current requirements](2026-11-06_组包与维护需求说明.md) propose retaining `BatteryPack`,
`BatteryPackUnit` (membership occurrence / associative entity), and `MaintenanceEvent`,
and adding `AssemblyJob`, `PackInspection`, and `ServiceRelease`. The additions are
requirements proposals, not accepted schema changes. Specification attributes and
temporal membership remain the initial representation for specifications and composition;
separate specifications, configuration versions and maintenance work orders are deferred.
Inspection must be coordinated with module 2; purpose and leasing rules with modules 3
and 5; shared identity and event semantics with module 1. A four-view
[module-4 Chen ER/EER v0.1 review draft](2026-11-06_第四板块ER建模说明.md) is now available,
with editable diagrams, identifiers, a conceptual attribute dictionary and explicit
temporal/source rules. It is a proposed local model, not an approved merged schema;
ownership and eligibility-evidence interfaces still need neighboring-module review.
No DDL is included. The historical 10–12 count is not a current ceiling.

High-volume public measurements will be loaded into a separate technical/staging table such as `DiagnosticMeasurement`, then summarized into `DiagnosticTest`. This keeps the conceptual business model focused while still demonstrating realistic ingestion, indexing, and aggregation.

## Data and evidence boundary

The primary public source contains measured cell-level charge/discharge curves. Therefore:

- imported real records will be described as battery cells or battery units, not real enterprise battery packs;
- pack assembly and leasing/maintenance/transfer/recycling events will be synthetic;
- every imported or generated row must carry provenance, such as `data_origin = public_experimental` or `data_origin = synthetic`;
- synthetic records must never be presented as observations from a real company;
- any eligibility rule is a database demonstration rule, not a certified safety determination;
- conclusions will concern database traceability and workflow support, not the commercial performance of a real battery-leasing business.

## Primary public dataset

**Battery Characterization Datasets — Charge/Discharge Voltage Curves**  
Repository: <https://github.com/BulyK47/battery-datasets>  
Dataset folder: <https://github.com/BulyK47/battery-datasets/tree/main/charge-discharge-voltage-curves>  
License: CC BY 4.0

Verified local coverage:

- 10 LiFePO4 battery units (`BATT_001`–`BATT_010`);
- 20 CSV files: 10 charge and 10 discharge;
- 60 timestamp-voltage curves;
- 703,657 non-null measurement pairs;
- complete source README, citation metadata, and license.

See `docs/DATA_AUDIT.md` for the acquisition and quality checks.

## Success criteria

The project is successful if it delivers:

1. a defensible requirement analysis with clear actors and business rules;
2. a correct ER/EER model and a normalized relational schema, targeted at 3NF;
3. executable DDL with primary keys, foreign keys, checks, uniqueness rules, and documented indexes;
4. a reproducible import from the public dataset with provenance and quality flags;
5. an end-to-end demonstration from diagnostic evidence to eligibility, project assignment, lease, maintenance, and disposition;
6. representative SQL queries and at least one transaction/concurrency scenario;
7. honest discussion of what is measured, what is synthetic, and what cannot be concluded;
8. a clear English report and presentation aligned with the course rubric.

## Current risks

- The public measurements are cell-level rather than real pack-level operating records.
- The source has voltage and timestamp curves but not complete real-world BMS telemetry.
- One short startup segment contains implausibly low voltage values and requires a quality flag.
- Course documents contain slightly inconsistent final-presentation/report dates; the LMS must be checked before submission planning.
- Business-module claims are recorded in the local assignment document; the user confirmed
  module-4 ownership on 2026-11-06. Personal names and student IDs remain outside the repository.
- The next review date and acceptance of the current module-4 proposal remain unconfirmed.
