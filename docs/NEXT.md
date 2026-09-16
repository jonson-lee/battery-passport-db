# IBA6151 Next Actions

**Current status:** Topic established — Go  
**Last updated:** 2026-09-12

## Immediate priority

1. **Prepare the implementation platform.** PostgreSQL is locked; next verify whether it is already installed, select a supported local version, and document the repeatable setup without exposing credentials.
2. **Design the conceptual model.** Produce the ER/EER diagram for the 10–12 core business entities and document cardinalities, optionality, and business rules.
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
- If the core workflow requires more than roughly 12 business tables before it works end to end, reduce scope rather than adding modules.
- Optional analytics or additional datasets may begin only after the core database, constraints, and demonstration queries pass verification.

## Still needed from the group

- Recruit four additional members to reach the locked five-person group size
- Member names and student IDs after recruitment
- Division of responsibility
- Instructor/LMS confirmation of the exact submission and presentation dates
