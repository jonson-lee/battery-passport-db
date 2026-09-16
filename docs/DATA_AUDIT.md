# Public Battery Data Acquisition and Quality Audit

**Audit date:** 2026-09-12  
**Result:** Go with one documented quality warning

## Dataset selected

**Name:** Battery Characterization Datasets — Charge/Discharge Voltage Curves  
**Repository:** <https://github.com/BulyK47/battery-datasets>  
**Dataset page:** <https://github.com/BulyK47/battery-datasets/tree/main/charge-discharge-voltage-curves>  
**Institution stated by source:** National University of Science and Technology POLITEHNICA Bucharest  
**License:** Creative Commons Attribution 4.0 International (CC BY 4.0)  
**Related focus:** high-speed screening of retired lithium-ion batteries

The license and citation metadata are preserved locally as `SOURCE_LICENSE` and `CITATION.cff`.

## Acquisition verification

The complete public repository archive was downloaded successfully without account authentication.

- Downloaded ZIP size: 20,903,526 bytes
- Project data footprint: 25 files, 33,126,194 bytes
- Local source directory: `data/raw/battery_charge_discharge_curves/`
- CSV coverage: 20 files
- Other preserved materials: source README, original XLSX workbook, figure, citation metadata, and license

This is a low-acquisition-risk source for the course project because the complete working copy is now local, modest in size, and accompanied by attribution material.

## Structural validation

The validation command is:

```powershell
python scripts/validate_public_battery_data.py --summary-only
```

Validated results:

| Check | Result |
|---|---:|
| CSV files | 20 |
| Charge files | 10 |
| Discharge files | 10 |
| Battery IDs | 10 (`BATT_001`–`BATT_010`) |
| Curves | 60 |
| Non-null timestamp-voltage observations | 703,657 |
| Numeric timestamp and voltage columns | Pass |
| Paired timestamp/voltage missingness | Pass |
| Missing data confined to trailing padding | Pass |
| Strictly increasing timestamps | Pass |
| Overall status | `valid_with_warnings` |

Each CSV contains three timestamp-voltage pairs. Different curves have different lengths, so shorter curves are padded with trailing nulls. The import must split each pair independently and discard only the paired trailing padding.

## Quality warning

One curve, `BATT_010_CC2`, contains a short startup segment before the voltage jumps to the expected operating region. The automated range check flags 45 observations below 1.5 V, with a minimum of 1.301 V.

Required handling:

- retain the raw values unchanged;
- attach a data-quality warning to the source curve/test;
- exclude flagged startup observations from derived summaries only through a documented transformation;
- show the warning in the project demonstration as evidence of reliable data management.

## What the data supports

The public source is sufficient for:

- battery-unit master records and manufacturer/chemistry metadata;
- diagnostic test and curve records;
- high-volume measurement ingestion;
- curve summaries and data-quality rules;
- provenance and traceability demonstrations;
- indexing and aggregation examples;
- a transparent classroom eligibility workflow when combined with documented rules or tester approval.

## What the data does not support

The source does not provide real enterprise records for:

- assembled battery packs;
- ownership transfers;
- storage-project assignments;
- lease contracts or payments;
- maintenance work orders;
- returns, recycling, or disposal;
- certified safety eligibility;
- real commercial profitability or ROI.

Those operational records will be synthetic and explicitly labelled. No report or presentation may imply that they came from the public experimental source or from a real company.

## Data-to-database mapping

| Source content | Target database area | Origin |
|---|---|---|
| Battery identifiers and specifications | `BatteryUnit` | `public_experimental` |
| Charge/discharge run metadata | `DiagnosticTest` | `public_experimental` |
| Timestamp-voltage pairs | `DiagnosticMeasurement` staging | `public_experimental` |
| Derived curve summaries and quality flags | `DiagnosticTest` / assessment evidence | `derived_public` |
| Pack composition | `BatteryPack`, `BatteryPackUnit` | `synthetic` |
| Organizations, projects, and contracts | operational tables | `synthetic` |
| Maintenance and lifecycle events | event tables | `synthetic` |

## Final data verdict

**Go.** The dataset is obtainable, reproducible, appropriately licensed, small enough for a course project, and structurally adequate for the technical portion of the proposed database. Development may proceed under the locked condition that cell-level experimental evidence and synthetic business events remain visibly separated.

