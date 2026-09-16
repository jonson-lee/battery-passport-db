"""Validate the public battery charge/discharge curve dataset used by IBA6151.

The script is intentionally dependency-light: it uses pandas for CSV parsing and
prints a compact JSON report to stdout. It never modifies the source data.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


EXPECTED_FILE_COUNT = 20
EXPECTED_COLUMNS_PER_FILE = 6
BATTERY_ID_PATTERN = re.compile(r"BATT_(\d{3})")


def validate_pair(timestamp: pd.Series, voltage: pd.Series) -> dict[str, object]:
    timestamp_present = timestamp.notna()
    voltage_present = voltage.notna()
    paired_missingness = bool(timestamp_present.equals(voltage_present))

    present = timestamp_present & voltage_present
    present_positions = present.to_numpy().nonzero()[0]
    trailing_only_missingness = bool(
        len(present_positions) == 0
        or (
            present_positions[0] == 0
            and len(present_positions) == present_positions[-1] + 1
        )
    )

    aligned = pd.DataFrame({"timestamp": timestamp, "voltage": voltage}).dropna()
    timestamp_numeric = pd.to_numeric(aligned["timestamp"], errors="coerce")
    voltage_numeric = pd.to_numeric(aligned["voltage"], errors="coerce")
    voltage_out_of_range = ~voltage_numeric.between(1.5, 4.5)

    return {
        "observations": int(len(aligned)),
        "numeric_timestamp": bool(timestamp_numeric.notna().all()),
        "numeric_voltage": bool(voltage_numeric.notna().all()),
        "paired_missingness": paired_missingness,
        "trailing_only_missingness": trailing_only_missingness,
        "strictly_increasing_timestamp": bool(
            timestamp_numeric.diff().dropna().gt(0).all()
        ),
        "timestamp_min_h": float(timestamp_numeric.min()),
        "timestamp_max_h": float(timestamp_numeric.max()),
        "voltage_min_v": float(voltage_numeric.min()),
        "voltage_max_v": float(voltage_numeric.max()),
        "voltage_in_plausible_range": bool(~voltage_out_of_range.any()),
        "voltage_out_of_range_observations": int(voltage_out_of_range.sum()),
    }


def validate_file(path: Path) -> dict[str, object]:
    frame = pd.read_csv(path)
    columns = frame.columns.tolist()
    battery_ids = sorted(
        {
            match.group(0)
            for column in columns
            if (match := BATTERY_ID_PATTERN.search(column))
        }
    )

    pairs = []
    for index in range(0, len(columns), 2):
        timestamp_column = columns[index]
        voltage_column = columns[index + 1]
        pair_result = validate_pair(frame[timestamp_column], frame[voltage_column])
        pair_result.update(
            {
                "timestamp_column": timestamp_column,
                "voltage_column": voltage_column,
            }
        )
        pairs.append(pair_result)

    file_ok = (
        len(columns) == EXPECTED_COLUMNS_PER_FILE
        and len(battery_ids) == 1
        and all(
            pair["numeric_timestamp"]
            and pair["numeric_voltage"]
            and pair["paired_missingness"]
            and pair["trailing_only_missingness"]
            and pair["strictly_increasing_timestamp"]
            for pair in pairs
        )
    )

    return {
        "file": path.name,
        "rows": int(len(frame)),
        "columns": columns,
        "battery_ids": battery_ids,
        "pairs": pairs,
        "ok": bool(file_ok),
    }


def validate_dataset(csv_directory: Path) -> dict[str, object]:
    files = sorted(csv_directory.glob("*.csv"))
    results = [validate_file(path) for path in files]
    battery_ids = sorted(
        {battery_id for result in results for battery_id in result["battery_ids"]}
    )
    charge_files = [result for result in results if "__chg_" in result["file"]]
    discharge_files = [result for result in results if "__dchg_" in result["file"]]
    curve_count = sum(len(result["pairs"]) for result in results)
    observation_count = sum(
        pair["observations"] for result in results for pair in result["pairs"]
    )
    quality_warning_count = sum(
        pair["voltage_out_of_range_observations"]
        for result in results
        for pair in result["pairs"]
    )

    dataset_ok = (
        len(files) == EXPECTED_FILE_COUNT
        and len(charge_files) == 10
        and len(discharge_files) == 10
        and len(battery_ids) == 10
        and all(result["ok"] for result in results)
    )

    return {
        "dataset_directory": str(csv_directory.resolve()),
        "csv_file_count": len(files),
        "charge_file_count": len(charge_files),
        "discharge_file_count": len(discharge_files),
        "battery_ids": battery_ids,
        "curve_count": curve_count,
        "non_null_observation_count": observation_count,
        "quality_warning_count": quality_warning_count,
        "validation_status": (
            "valid_with_warnings"
            if dataset_ok and quality_warning_count
            else "valid"
            if dataset_ok
            else "invalid"
        ),
        "all_files_valid": bool(dataset_ok),
        "files": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "csv_directory",
        nargs="?",
        default=(
            Path(__file__).resolve().parents[1]
            / "data"
            / "raw"
            / "battery_charge_discharge_curves"
            / "csv"
        ),
        type=Path,
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omit per-file details from the printed JSON report.",
    )
    args = parser.parse_args()

    report = validate_dataset(args.csv_directory)
    if args.summary_only:
        report.pop("files", None)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_files_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
