"""Regression test for the full OCR pipeline on a set of test images.

This test suite uses 1 screenshot1 of each type (1 match overview, 1 player
attributes, 1 player stats). It has hardcoded expected values for each of the 3
screenshots, and runs each image through the appropriate OCR pipeline, comparing
them against the expected values.

This includes loading the image, getting its
width and height, calling the screen resolution lookup to that width and height
before calling the OCR servce, so coordinate scaling from coordinates config matches
fixture dimensions. It then calls the correct OCR entry point and captures the full
extracted payload, which is then compared against the expected payload for that image.

Mismatches are collected as structured records: case, expected, actual and mismatches.
Mismatches are scored for each image, computing total compared values, mismatched
values and mismatch rate, and uses tiered outcomes: 0 mismatches - clean pass,
<50% mismatch for an image or <30% overall - pass but flag detailes,
>50% mismatch for an image or >30% overall - fail and flag details.

If any mismatches are found, a report should be emitted listing the image, field path,
expected value, actual value, and mismatch rate for the image and overall.

Missing images, unreadable images, bad config, OCR exceptions and other errors should
still fail the test like normal.
"""

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2 as cv
import pytest

from src.services.app import ocr_service as ocr_service_module
from src.services.app.ocr_service import OCRService

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "tests" / "fixtures" / "screenshots"
REPORT_PATH = PROJECT_ROOT / "tests" / "reports" / "ocr_test_report.json"

HARD_IMAGE_MISMATCH_THRESHOLD = 0.5
HARD_OVERALL_MISMATCH_THRESHOLD = 0.3


@dataclass(frozen=True)
class OCRCase:
    """Defines a test case for OCR regression testing."""

    name: str
    screenshot: str
    detector: Literal["stats", "attributes"]
    detector_kwargs: dict[str, bool]
    expected: dict[str, int | float | dict[str, int | float]]


CASES: list[OCRCase] = [
    OCRCase(
        name="match_overview_2",
        screenshot="match_overview_2.png",
        detector="stats",
        detector_kwargs={"is_player": False},
        expected={
            "home_team": {
                "score": 0,
                "possession": 59,
                "ball_recovery": 12,
                "shots": 7,
                "xg": 1.0,
                "passes": 223,
                "tackles": 11,
                "tackles_won": 8,
                "interceptions": 16,
                "saves": 4,
                "fouls_committed": 1,
                "offsides": 0,
                "corners": 0,
                "free_kicks": 4,
                "penalty_kicks": 0,
                "yellow_cards": 0,
            },
            "away_team": {
                "score": 0,
                "possession": 41,
                "ball_recovery": 16,
                "shots": 10,
                "xg": 2.4,
                "passes": 126,
                "tackles": 57,
                "tackles_won": 21,
                "interceptions": 3,
                "saves": 4,
                "fouls_committed": 4,
                "offsides": 1,
                "corners": 3,
                "free_kicks": 0,
                "penalty_kicks": 1,
                "yellow_cards": 1,
            },
        },
    ),
    OCRCase(
        name="player_attributes_1_2",
        screenshot="player_attributes_1_2.png",
        detector="attributes",
        detector_kwargs={"is_goalkeeper": False, "is_first_page": False},
        expected={
            "ball_control": 81,
            "crossing": 84,
            "curve": 80,
            "defensive_awareness": 81,
            "dribbling": 78,
            "fk_accuracy": 49,
            "finishing": 61,
            "heading_accuracy": 64,
            "long_pass": 77,
            "long_shots": 59,
            "penalties": 60,
            "short_pass": 80,
            "shot_power": 62,
            "slide_tackle": 84,
            "stand_tackle": 84,
            "volleys": 58,
        },
    ),
    OCRCase(
        name="player_performance_12",
        screenshot="player_performance_12.png",
        detector="stats",
        detector_kwargs={"is_player": True},
        expected={
            "goals": 0,
            "assists": 3,
            "shots": 1,
            "shot_accuracy": 100,
            "passes": 20,
            "pass_accuracy": 85,
            "dribbles": 18,
            "dribble_success_rate": 100,
            "tackles": 4,
            "tackle_success_rate": 0,
            "offsides": 0,
            "fouls_committed": 0,
            "possession_won": 1,
            "possession_lost": 4,
            "minutes_played": 92,
            "distance_covered": 10.4,
            "distance_sprinted": 2.3,
        },
    ),
]


def _flatten(data: dict, prefix: str = "") -> dict[str, int | float]:
    """Flatten a nested dictionary into a single level with dot-separated keys."""
    if not isinstance(data, dict):
        return {prefix: data}
    flat: dict[str, int | float] = {}
    for key, value in data.items():
        child = f"{prefix}.{key}" if prefix else str(key)
        flat |= _flatten(value, child)
    return flat


