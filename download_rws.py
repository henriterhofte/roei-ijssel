from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from rws_api import LOCATIES, PARAMETERS, get_river_data


# ============================================================
# INSTELLINGEN
# ============================================================

DEFAULT_PERIODE_UREN = 24

BASE_DIR = Path.home() / "rws_data"
OUTPUT_DIR = BASE_DIR / "downloads"

DEFAULT_PARAMETERS = ("WATHTE", "Q")


# ============================================================
# HULPFUNCTIES
# ============================================================

def json_waarde(record):
    """Maak een RWS-meetrecord JSON-serialiseerbaar."""
    return {
        "tijd": record["tijd"].isoformat(),
        "waarde": record["waarde"],
        "locatie": record.get("locatie"),
    }


def bestandsnaam(locatie, parameter):
    """Bepaal de naam van het raw JSON-bestand."""
    naam = locatie.replace(".", "_")
    return OUTPUT_DIR / f"{naam}_{parameter}.json"


def maak_document(locatie, parameter, data, periode_uren):
    """
    Maak het raw download-document.

    Dit document bevat de door rws_api.py opgehaalde gegevens.
    Er vindt hier GEEN interpolatie of andere bewerking plaats.
    """
    return {
        "bron": "Rijkswaterstaat Waterwebservices",
        "opgehaald": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "locatie": locatie,
        "locatie_naam": LOCATIES[locatie]["naam"],
        "locatie_id": LOCATIES[locatie]["id"],
        "parameter": parameter,
        "grootheid": PARAMETERS[parameter]["grootheid"],
        "eenheid": data.eenheid,
        "periode_uren": periode_uren,
        "meting": [
            json_waarde(x)
            for x in data.meting
        ],
        "verwachting": [
            json_waarde(x)
            for x in data.verwachting
        ],
    }


def schrijf_json(document, output):
    """Schrijf JSON netjes en reproduceerbaar weg."""
    with output.open("w", encoding="utf-8") as f:
        json.dump(
            document,
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")


# ============================================================
# DOWNLOAD
# ============================================================

def download(locatie, parameter, periode_uren):
    """Download één locatie/parameter-combinatie."""

    data = get_river_data(
        locatie,
        parameter,
        uren=periode_uren,
    )

    totaal = len(data.meting) + len(data.verwachting)

    if totaal == 0:
        return None, 0, 0

    document = maak_document(
        locatie,
        parameter,
        data,
        periode_uren,
    )

    output = bestandsnaam(locatie, parameter)
    schrijf_json(document, output)

    return output, len(data.meting), len(data.verwachting)


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Download RWS-riviergegevens naar raw JSON-bestanden."
        )
    )

    parser.add_argument(
        "--hours",
        type=float,
        default=DEFAULT_PERIODE_UREN,
        help=(
            f"Aantal uren terug vanaf nu. "
            f"Standaard: {DEFAULT_PERIODE_UREN}."
        ),
    )

    parser.add_argument(
        "--location",
        choices=sorted(LOCATIES),
        help="Download alleen deze locatie.",
    )

    parser.add_argument(
        "--parameter",
        choices=sorted(PARAMETERS),
        help="Download alleen deze parameter.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Outputdirectory. Standaard: {OUTPUT_DIR}",
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()

    if args.hours <= 0:
        raise SystemExit("--hours moet groter zijn dan 0.")

    output_dir = args.output.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    locaties = (
        [args.location]
        if args.location
        else list(LOCATIES)
    )

    parameters = (
        [args.parameter]
        if args.parameter
        else list(DEFAULT_PARAMETERS)
    )

    # Zorg ervoor dat de globale outputdirectory aansluit
    # bij de gekozen --output-directory.
    global OUTPUT_DIR
    OUTPUT_DIR = output_dir

    print("=" * 70)
    print("RWS RAW DATA DOWNLOAD")
    print("=" * 70)
    print(f"Periode:      laatste {args.hours:g} uur")
    print(f"Output:       {output_dir}")
    print(f"Locaties:     {len(locaties)}")
    print(f"Parameters:   {', '.join(parameters)}")
    print("-" * 70)

    succesvol = 0
    geen_data = 0
    fouten = 0

    for locatie in locaties:
        for parameter in parameters:

            print(f"{locatie} | {parameter}")

            try:
                output, n_meting, n_verwachting = download(
                    locatie,
                    parameter,
                    args.hours,
                )

                if output is None:
                    print("  GEEN GEGEVENS")
                    geen_data += 1
                    continue

                print(f"  meting:       {n_meting:3d}")
                print(f"  verwachting:  {n_verwachting:3d}")
                print(f"  opgeslagen:   {output}")

                succesvol += 1

            except Exception as e:
                print(
                    f"  FOUT: "
                    f"{type(e).__name__}: {e}"
                )
                fouten += 1

            print()

    print("=" * 70)
    print("SAMENVATTING")
    print("=" * 70)
    print(f"Succesvol:    {succesvol}")
    print(f"Geen data:    {geen_data}")
    print(f"Fouten:       {fouten}")
    print("=" * 70)

    if fouten:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
