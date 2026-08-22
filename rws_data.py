#!/usr/bin/env python3

"""
RWS data processing layer

Verwerkt ruwe RWS Waterwebservices JSON-bestanden uit:

    ~/rws_data/downloads/

naar uniforme 10-minutenreeksen in:

    ~/rws_data/processed/

Belangrijke principes
---------------------
1. Ruwe downloads worden NOOIT gewijzigd.
2. Metingen en verwachtingen krijgen ieder hun eigen tijdas.
3. Een verwachting die verder vooruitloopt dan de meting
   wordt NIET als ontbrekende meting beschouwd.
4. Ontbrekende punten binnen het natuurlijke meetbereik krijgen:
       waarde=None
       kwaliteit="missing"
5. Originele RWS-metingen krijgen:
       kwaliteit="observed"
6. Verwachtingen krijgen:
       kwaliteit="forecast"
7. Optionele interpolatie van korte gaten is mogelijk.
8. Geïnterpoleerde waarden krijgen:
       kwaliteit="interpolated"
9. Geen extrapolatie aan begin/einde van een reeks.
10. Tijdstippen blijven timezone-aware.

Normaal uitvoeren
-----------------
    python ~/rws_data/rws_data.py

Eén bestand
-----------
    python ~/rws_data/rws_data.py \
        --file lobith_bovenrijn_tolkamer_Q.json

Interpolatie van maximaal één ontbrekend meetpunt
--------------------------------------------------
    python ~/rws_data/rws_data.py --interpolate 1

Interpolatie van maximaal drie opeenvolgende ontbrekende punten
----------------------------------------------------------------
    python ~/rws_data/rws_data.py --interpolate 3

Processed-directory eerst leegmaken
------------------------------------
    python ~/rws_data/rws_data.py --clean

Combinatie
----------
    python ~/rws_data/rws_data.py --clean --interpolate 1
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# ======================================================================
# DIRECTORIES / CONFIG
# ======================================================================

BASE_DIR = Path.home() / "rws_data"
INPUT_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "processed"

STEP_MINUTES = 10


# ======================================================================
# TIME / JSON HELPERS
# ======================================================================

def parse_time(value: str) -> datetime:
    """
    Parse ISO-8601 timestamp.

    RWS timestamps moeten timezone-aware zijn.
    """
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        raise ValueError(
            f"Timestamp zonder timezone: {value}"
        )

    return dt


def iso_time(dt: datetime) -> str:
    """
    Geef datetime terug als ISO-string met seconden en timezone.
    """
    return dt.isoformat(timespec="seconds")


def is_number(value: Any) -> bool:
    """
    Controleer of waarde een eindige numerieke waarde is.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def load_json(path: Path) -> dict[str, Any]:
    """
    Lees JSON-bestand.
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(
    path: Path,
    data: dict[str, Any],
) -> None:
    """
    Schrijf JSON netjes geformatteerd.
    """
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")


# ======================================================================
# TIJDAS
# ======================================================================

def build_grid(
    start: datetime,
    end: datetime,
) -> list[datetime]:
    """
    Maak een uniforme 10-minuten tijdas van start t/m end.

    Beide grenzen zijn inclusief.
    """
    if end < start:
        return []

    result: list[datetime] = []

    current = start

    while current <= end:
        result.append(current)
        current += timedelta(
            minutes=STEP_MINUTES
        )

    return result


def expected_point_count(
    start: datetime,
    end: datetime,
) -> int:
    """
    Verwacht aantal punten op een 10-minutenrooster.
    """
    if end < start:
        return 0

    delta = end - start

    return int(
        delta.total_seconds()
        / (STEP_MINUTES * 60)
    ) + 1


# ======================================================================
# RWS RECORDS
# ======================================================================

def build_series(
    records: list[dict[str, Any]],
) -> tuple[dict[datetime, float], list[str]]:
    """
    Zet RWS-records om naar:

        {datetime: waarde}

    Geeft daarnaast waarschuwingen terug.

    Een timestamp moet exact op een 10-minutenpunt liggen.
    Als dat niet zo is, wordt hij naar het dichtstbijzijnde
    10-minutenpunt afgerond en wordt een waarschuwing geregistreerd.
    """

    values: dict[datetime, float] = {}
    warnings: list[str] = []

    for record in records:

        if "tijd" not in record:
            warnings.append(
                "Record zonder 'tijd' overgeslagen"
            )
            continue

        try:
            dt = parse_time(
                record["tijd"]
            )

        except Exception as exc:
            warnings.append(
                f"Ongeldige timestamp "
                f"{record.get('tijd')!r}: {exc}"
            )
            continue

        value = record.get("waarde")

        if not is_number(value):
            warnings.append(
                f"Niet-numerieke waarde op "
                f"{record.get('tijd')!r}: {value!r}"
            )
            continue

        # --------------------------------------------------------------
        # Controleer 10-minutenrooster
        # --------------------------------------------------------------

        exact_grid = (
            dt.minute % STEP_MINUTES == 0
            and dt.second == 0
            and dt.microsecond == 0
        )

        if not exact_grid:
            rounded_minute = (
                round(dt.minute / STEP_MINUTES)
                * STEP_MINUTES
            )

            # Afhandeling van afronding naar het volgende uur.
            base = dt.replace(
                minute=0,
                second=0,
                microsecond=0,
            )

            rounded = base + timedelta(
                minutes=rounded_minute
            )

            warnings.append(
                "Timestamp niet exact op "
                f"10-minutenrooster: "
                f"{iso_time(dt)} -> "
                f"{iso_time(rounded)}"
            )

            dt = rounded

        # --------------------------------------------------------------
        # Dubbele timestamp
        # --------------------------------------------------------------

        if dt in values:
            warnings.append(
                f"Dubbele timestamp: "
                f"{iso_time(dt)}; "
                f"laatste waarde behouden"
            )

        values[dt] = float(value)

    return values, warnings


# ======================================================================
# UNIFORME REEKS
# ======================================================================

def make_uniform_series(
    values: dict[datetime, float],
    start: datetime,
    end: datetime,
    quality_present: str,
) -> list[dict[str, Any]]:
    """
    Maak uniforme 10-minutenreeks binnen het natuurlijke bereik.

    Belangrijk:
    alleen het bereik start -> end van deze specifieke reeks
    wordt gebruikt.

    Daardoor wordt bijvoorbeeld 13:20 niet als ontbrekende
    METING gezien als de laatste echte meting 13:10 is.
    """

    grid = build_grid(
        start,
        end,
    )

    result: list[dict[str, Any]] = []

    for dt in grid:

        if dt in values:
            result.append(
                {
                    "tijd": iso_time(dt),
                    "waarde": values[dt],
                    "kwaliteit": quality_present,
                }
            )

        else:
            result.append(
                {
                    "tijd": iso_time(dt),
                    "waarde": None,
                    "kwaliteit": "missing",
                }
            )

    return result


# ======================================================================
# INTERPOLATIE
# ======================================================================

def interpolate_short_gaps(
    points: list[dict[str, Any]],
    max_gap: int,
) -> int:
    """
    Interpoleer maximaal max_gap opeenvolgende ontbrekende
    meetpunten.

    Alleen tussen twee echte 'observed' waarden.

    Voorbeeld:

        observed
        missing
        observed

    wordt:

        observed
        interpolated
        observed

    Geen extrapolatie aan begin of einde.
    """

    if max_gap <= 0:
        return 0

    n = len(points)
    interpolated_count = 0

    i = 0

    while i < n:

        if points[i]["kwaliteit"] != "missing":
            i += 1
            continue

        # --------------------------------------------------------------
        # Zoek begin gat
        # --------------------------------------------------------------

        start = i

        while (
            i < n
            and points[i]["kwaliteit"] == "missing"
        ):
            i += 1

        end = i - 1

        gap_length = end - start + 1

        # --------------------------------------------------------------
        # Geen linker of rechter buur
        # --------------------------------------------------------------

        if start == 0:
            continue

        if i >= n:
            continue

        left = points[start - 1]
        right = points[i]

        # --------------------------------------------------------------
        # Alleen tussen echte metingen
        # --------------------------------------------------------------

        if left["kwaliteit"] != "observed":
            continue

        if right["kwaliteit"] != "observed":
            continue

        if gap_length > max_gap:
            continue

        left_value = left["waarde"]
        right_value = right["waarde"]

        if left_value is None:
            continue

        if right_value is None:
            continue

        # --------------------------------------------------------------
        # Lineaire interpolatie
        # --------------------------------------------------------------

        denominator = i - (start - 1)

        for j in range(start, end + 1):

            fraction = (
                (j - (start - 1))
                / denominator
            )

            value = (
                left_value
                + fraction
                * (right_value - left_value)
            )

            points[j]["waarde"] = value

            points[j]["kwaliteit"] = (
                "interpolated"
            )

            points[j]["interpolatie"] = {
                "methode": "lineair",
                "max_gap": max_gap,
                "tussen": [
                    left["tijd"],
                    right["tijd"],
                ],
            }

            interpolated_count += 1

    return interpolated_count


# ======================================================================
# STATISTIEKEN
# ======================================================================

def count_quality(
    points: list[dict[str, Any]],
    quality: str,
) -> int:
    """
    Tel punten met bepaalde kwaliteitsstatus.
    """
    return sum(
        p.get("kwaliteit") == quality
        for p in points
    )


# ======================================================================
# VERWERK ÉÉN BESTAND
# ======================================================================

def process_file(
    input_path: Path,
    output_path: Path,
    interpolate_max_gap: int = 0,
) -> dict[str, Any]:

    source = load_json(
        input_path
    )

    raw_measurements = source.get(
        "meting",
        [],
    )

    raw_forecasts = source.get(
        "verwachting",
        [],
    )

    # ------------------------------------------------------------------
    # Bouw bronreeksen
    # ------------------------------------------------------------------

    measurements, measurement_warnings = (
        build_series(
            raw_measurements
        )
    )

    forecasts, forecast_warnings = (
        build_series(
            raw_forecasts
        )
    )

    if not measurements:
        raise ValueError(
            "Geen meetgegevens gevonden"
        )

    if not forecasts:
        raise ValueError(
            "Geen verwachtingsgegevens gevonden"
        )

    # ------------------------------------------------------------------
    # BELANGRIJK:
    #
    # Iedere reeks krijgt zijn EIGEN natuurlijke bereik.
    #
    # Meting:
    #     eerste echte meting -> laatste echte meting
    #
    # Verwachting:
    #     eerste verwachting -> laatste verwachting
    #
    # Hierdoor wordt het verschil in looptijd niet als missing
    # aangemerkt.
    # ------------------------------------------------------------------

    measurement_start = min(
        measurements.keys()
    )

    measurement_end = max(
        measurements.keys()
    )

    forecast_start = min(
        forecasts.keys()
    )

    forecast_end = max(
        forecasts.keys()
    )

    # ------------------------------------------------------------------
    # Uniforme reeksen
    # ------------------------------------------------------------------

    measurement_points = (
        make_uniform_series(
            measurements,
            measurement_start,
            measurement_end,
            "observed",
        )
    )

    forecast_points = (
        make_uniform_series(
            forecasts,
            forecast_start,
            forecast_end,
            "forecast",
        )
    )

    # ------------------------------------------------------------------
    # Optionele interpolatie
    # ------------------------------------------------------------------

    interpolated_count = (
        interpolate_short_gaps(
            measurement_points,
            interpolate_max_gap,
        )
    )

    # ------------------------------------------------------------------
    # Statistieken
    # ------------------------------------------------------------------

    measurement_expected = (
        expected_point_count(
            measurement_start,
            measurement_end,
        )
    )

    forecast_expected = (
        expected_point_count(
            forecast_start,
            forecast_end,
        )
    )

    measurement_observed = (
        count_quality(
            measurement_points,
            "observed",
        )
    )

    measurement_missing = (
        count_quality(
            measurement_points,
            "missing",
        )
    )

    forecast_count = (
        count_quality(
            forecast_points,
            "forecast",
        )
    )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    output = {
        "bron": source.get(
            "bron",
            "Rijkswaterstaat Waterwebservices",
        ),

        "verwerking": {
            "script": "rws_data.py",
            "verwerkt": iso_time(
                datetime.now().astimezone()
            ),
            "bronbestand": input_path.name,
            "interval_minuten": STEP_MINUTES,

            "interpolatie": {
                "ingeschakeld": (
                    interpolate_max_gap > 0
                ),
                "max_opeenvolgende_punten": (
                    interpolate_max_gap
                ),
                "methode": (
                    "lineair"
                    if interpolate_max_gap > 0
                    else None
                ),
            },
        },

        "locatie": source.get(
            "locatie"
        ),

        "locatie_naam": source.get(
            "locatie_naam"
        ),

        "locatie_id": source.get(
            "locatie_id"
        ),

        "parameter": source.get(
            "parameter"
        ),

        "eenheid": source.get(
            "eenheid"
        ),

        # --------------------------------------------------------------
        # Iedere reeks heeft eigen periode
        # --------------------------------------------------------------

        "periode": {
            "meting": {
                "start": iso_time(
                    measurement_start
                ),
                "einde": iso_time(
                    measurement_end
                ),
                "aantal_punten": (
                    len(measurement_points)
                ),
            },

            "verwachting": {
                "start": iso_time(
                    forecast_start
                ),
                "einde": iso_time(
                    forecast_end
                ),
                "aantal_punten": (
                    len(forecast_points)
                ),
            },
        },

        # --------------------------------------------------------------
        # Kwaliteit
        # --------------------------------------------------------------

        "kwaliteit": {
            "meting": {
                "verwacht": measurement_expected,
                "observed": measurement_observed,
                "missing": measurement_missing,
                "interpolated": interpolated_count,
            },

            "verwachting": {
                "verwacht": forecast_expected,
                "forecast": forecast_count,
                "missing": (
                    forecast_expected
                    - forecast_count
                ),
            },

            "waarschuwingen": (
                measurement_warnings
                + forecast_warnings
            ),
        },

        # --------------------------------------------------------------
        # Data
        # --------------------------------------------------------------

        "meting": measurement_points,

        "verwachting": forecast_points,
    }

    save_json(
        output_path,
        output,
    )

    return output


# ======================================================================
# CONSOLE OUTPUT
# ======================================================================

def print_file_summary(
    input_path: Path,
    output_path: Path,
    data: dict[str, Any],
) -> None:

    quality = data["kwaliteit"]

    measurement_period = (
        data["periode"]["meting"]
    )

    forecast_period = (
        data["periode"]["verwachting"]
    )

    measurement_quality = (
        quality["meting"]
    )

    forecast_quality = (
        quality["verwachting"]
    )

    print("-" * 70)

    print(input_path.name)

    print(
        f"  locatie:       "
        f"{data.get('locatie_naam', data.get('locatie'))}"
    )

    print(
        f"  parameter:     "
        f"{data.get('parameter')}"
    )

    print(
        f"  eenheid:       "
        f"{data.get('eenheid')}"
    )

    # --------------------------------------------------------------
    # METING
    # --------------------------------------------------------------

    print("  METING")

    print(
        f"    periode:     "
        f"{measurement_period['start']} -> "
        f"{measurement_period['einde']}"
    )

    print(
        f"    verwacht:    "
        f"{measurement_quality['verwacht']}"
    )

    print(
        f"    observed:    "
        f"{measurement_quality['observed']}"
    )

    print(
        f"    missing:     "
        f"{measurement_quality['missing']}"
    )

    print(
        f"    interpolated:"
        f"{measurement_quality['interpolated']}"
    )

    # --------------------------------------------------------------
    # VERWACHTING
    # --------------------------------------------------------------

    print("  VERWACHTING")

    print(
        f"    periode:     "
        f"{forecast_period['start']} -> "
        f"{forecast_period['einde']}"
    )

    print(
        f"    verwacht:    "
        f"{forecast_quality['verwacht']}"
    )

    print(
        f"    forecast:    "
        f"{forecast_quality['forecast']}"
    )

    print(
        f"    missing:     "
        f"{forecast_quality['missing']}"
    )

    print(
        f"  output:        "
        f"{output_path}"
    )

    warning_count = len(
        quality["waarschuwingen"]
    )

    if warning_count:
        print(
            f"  waarschuwingen:{warning_count}"
        )


# ======================================================================
# MAIN
# ======================================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Verwerk RWS-data naar betrouwbare "
            "uniforme 10-minutenreeksen."
        )
    )

    parser.add_argument(
        "--file",
        help=(
            "Verwerk alleen dit JSON-bestand "
            "uit downloads/"
        ),
    )

    parser.add_argument(
        "--interpolate",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Interpoloeer maximaal N opeenvolgende "
            "ontbrekende meetpunten. "
            "Standaard: 0."
        ),
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help=(
            "Verwijder bestaande processed/*.json "
            "voor verwerking."
        ),
    )

    args = parser.parse_args()

    if args.interpolate < 0:
        parser.error(
            "--interpolate moet >= 0 zijn"
        )

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------

    INPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # Clean
    # ------------------------------------------------------------------

    if args.clean:

        for path in OUTPUT_DIR.glob(
            "*.json"
        ):
            path.unlink()

    # ------------------------------------------------------------------
    # Inputbestanden
    # ------------------------------------------------------------------

    if args.file:

        input_path = (
            INPUT_DIR / args.file
        )

        if not input_path.exists():
            raise SystemExit(
                f"Bestand niet gevonden: "
                f"{input_path}"
            )

        input_files = [
            input_path
        ]

    else:

        input_files = sorted(
            INPUT_DIR.glob(
                "*.json"
            )
        )

    if not input_files:
        raise SystemExit(
            f"Geen JSON-bestanden gevonden in "
            f"{INPUT_DIR}"
        )

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    print("=" * 70)
    print(
        "RWS DATA VERWERKINGSLAAG"
    )
    print("=" * 70)

    print(
        f"Input:             {INPUT_DIR}"
    )

    print(
        f"Output:            {OUTPUT_DIR}"
    )

    print(
        f"Interval:          "
        f"{STEP_MINUTES} minuten"
    )

    if args.interpolate > 0:
        print(
            f"Interpolatie:      "
            f"maximaal {args.interpolate} "
            f"opeenvolgende punten"
        )
    else:
        print(
            "Interpolatie:      UIT"
        )

    print(
        f"Bestanden:         "
        f"{len(input_files)}"
    )

    # ------------------------------------------------------------------
    # Verwerken
    # ------------------------------------------------------------------

    success = 0
    errors = 0

    for input_path in input_files:

        output_path = (
            OUTPUT_DIR / input_path.name
        )

        try:

            data = process_file(
                input_path,
                output_path,
                interpolate_max_gap=(
                    args.interpolate
                ),
            )

            print_file_summary(
                input_path,
                output_path,
                data,
            )

            success += 1

        except Exception as exc:

            errors += 1

            print("-" * 70)

            print(
                input_path.name
            )

            print(
                f"  FOUT: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

    # ------------------------------------------------------------------
    # Samenvatting
    # ------------------------------------------------------------------

    print("=" * 70)
    print("SAMENVATTING")
    print("=" * 70)

    print(
        f"Succesvol:         {success}"
    )

    print(
        f"Fouten:            {errors}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