def _diff(
    expected: dict[str, int | float], actual: dict[str, int | float]
) -> list[dict[str, int | float]]:
    diffs: list[dict[str, int | float]] = []
    all_keys = sorted(set(expected) | set(actual))
    missing = object()
    for key in all_keys:
        expected_value = expected.get(key, missing)
        actual_value = actual.get(key, missing)
        if expected_value != actual_value:
            diffs.append(
                {
                    "path": key,
                    "expected": "<missing>"
                    if expected_value is missing
                    else expected_value,
                    "actual": "<missing>" if actual_value is missing else actual_value,
                }
            )
    return diffs


def _run_case(
    case: OCRCase, service: OCRService, monkeypatch: pytest.MonkeyPatch
) -> dict[str, int | float]:
    screenshot_path = SCREENSHOT_DIR / case.screenshot
    if not screenshot_path.exists():
        raise FileNotFoundError(f"Missing fixture screenshot: {screenshot_path}")

    screenshot_image = cv.imread(str(screenshot_path))
    if screenshot_image is None:
        raise RuntimeError(f"Could not decode fixture screenshot: {screenshot_path}")

    height, width = screenshot_image.shape[:2]

    # Force coordinate scaling to match the fixture image size.
    monkeypatch.setattr(
        ocr_service_module,
        "get_screen_resolution",
        lambda: (width, height),
    )

    if case.detector == "stats":
        return service.detect_stats(
            latest_screenshot_path=screenshot_path,
            **case.detector_kwargs,
        )
    return service.detect_player_attributes(
        latest_screenshot_path=screenshot_path,
        **case.detector_kwargs,
    )


def test_ocr_regression_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run OCR tests on a set of screenshots, comparing vs expected values."""
    service = OCRService(project_root=PROJECT_ROOT)

    hard_failures: list[dict[str, int | float]] = []
    report_rows: list[dict[str, int | float]] = []
    total_compared = 0
    total_mismatches = 0

    for case in CASES:
        actual_payload = _run_case(case, service, monkeypatch)

        if not case.expected:
            warnings.warn(
                (
                    f"{case.name}: no expected values configured yet; "
                    "recorded actual payload only."
                ),
                stacklevel=2,
            )
            report_rows.append(
                {
                    "case": case.name,
                    "status": "no expected values",
                    "actual": actual_payload,
                    "mismatches": [],
                }
            )
            continue
        expected_flat = _flatten(case.expected)
        actual_flat = _flatten(actual_payload)
        mismatches = _diff(expected_flat, actual_flat)

        compared = max(1, len(set(expected_flat) | set(actual_flat)))
        mismatch_count = len(mismatches)
        mismatch_rate = mismatch_count / compared

        total_compared += compared
        total_mismatches += mismatch_count

        case_row = {
            "case": case.name,
            "status": "ok",
            "compared": compared,
            "mismatch_count": mismatch_count,
            "mismatch_rate": round(mismatch_rate, 4),
            "mismatches": mismatches,
            "actual": actual_payload,
        }

        if mismatch_rate == 0:
            report_rows.append(case_row)
            continue
        if mismatch_rate > HARD_IMAGE_MISMATCH_THRESHOLD or (
            total_compared > 0
            and total_mismatches / total_compared > HARD_OVERALL_MISMATCH_THRESHOLD
        ):
            case_row["status"] = "hard_fail"
            hard_failures.append(case_row)
        else:
            case_row["status"] = "soft_fail"
            warnings.warn(
                f"{case.name}: {mismatch_count}/{compared} mismatches "
                f"({mismatch_rate:.1%})",
                stacklevel=2,
            )

        report_rows.append(case_row)

    overall_mismatch_rate = (
        total_mismatches / total_compared if total_compared > 0 else 0
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "overall_mismatch_rate": round(overall_mismatch_rate, 4),
                "total_compared": total_compared,
                "total_mismatches": total_mismatches,
                "cases": report_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if overall_mismatch_rate > HARD_OVERALL_MISMATCH_THRESHOLD:
        pytest.fail(
            f"Overall OCR mismatch rate too high: {overall_mismatch_rate:.1%}. "
            f"See report at {REPORT_PATH}"
        )

    if hard_failures:
        lines = [
            f"{row['case']}: {row['mismatch_count']}/{row['compared']} "
            f"({row['mismatch_rate']:.1%})"
            for row in hard_failures
        ]
        joined = "; ".join(lines)
        pytest.fail(
            f"OCR hard-fail cases detected: {joined}. See report at {REPORT_PATH}"
        )
