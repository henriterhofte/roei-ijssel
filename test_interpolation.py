#!/usr/bin/env python3

import json
import subprocess
import sys
from pathlib import Path


BASE = Path.home() / "rws_data"
DOWNLOADS = BASE / "downloads"
PROCESSED = BASE / "processed"

TEST_NAME = "_test_interpolation_Q.json"
INPUT = DOWNLOADS / TEST_NAME
OUTPUT = PROCESSED / TEST_NAME


TIMES = [
    "2026-08-22T12:00:00+02:00",
    "2026-08-22T12:10:00+02:00",
    "2026-08-22T12:20:00+02:00",
    "2026-08-22T12:30:00+02:00",
]


def make_input():
    # Twee ontbrekende meetpunten:
    #
    # 12:00 = 100
    # 12:10 = missing
    # 12:20 = missing
    # 12:30 = 130
    #
    # Verwachting is compleet, omdat rws_data.py die verplicht stelt.

    data = {
        "bron": "TEST",
        "opgehaald": "2026-08-22T14:00:00+02:00",
        "locatie": "test.locatie",
        "locatie_naam": "Testlocatie",
        "locatie_id": "test.locatie",
        "parameter": "Q",
        "eenheid": "m3/s",
        "periode_uren": 1,

        "meting": [
            {
                "tijd": TIMES[0],
                "waarde": 100.0,
                "locatie": "test.locatie",
            },
            {
                "tijd": TIMES[3],
                "waarde": 130.0,
                "locatie": "test.locatie",
            },
        ],

        "verwachting": [
            {
                "tijd": t,
                "waarde": 200.0,
                "locatie": "test.locatie",
            }
            for t in TIMES
        ],
    }

    with open(INPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run(interpolate):
    result = subprocess.run(
        [
            sys.executable,
            str(BASE / "rws_data.py"),
            "--file",
            TEST_NAME,
            "--interpolate",
            str(interpolate),
        ],
        cwd=BASE,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(
            f"rws_data.py gaf exitcode {result.returncode}"
        )

    if not OUTPUT.exists():
        print(result.stdout)
        raise RuntimeError(
            f"Verwerkt bestand niet gevonden: {OUTPUT}"
        )

    with open(OUTPUT, encoding="utf-8") as f:
        return json.load(f)


def find(points, tijd):
    matches = [p for p in points if p["tijd"] == tijd]

    assert len(matches) == 1, (
        f"{tijd}: verwacht 1 punt, kreeg {len(matches)}"
    )

    return matches[0]


def test_interpolate_1():
    print("Test 1: --interpolate 1")

    data = run(1)
    points = data["meting"]

    assert len(points) == 4, (
        f"Verwacht 4 meetpunten, kreeg {len(points)}"
    )

    p10 = find(points, TIMES[1])
    p20 = find(points, TIMES[2])

    assert p10["kwaliteit"] == "missing", p10
    assert p20["kwaliteit"] == "missing", p20

    print("  OK: twee opeenvolgende gaten blijven missing")


def test_interpolate_2():
    print("Test 2: --interpolate 2")

    data = run(2)
    points = data["meting"]

    assert len(points) == 4, (
        f"Verwacht 4 meetpunten, kreeg {len(points)}"
    )

    p10 = find(points, TIMES[1])
    p20 = find(points, TIMES[2])

    assert p10["kwaliteit"] == "interpolated", p10
    assert p20["kwaliteit"] == "interpolated", p20

    # Lineair tussen 100 en 130:
    #
    # 12:10 = 110
    # 12:20 = 120

    assert abs(p10["waarde"] - 110.0) < 1e-9, p10
    assert abs(p20["waarde"] - 120.0) < 1e-9, p20

    print("  OK: twee punten lineair geïnterpoleerd: 110 en 120")


def test_provenance():
    print("Test 3: provenance")

    data = run(2)
    points = data["meting"]

    for tijd in TIMES[1:3]:
        p = find(points, tijd)

        assert p["kwaliteit"] == "interpolated", p
        assert "interpolatie" in p, p

        info = p["interpolatie"]

        assert info["methode"] == "lineair", info
        assert info["max_gap"] == 2, info

        assert info["tussen"] == [
            TIMES[0],
            TIMES[3],
        ], info

    print("  OK: interpolatie-provenance aanwezig")


def test_forecast_unchanged():
    print("Test 4: verwachting blijft ongemoeid")

    data = run(2)

    verwachting = data["verwachting"]

    assert len(verwachting) == 4, (
        f"Verwacht 4 forecastpunten, kreeg {len(verwachting)}"
    )

    for p in verwachting:
        assert p["waarde"] == 200.0, p

    print("  OK: verwachting niet geïnterpoleerd of gewijzigd")


def main():
    print("=" * 70)
    print("RWS INTERPOLATIEREGRESSIETEST")
    print("=" * 70)

    if INPUT.exists() or OUTPUT.exists():
        raise RuntimeError(
            "Testbestanden bestaan al. Verwijder eerst:\n"
            f"  {INPUT}\n"
            f"  {OUTPUT}"
        )

    try:
        make_input()

        test_interpolate_1()
        test_interpolate_2()
        test_provenance()
        test_forecast_unchanged()

        print("=" * 70)
        print("ALLE INTERPOLATIETESTS GESLAAGD")
        print("=" * 70)

    finally:
        INPUT.unlink(missing_ok=True)
        OUTPUT.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
