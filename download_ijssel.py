from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta

from rws_api import LOCATIES, get_river_data


# ------------------------------------------------------------
# INSTELLINGEN
# ------------------------------------------------------------

PERIODE_UREN = 24

BASE_DIR = Path.home() / "rws_data"
OUTPUT_DIR = BASE_DIR / "downloads"

PARAMETERS = ("WATHTE", "Q")


# ------------------------------------------------------------
# HULPFUNCTIES
# ------------------------------------------------------------

def json_waarde(record):
    """Maak een meetrecord JSON-serialiseerbaar."""
    return {
        "tijd": record["tijd"].isoformat(),
        "waarde": record["waarde"],
        "locatie": record.get("locatie"),
    }


def bestandsnaam(locatie, parameter):
    """Veilige bestandsnaam."""
    naam = locatie.replace(".", "_")
    return OUTPUT_DIR / f"{naam}_{parameter}.json"


def maak_document(locatie, parameter, data):
    """Maak compact maar bruikbaar JSON-document."""

    return {
        "bron": "Rijkswaterstaat Waterwebservices",
        "opgehaald": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "locatie": locatie,
        "locatie_naam": LOCATIES[locatie]["naam"],
        "locatie_id": LOCATIES[locatie]["id"],
        "parameter": parameter,
        "eenheid": data.eenheid,
        "periode_uren": PERIODE_UREN,
        "meting": [
            json_waarde(x)
            for x in data.meting
        ],
        "verwachting": [
            json_waarde(x)
            for x in data.verwachting
        ],
    }


# ------------------------------------------------------------
# DOWNLOAD
# ------------------------------------------------------------

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("=" * 70)
    print("RWS IJssel/Boven-Rijn download")
    print("=" * 70)

    print(
        f"Periode: laatste {PERIODE_UREN} uur"
    )

    print(
        f"Output:  {OUTPUT_DIR}"
    )

    print("-" * 70)

    succesvol = 0
    geen_data = 0
    fouten = 0

    for locatie, info in LOCATIES.items():

        for parameter in PARAMETERS:

            print(
                f"{locatie} | {parameter}"
            )

            try:

                data = get_river_data(
                    locatie,
                    parameter,
                    uren=PERIODE_UREN,
                )

                totaal = (
                    len(data.meting)
                    + len(data.verwachting)
                )

                if totaal == 0:

                    print(
                        "  GEEN GEGEVENS"
                    )

                    geen_data += 1
                    continue

                document = maak_document(
                    locatie,
                    parameter,
                    data,
                )

                output = bestandsnaam(
                    locatie,
                    parameter,
                )

                with output.open(
                    "w",
                    encoding="utf-8"
                ) as f:

                    json.dump(
                        document,
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )

                print(
                    f"  meting:       "
                    f"{len(data.meting):3d}"
                )

                print(
                    f"  verwachting: "
                    f"{len(data.verwachting):3d}"
                )

                print(
                    f"  opgeslagen:   {output}"
                )

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

    print(
        f"Succesvol:    {succesvol}"
    )

    print(
        f"Geen data:    {geen_data}"
    )

    print(
        f"Fouten:       {fouten}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
