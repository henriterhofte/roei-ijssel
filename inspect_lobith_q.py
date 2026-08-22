import json
from pathlib import Path
from datetime import datetime

FILE = Path.home() / "rws_data" / "downloads" / "lobith_bovenrijn_tolkamer_Q.json"

with FILE.open(encoding="utf-8") as f:
    data = json.load(f)

print("=" * 70)
print("INSPECTIE LOBITH Q — AFWIJKENDE MEETINTERVALLEN")
print("=" * 70)
print(f"Bestand: {FILE}")
print()

metingen = data.get("meting", [])

if not metingen:
    print("GEEN METINGEN AANWEZIG")
    raise SystemExit

metingen = sorted(metingen, key=lambda x: x["tijd"])

print(f"Aantal metingen: {len(metingen)}")
print()

afwijkingen = []

for a, b in zip(metingen, metingen[1:]):
    t1 = datetime.fromisoformat(a["tijd"])
    t2 = datetime.fromisoformat(b["tijd"])
    minuten = (t2 - t1).total_seconds() / 60

    if minuten != 10:
        afwijkingen.append((t1, t2, minuten, a["waarde"], b["waarde"]))

if not afwijkingen:
    print("Geen afwijkende intervallen gevonden.")
else:
    print(f"Afwijkende intervallen: {len(afwijkingen)}")
    print()
    print("-" * 70)

    for i, (t1, t2, minuten, v1, v2) in enumerate(afwijkingen, 1):
        print(f"{i}.")
        print(f"   vorige meting : {t1.isoformat()}  {v1} m3/s")
        print(f"   volgende meting: {t2.isoformat()}  {v2} m3/s")
        print(f"   interval       : {minuten:.1f} minuten")
        print()

print("=" * 70)
print("EERSTE EN LAATSTE METING")
print("=" * 70)
print(metingen[0])
print(metingen[-1])

print()
print("=" * 70)
print("KLAAR")
print("=" * 70)
