#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


LOCATION_TERMS = [
    "ijssel",
    "zutphen",
    "deventer",
    "ijsselkop",
    "lobith",
    "pannerden",
    "dieren",
    "doesburg",
    "olst",
    "wijhe",
    "westervoort",
    "kampen",
]


QUANTITY_TERMS = [
    "afvoer",
    "debiet",
    "waterstand",
    "waterhoogte",
    "stroomsnelheid",
    "stroming",
    "stroomrichting",
    "snelheid",
    "richting",
]


def norm(value):
    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(
            norm(v)
            for v in value.values()
        )

    if isinstance(value, list):
        return " ".join(
            norm(v)
            for v in value
        )

    return str(value).lower()


def code(obj):
    if isinstance(obj, dict):
        return obj.get("Code", "")
    return ""


def desc(obj):
    if isinstance(obj, dict):
        return obj.get(
            "Omschrijving",
            ""
        )
    return ""


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        default="rws_data/rws_catalogus.json"
    )

    parser.add_argument(
        "--out",
        default="rws_data"
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_dir = Path(args.out)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print()
    print("=" * 70)
    print("RWS IJssel discovery")
    print("=" * 70)
    print()

    with open(
        input_file,
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    metadata = data[
        "AquoMetadataLijst"
    ]

    locations = data[
        "LocatieLijst"
    ]

    links = data[
        "AquoMetadataLocatieLijst"
    ]

    print(
        f"Metadata : {len(metadata):,}"
    )

    print(
        f"Locaties : {len(locations):,}"
    )

    print(
        f"Koppelingen : {len(links):,}"
    )

    print()

    # ---------------------------------------------------------
    # Index locaties
    # ---------------------------------------------------------

    location_by_id = {
        item["Locatie_MessageID"]: item
        for item in locations
    }

    # ---------------------------------------------------------
    # Index metadata
    # ---------------------------------------------------------

    metadata_by_id = {
        item["AquoMetadata_MessageID"]: item
        for item in metadata
    }

    # ---------------------------------------------------------
    # Eerst bepalen welke locaties relevant zijn
    # ---------------------------------------------------------

    relevant_locations = {}

    for location in locations:

        searchable = norm(location)

        if any(
            term in searchable
            for term in LOCATION_TERMS
        ):

            relevant_locations[
                location["Locatie_MessageID"]
            ] = location

    print(
        f"Relevante locaties: "
        f"{len(relevant_locations)}"
    )

    # ---------------------------------------------------------
    # Koppelingen verwerken
    # ---------------------------------------------------------

    results = []

    seen = set()

    for link in links:

        metadata_id = link[
            "AquoMetaData_MessageID"
        ]

        location_id = link[
            "Locatie_MessageID"
        ]

        location = location_by_id.get(
            location_id
        )

        metadata_item = metadata_by_id.get(
            metadata_id
        )

        if (
            location is None
            or metadata_item is None
        ):
            continue

        if (
            location_id
            not in relevant_locations
        ):
            continue

        # Alleen fysisch relevante parameters
        searchable = norm(
            metadata_item
        )

        if not any(
            term in searchable
            for term in QUANTITY_TERMS
        ):
            continue

        key = (
            location_id,
            metadata_id
        )

        if key in seen:
            continue

        seen.add(key)

        results.append({
            "location_id": location_id,

            "location_code":
                location.get(
                    "Code",
                    ""
                ),

            "location_name":
                location.get(
                    "Naam",
                    ""
                ),

            "location_description":
                location.get(
                    "Omschrijving",
                    ""
                ),

            "lat":
                location.get(
                    "Lat"
                ),

            "lon":
                location.get(
                    "Lon"
                ),

            "metadata_id":
                metadata_id,

            "compartiment_code":
                code(
                    metadata_item.get(
                        "Compartiment"
                    )
                ),

            "grootheid_code":
                code(
                    metadata_item.get(
                        "Grootheid"
                    )
                ),

            "grootheid":
                desc(
                    metadata_item.get(
                        "Grootheid"
                    )
                ),

            "parameter_code":
                code(
                    metadata_item.get(
                        "Parameter"
                    )
                ),

            "parameter":
                desc(
                    metadata_item.get(
                        "Parameter"
                    )
                ),

            "eenheid_code":
                code(
                    metadata_item.get(
                        "Eenheid"
                    )
                ),

            "eenheid":
                desc(
                    metadata_item.get(
                        "Eenheid"
                    )
                ),

            "hoedanigheid_code":
                code(
                    metadata_item.get(
                        "Hoedanigheid"
                    )
                ),

            "hoedanigheid":
                desc(
                    metadata_item.get(
                        "Hoedanigheid"
                    )
                ),

            "typering_code":
                code(
                    metadata_item.get(
                        "Typering"
                    )
                ),

            "typering":
                desc(
                    metadata_item.get(
                        "Typering"
                    )
                ),

            "proces_type":
                metadata_item.get(
                    "ProcesType"
                ),

            "omschrijving":
                metadata_item.get(
                    "Parameter_Wat_Omschrijving",
                    ""
                ),
        })

    # ---------------------------------------------------------
    # Sorteren
    # ---------------------------------------------------------

    results.sort(
        key=lambda x: (
            x["location_code"],
            x["grootheid_code"],
            x["parameter_code"],
            x["metadata_id"],
        )
    )

    # ---------------------------------------------------------
    # JSON
    # ---------------------------------------------------------

    json_file = (
        output_dir /
        "relevante_meetreeksen.json"
    )

    with open(
        json_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    # ---------------------------------------------------------
    # CSV
    # ---------------------------------------------------------

    csv_file = (
        output_dir /
        "relevante_meetreeksen.csv"
    )

    import csv

    if results:

        fields = list(
            results[0].keys()
        )

        with open(
            csv_file,
            "w",
            encoding="utf-8",
            newline=""
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fields
            )

            writer.writeheader()

            writer.writerows(
                results
            )

    # ---------------------------------------------------------
    # Output
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print(
        f"RELEVANTE MEETREEKSEN: "
        f"{len(results)}"
    )
    print("=" * 70)

    previous_location = None

    for row in results:

        location = (
            row["location_code"]
        )

        if location != previous_location:

            print()
            print("-" * 70)

            print(
                location,
                "|",
                row["location_name"]
            )

            print(
                f"  coordinates: "
                f"{row['lat']}, "
                f"{row['lon']}"
            )

            print("-" * 70)

            previous_location = location

        print(
            f"  {row['grootheid_code']:15}"
            f" {row['grootheid'][:35]:35}"
            f" | {row['eenheid_code']:10}"
            f" | {row['proces_type']}"
        )

        if row["parameter"]:
            print(
                f"      parameter: "
                f"{row['parameter_code']} "
                f"{row['parameter']}"
            )

        if row["omschrijving"]:
            print(
                f"      {row['omschrijving']}"
            )

    print()
    print("=" * 70)
    print("OUTPUT")
    print("=" * 70)

    print(
        json_file
    )

    print(
        csv_file
    )

    print()


if __name__ == "__main__":
    main()

