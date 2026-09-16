# DBMS Classification and PostgreSQL Rationale

**Course source:** `LN1_Introduction to database management.pdf`, especially slides 25, 33, 35, 44, and 47  
**Project requirement source:** `Group Project Requirement.pdf`, page 1  
**Last updated:** 2026-09-12

## Course framework

Lecture 1 classifies databases along three independent dimensions:

1. **Number of users:** single-user or multiuser; multiuser databases may serve a workgroup or an enterprise.
2. **Location:** centralized or distributed.
3. **Type of use:** operational database or data warehouse.

The lecture separately classifies database models as hierarchical, network, relational, and non-relational/NoSQL. Cloud deployment is another implementation option and may host either relational or non-relational databases.

These labels should not be collapsed into one dimension. For example, a database may be multiuser but centralized, and a relational database may be deployed locally or in the cloud.

## Classification of the proposed system

### Multiuser workgroup database

The database supports several roles: asset administrator, laboratory tester, operations staff, small energy-storage operator, and auditor. They share the same system of record and may access it concurrently. The MVP serves a bounded operating team rather than an organization-wide enterprise platform, so **workgroup database** is more accurate than **enterprise database**.

### Centralized database

The MVP will use one logical PostgreSQL database instance. Users may connect through different client sessions, but the authoritative data remains centrally managed. Multiple users or network connections do not make a database distributed; a distributed database partitions or replicates authoritative data across multiple database locations.

### Operational database

The principal workload creates and updates current business records: battery registration, diagnostic evidence, eligibility decisions, pack composition, project assignments, lease status, maintenance, return, transfer, and disposition. These are operational transactions. Historical summaries and analytical views are useful secondary outputs, but the system is not designed primarily as a data warehouse.

### Relational database model

The domain contains stable structured entities and explicit relationships. Examples include organizations owning battery units, tests supporting assessments, units composing packs, packs appearing in lease items, and assets generating lifecycle events. Primary keys, foreign keys, bridge tables, uniqueness rules, and transaction integrity are central to the design. This strongly matches the relational model required by the group project.

## Why this supports PostgreSQL

The course framework first narrows the product category to a **centralized multiuser operational RDBMS**. PostgreSQL and MySQL both satisfy that category, so the lecture classification alone should not be used to claim that PostgreSQL is uniquely correct.

PostgreSQL is selected within the category because it supports the project's strongest database-design demonstrations with relatively direct database-level rules:

- transactions and concurrent multiuser access;
- primary-key, foreign-key, unique, and check constraints;
- partial indexes for rules that apply only to active records;
- date/time range types;
- exclusion constraints that can reject overlapping active lease periods for the same battery pack;
- views and indexed queries over the public diagnostic measurements.

MySQL remains technically feasible, but overlap prevention normally requires additional trigger/application logic and explicit locking discipline. SQLite is excellent for a single-file prototype but is less aligned with the intended multiuser workgroup and concurrency demonstration. NoSQL and distributed databases address flexibility or scale-out problems that are outside the locked MVP.

## Proposal-ready wording

> The proposed system is a centralized, multiuser workgroup operational database based on the relational data model. It will serve as a shared system of record for battery-unit diagnostics, second-life eligibility decisions, pack allocation, leasing, maintenance, and lifecycle events. PostgreSQL is selected as the implementation DBMS because it supports concurrent operational transactions and strong relational integrity controls, while its range and exclusion constraints provide a direct mechanism for preventing overlapping active leases. The project does not require a distributed NoSQL architecture or a data warehouse because its primary need is reliable processing of structured, interdependent operational records rather than horizontal scale-out or historical analytical consolidation.

## Presentation caution

Do not say that PostgreSQL was selected merely because it is "more powerful" or because the dataset is "big data." The measured dataset contains roughly 0.7 million observations, which is manageable for several relational products. The defensible rationale is alignment between the business workload, the course classification, and the integrity rules the project will demonstrate.
