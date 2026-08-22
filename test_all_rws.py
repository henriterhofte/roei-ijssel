from rws_api import LOCATIES, get_river_data


PERIODE_UREN = 6


print("=" * 70)
print("RWS IJssel/Boven-Rijn integratietest")
print("=" * 70)
print(f"Periode: laatste {PERIODE_UREN} uur")
print("-" * 70)


for locatie, info in LOCATIES.items():

    print()
    print("-" * 70)
    print(f"{locatie} | {info['naam']}")

    for parameter in ("WATHTE", "Q"):

        try:
            data = get_river_data(
                locatie,
                parameter,
                uren=PERIODE_UREN,
            )

            print(
                f"  {parameter:6s} "
                f"meting={len(data.meting):3d} "
                f"verwachting={len(data.verwachting):3d}"
            )

            if data.meting:
                laatste = data.meting[-1]

                print(
                    "         laatste meting:       "
                    f"{laatste['tijd'].isoformat()} "
                    f"{laatste['waarde']} "
                    f"{data.eenheid}"
                )
            else:
                print(
                    "         laatste meting:       "
                    "GEEN GEGEVENS"
                )

            if data.verwachting:
                laatste = data.verwachting[-1]

                print(
                    "         laatste verwachting: "
                    f"{laatste['tijd'].isoformat()} "
                    f"{laatste['waarde']} "
                    f"{data.eenheid}"
                )
            else:
                print(
                    "         laatste verwachting: "
                    "GEEN GEGEVENS"
                )

        except Exception as e:

            print(
                f"  {parameter:6s} FOUT: "
                f"{type(e).__name__}: {e}"
            )


print()
print("=" * 70)
print("KLAAR")
print("=" * 70)
