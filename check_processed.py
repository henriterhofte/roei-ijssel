from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta


# ============================================================
# INSTELLINGEN
# ============================================================

BASE_DIR = Path.home() / "rws_data"
DEFAULT_INPUT_DIR = BASE_DIR / "processed"

INTERVAL_MINUTES = 10
EXPECTED_STEP = timedelta(minutes=INTERVAL_MINUTES)


# ============================================================
# HULPFUNCTIES
# ============================================================

def parse_time(value):
    return datetime.fromisoformat(value)


def format_range(values):
    if not values:
        return "-"

    numeric = [
        float(x["waarde"])
        for x in values
        if x.get("waarde") is not None
    ]

    if not numeric:
        return "-"

    return f"{min(numeric):g} - {max(numeric):g}"


def analyse_reeks(values):
    if not values:
        return {
            "aantal": 0,
            "missing": 0,
            "observed": 0,
            "interpolated": 0,
            "forecast": 0,
            "overig": 0,
            "eerste": None,
            "laatste": None,
            "stap": None,
            "chronologisch": True,
            "dubbele_tijden": 0,
            "bereik": "-",
            "interpolatie_pct": 0.0,
        }

    tijden = [
        parse_time(x["tijd"])
        for x in values
        if x.get("tijd")
    ]

    observed = 0
    interpolated = 0
    forecast = 0
    overig = 0
    missing = 0

    for x in values:
        kwaliteit = x.get("kwaliteit")

        if x.get("waarde") is None:
            missing += 1

        if kwaliteit == "observed":
            observed += 1
        elif kwaliteit == "interpolated":
            interpolated += 1
        elif kwaliteit == "forecast":
            forecast += 1
        elif kwaliteit is not None:
            overig += 1

    chronologisch = all(
        tijden[i] < tijden[i + 1]
        for i in range(len(tijden) - 1)
    )

    dubbele_tijden = len(tijden) - len(set(tijden))

    stappen = [
        tijden[i + 1] - tijden[i]
        for i in range(len(tijden) - 1)
    ]

    unieke_stappen = sorted(set(stappen))

    if not stappen:
        stap = "-"
    elif len(unieke_stappen) == 1:
        minuten = unieke_stappen[0].total_seconds() / 60
        stap = f"{minuten:g} min"
    else:
        stap = "wisselend"

    totaal = len(values)

    interpolatie_pct = (
        100.0 * interpolated / totaal
        if totaal
        else 0.0
    )

    return {
        "aantal": totaal,
        "missing": missing,
        "observed": observed,
        "interpolated": interpolated,
        "forecast": forecast,
        "overig": overig,
        "eerste": tijden[0].isoformat() if tijden else None,
        "laatste": tijden[-1].isoformat() if tijden else None,
        "stap": stap,
        "chronologisch": chronologisch,
        "dubbele_tijden": dubbele_tijden,
        "bereik": format_range(values),
        "interpolatie_pct": interpolatie_pct,
    }


def print_reeks(label, result):
    print(f"  {label}")
    print(f"    aantal:          {result['aantal']}")
    print(f"    observed:        {result['observed']}")
    print(f"    interpolated:    {result['interpolated']}")
    print(f"    missing:         {result['missing']}")

    if result["forecast"] or label.upper() == "VERWACHTING":
        print(f"    forecast:        {result['forecast']}")

    if result["overig"]:
        print(f"    overig:          {result['overig']}")

    print(f"    interpolatie:    {result['interpolatie_pct']:.1f}%")
    print(f"    eerste:          {result['eerste']}")
    print(f"    laatste:         {result['laatste']}")
    print(f"    stap:            {result['stap']}")
    print(
        f"    chronologisch:   "
        f"{'JA' if result['chronologisch'] else 'NEE'}"
    )
    print(f"    dubbele tijden:  {result['dubbele_tijden']}")
    print(f"    bereik:          {result['bereik']}")


def controleer_reeks(result):
    fouten = []

    if result["aantal"] == 0:
        fouten.append("geen gegevens")

    if result["missing"] > 0:
        fouten.append(f"{result['missing']} missing")

    if not result["chronologisch"]:
        fouten.append("niet chronologisch")

    if result["dubbele_tijden"] > 0:
        fouten.append(
            f"{result['dubbele_tijden']} dubbele tijden"
        )

    if result["stap"] != f"{INTERVAL_MINUTES:g} min":
        fouten.append(
            f"verkeerde stap ({result['stap']})"
        )

    return fouten


# ============================================================
# BESTAND
# ============================================================

def controleer_bestand(path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    meting = data.get("meting", [])
    verwachting = data.get("verwachting", [])

    meting_result = analyse_reeks(meting)
    verwachting_result = analyse_reeks(verwachting)

    fouten = (
        controleer_reeks(meting_result)
        + controleer_reeks(verwachting_result)
    )

    print("-" * 70)
    print(f"{path.name}")

    print(
        f"  locatie:          "
        f"{data.get('locatie_naam', data.get('locatie', '-'))}"
    )
    print(
        f"  parameter:        "
        f"{data.get('parameter', '-')}"
    )
    print(
        f"  eenheid:          "
        f"{data.get('eenheid', '-')}"
    )

    print()
    print_reeks("METING", meting_result)

    print()
    print_reeks("VERWACHTING", verwachting_result)

    if meting_result["aantal"]:
        print()
        print(
            f"  Meetreeks kwaliteit: "
            f"{meting_result['observed']} observed + "
            f"{meting_result['interpolated']} interpolated"
        )

        if meting_result["interpolated"]:
            print(
                f"  Interpolatie-aandeel: "
                f"{meting_result['interpolatie_pct']:.1f}%"
            )

    if fouten:
        print()
        print("  STATUS: FOUT")
        for fout in fouten:
            print(f"    - {fout}")
        return False

    if meting_result["interpolated"] > 0:
        print()
        print("  STATUS: OK (met interpolatie)")
    else:
        print()
        print("  STATUS: OK")

    return True


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Controleer verwerkte RWS-data op "
            "10-minutenstructuur en datakwaliteit."
        )
    )

    parser.add_argument(
        "--directory",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=(
            f"Directory met processed JSON-bestanden. "
            f"Standaard: {DEFAULT_INPUT_DIR}"
        ),
    )

    args = parser.parse_args()

    directory = args.directory.expanduser()
    bestanden = sorted(directory.glob("*.json"))

    print("=" * 70)
    print("RWS PROCESSED DATA KWALITEITSCONTROLE")
    print("=" * 70)
    print(f"Directory:          {directory}")
    print(f"Interval:           {INTERVAL_MINUTES} minuten")
    print("Wijzigt bestanden:  NEE")
    print(f"Bestanden:          {len(bestanden)}")

    if not bestanden:
        print()
        print("GEEN JSON-BESTANDEN GEVONDEN")
        raise SystemExit(1)

    ok = 0
    aandacht = 0
    fouten = 0

    for path in bestanden:
        try:
            resultaat = controleer_bestand(path)

            if resultaat:
                ok += 1

                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                interpolated = sum(
                    1
                    for x in data.get("meting", [])
                    if x.get("kwaliteit") == "interpolated"
                )

                if interpolated:
                    aandacht += 1

        except Exception as e:
            fouten += 1
            print()
            print("  STATUS: FOUT")
            print(f"    {type(e).__name__}: {e}")

    print("=" * 70)
    print("SAMENVATTING")
    print("=" * 70)
    print(f"OK:                 {ok}")
    print(f"Met aandachtspunt:  {aandacht}")
    print(f"Fouten:             {fouten}")
    print("=" * 70)
    print("KLAAR")

    if fouten:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
