# IBA6151 Project Decisions

**Last updated:** 2026-09-12

## D-001 — Project direction

**Decision:** Build a battery passport and second-life eligibility leasing database for small energy-storage operators.  
**Status:** Accepted.  
**Reason:** It is novel enough for the presentation rubric while still offering a clear relational workflow involving assets, tests, assessments, assignments, contracts, maintenance, and lifecycle events.

## D-002 — Small and solid MVP

**Decision:** Limit the project to one end-to-end second-life workflow and approximately 10–12 core business tables.  
**Status:** Accepted.  
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

**Decision:** Form a five-person group. The project currently has one member and will recruit four additional members.  
**Status:** Accepted on 2026-09-12.  
**Reason:** Official course materials require 5–6 persons per group; five members meet the requirement while keeping coordination manageable.

## Open decisions

- Final eligibility thresholds and whether the tester may override them.
- Final group member names, student IDs, and role allocation.
- Official presentation/report deadline to use when course documents conflict.
