# Data Directory

## Raw public source

`raw/battery_charge_discharge_curves/` contains the public charge/discharge voltage-curve dataset selected for the IBA6151 project.

- Source: <https://github.com/BulyK47/battery-datasets>
- Dataset: <https://github.com/BulyK47/battery-datasets/tree/main/charge-discharge-voltage-curves>
- License: CC BY 4.0
- Public experimental unit: battery cell / `BatteryUnit`

Preserved attribution files:

- `raw/battery_charge_discharge_curves/SOURCE_LICENSE`
- `raw/battery_charge_discharge_curves/CITATION.cff`
- `raw/battery_charge_discharge_curves/README.md`

Do not edit files under `raw/`. Cleaning and transformation must write to a separate future `processed/` directory and document the transformation.

## Validation

Run from the project root:

```powershell
python scripts/validate_public_battery_data.py --summary-only
```

Expected status as of 2026-09-12: `valid_with_warnings`, with all 20 CSV files structurally valid and one documented startup-voltage warning.

## Provenance policy

Database rows must identify their origin:

- `public_experimental`: directly imported public measurements or metadata;
- `derived_public`: summaries calculated from public measurements;
- `synthetic`: generated organizations, packs, projects, contracts, maintenance, or lifecycle events.

Synthetic records must not be described as observations from a real company.

