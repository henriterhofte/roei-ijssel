from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime


DOWNLOAD_DIR = Path.home() / "rws_data" / "downloads"
EXPECTED_MINUTES = 10


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def inspect_series(records: list[dict]) -> dict:
    if not records:
        return {
            "aantal": 0,
            "eerste": None,
            "laatste": None,
            "intervallen": [],
            "afwijkingen": [],
            "dubbele_tijden": [],
            "ontbrekende_punten": None,
            "verwacht": None,
            "chronologisch": True,
        }

    times = [parse_time(r["tijd"]) for r in records]

    # Controle chronologie
    chronologisch = all(
        b >= a for a, b in zip(times, times[1:])
    )

    # Dubbele tijdstippen
    seen = set()
    dubbele_tijden = []

    for t in times:
        if t in seen:
            dubbele_tijden.append(t)
        seen.add(t)

    # Intervallen
    intervallen = []

    for a, b in zip(times, times[1:]):
        minuten = (b - a).total_seconds() / 60
        intervallen.append(minuten)

    afwijkingen = [
        minuten
        for minuten in intervallen
        if minuten != EXPECTED_MINUTES
    ]

    # Verwacht aantal punten op basis van de eerste/laatste timestamp.
    if len(times) >= 2:
        totale_minuten = (times[-1] - times[0]).total_seconds() / 60
        verwacht = int(totale_minuten / EXPECTED_MINUTES) + 1

        # Alleen echte ontbrekende tijdstappen tellen.
        ontbrekende_punten = sum(
            max(0, int(round(minuten / EXPECTED_MINUTES)) - 1)
            for minuten in intervallen
            if minuten > EXPECTED_MINUTES
        )
    else:
        verwacht = len(times)
        ontbrekende_punten = 0

    return {
        "aantal": len(records),
        "eerste": times[0],
        "laatste": times[-1],
        "intervallen": intervallen,
        "afwijkingen": afwijkingen,
        "dubbele_tijden": dubbele_tijden,
        "ontbrekende_punten": ontbrekende_punten,
        "verwacht": verwacht,
        "chronologisch": chronologisch,
    }


def print_series(label: str, records: list[dict], eenheid: str):
    print(f"    {label}")
    
    if not records:
        print("      GEEN GEGEVENS")
        return

    info = inspect_series(records)
    waarden = [float(r["waarde"]) for r in records]

    intervallen = info["intervallen"]

    if intervallen:
        min_stap = min(intervallen)
        max_stap = max(intervallen)
        staptekst = f"{min_stap:.1f} - {max_stap:.1f} min"
    else:
        staptekst = "n.v.t."

    print(f"      aantal:          {info['aantal']}")
    print(f"      verwacht:        {info['verwacht']}")
    print(f"      ontbrekend:      {info['ontbrekende_punten']}")
    print(f"      eerste:          {info['eerste'].isoformat()}")
    print(f"      laatste:         {info['laatste'].isoformat()}")
    print(f"      stap:            {staptekst}")
    print(f"      afwijkingen:     {len(info['afwijkingen'])}")
    print(
        f"      chronologisch:   "
        f"{'JA' if info['chronologisch'] else 'NEE'}"
    )
    print(f"      dubbele tijden:  {len(info['dubbele_tijden'])}")
    print(
        f"      bereik:          "
        f"{min(waarden)} - {max(waarden)} {eenheid}"
    )

    # Toon de exacte gaten.
    if info["afwijkingen"]:
        print("      GATEN:")

        times = [
            parse_time(r["tijd"])
            for r in records
        ]

        for a, b in zip(times, times[1:]):
            minuten = (b - a).total_seconds() / 60

            if minuten > EXPECTED_MINUTES:
                ontbrekend = (
                    int(round(minuten / EXPECTED_MINUTES)) - 1
                )

                print(
                    f"        {a.isoformat()} -> "
                    f"{b.isoformat()} : "
                    f"{minuten:.0f} min "
                    f"({ontbrekend} ontbrekend punt)"
                )


def main():
    print("=" * 70)
    print("RWS DOWNLOAD KWALITEITSCONTROLE")
    print("=" * 70)
    print(f"Directory: {DOWNLOAD_DIR}")
    print()

    files = sorted(DOWNLOAD_DIR.glob("*.json"))

    print(f"Bestanden: {len(files)}")
    print()

    totaal_ok = 0
    totaal_problemen = 0

    for path in files:
        print("-" * 70)
        print(path.name)

        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"    FOUT bij lezen: {type(e).__name__}: {e}")
            totaal_problemen += 1
            continue

        locatie = data.get("locatie", "?")
        parameter = data.get("parameter", "?")
        eenheid = data.get("eenheid", "?")

        print(f"    locatie:          {locatie}")
        print(f"    parameter:        {parameter}")
        print(f"    eenheid:          {eenheid}")

        meting = data.get("meting", [])
        verwachting = data.get("verwachting", [])

        print()
        print_series("METING", meting, eenheid)

        print()
        print_series("VERWACHTING", verwachting, eenheid)

        problemen = False

        for records in (meting, verwachting):
            if not records:
                continue

            info = inspect_series(records)

            if (
                not info["chronologisch"]
                or info["dubbele_tijden"]
                or info["ontbrekende_punten"]
                or info["afwijkingen"]
            ):
                problemen = True

        if problemen:
            totaal_problemen += 1
        else:
            totaal_ok += 1

    print()
    print("=" * 70)
    print("SAMENVATTING")
    print("=" * 70)
    print(f"OK:                {totaal_ok}")
    print(f"Met aandachtspunt: {totaal_problemen}")
    print("=" * 70)
    print("KLAAR")
    print("=" * 70)


if __name__ == "__main__":
    main()
