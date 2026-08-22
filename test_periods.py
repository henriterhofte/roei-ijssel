from rws_api import get_river_data


LOCATIE = "olst"
PARAMETER = "Q"


print("=" * 70)
print("RWS PERIODETEST")
print("=" * 70)

for uren in (1, 6, 12, 24, 48):

    print()
    print("-" * 70)
    print(f"Periode: laatste {uren} uur")

    try:
        data = get_river_data(
            LOCATIE,
            PARAMETER,
            uren=uren,
        )

        print(
            f"meting={len(data.meting)} "
            f"verwachting={len(data.verwachting)}"
        )

        if data.meting:
            print(
                "eerste meting:",
                data.meting[0]["tijd"].isoformat(),
                data.meting[0]["waarde"],
            )
            print(
                "laatste meting:",
                data.meting[-1]["tijd"].isoformat(),
                data.meting[-1]["waarde"],
            )

        if data.verwachting:
            print(
                "eerste verwachting:",
                data.verwachting[0]["tijd"].isoformat(),
                data.verwachting[0]["waarde"],
            )
            print(
                "laatste verwachting:",
                data.verwachting[-1]["tijd"].isoformat(),
                data.verwachting[-1]["waarde"],
            )

    except Exception as e:
        print(
            "FOUT:",
            type(e).__name__,
            e,
        )

print()
print("=" * 70)
print("KLAAR")
print("=" * 70)
