from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


API_URL = (
    "https://ddapi20-waterwebservices.rijkswaterstaat.nl/"
    "ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"
)


# ------------------------------------------------------------
# LOCATIES
# ------------------------------------------------------------

LOCATIES = {
    "zutphen.ijssel": {
        "id": "zutphen.ijssel",
        "naam": "Zutphen, IJssel",
        "lat": 52.154000,
        "lon": 6.182000,
    },
    "deventer": {
        "id": "deventer",
        "naam": "Deventer",
        "lat": 52.251194,
        "lon": 6.153247,
    },
    "dieren.ijssel": {
        "id": "dieren.ijssel",
        "naam": "Dieren, IJssel",
        "lat": 52.049838,
        "lon": 6.113642,
    },
    "wijhe": {
        "id": "wijhe",
        "naam": "Wijhe",
        "lat": 52.387000,
        "lon": 6.126917,
    },
    "olst": {
        "id": "olst",
        "naam": "Olst",
        "lat": 52.342010,
        "lon": 6.104480,
    },
    "westervoort.ijsselkop": {
        "id": "westervoort.ijsselkop",
        "naam": "Westervoort, IJsselkop",
        "lat": 51.950700,
        "lon": 5.953000,
    },
    "lobith.bovenrijn.tolkamer": {
        "id": "lobith.bovenrijn.tolkamer",
        "naam": "Lobith, Boven-Rijn, Tolkamer",
        "lat": 51.849500,
        "lon": 6.102400,
    },
}


PARAMETERS = {
    "WATHTE": {
        "grootheid": "Waterhoogte",
        "eenheid": "cm",
    },
    "Q": {
        "grootheid": "Debiet",
        "eenheid": "m3/s",
    },
}


# ------------------------------------------------------------
# DATASTRUCTUUR
# ------------------------------------------------------------

@dataclass
class RiverData:
    locatie: str
    locatie_id: str
    parameter: str
    eenheid: str
    meting: list
    verwachting: list


# ------------------------------------------------------------
# TIJD
# ------------------------------------------------------------

def lokale_tijd():
    """
    Lokale tijd van Android/Termux inclusief UTC-offset.

    Geen zoneinfo/tzdata nodig.
    """
    return datetime.now().astimezone()


def parse_time(value):
    """
    RWS ISO timestamp naar datetime.

    We behouden de offset die RWS meestuurt.
    """
    return datetime.fromisoformat(value)


def format_time(value):
    """
    datetime -> ISO timestamp voor RWS.

    Als geen timezone aanwezig is, nemen we de lokale
    Android/Termux timezone.
    """
    if value.tzinfo is None:
        value = value.astimezone()

    return value.isoformat(timespec="milliseconds")


# ------------------------------------------------------------
# RWS REQUEST
# ------------------------------------------------------------

def _request(location_id, parameter, van, tot, timeout=30):
    """
    Vraag één RWS meetreeks op.

    HTTP 204 = geen gegevens voor deze combinatie.
    Dat is geen fout.
    """

    payload = {
        "Locatie": {
            "Code": str(location_id)
        },
        "AquoPlusWaarnemingMetadata": {
            "AquoMetadata": {
                "Compartiment": {
                    "Code": "OW"
                },
                "Grootheid": {
                    "Code": parameter
                }
            }
        },
        "Periode": {
            "Begindatumtijd": format_time(van),
            "Einddatumtijd": format_time(tot)
        }
    }

    body = json.dumps(payload).encode("utf-8")

    request = Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read()

    except HTTPError as e:
        if e.code == 204:
            return None

        raise RuntimeError(
            f"RWS HTTP fout {e.code}: {e.reason}"
        ) from e

    except URLError as e:
        raise RuntimeError(
            f"RWS netwerkfout: {e.reason}"
        ) from e

    # HTTP 204 / lege body = geen gegevens
    if status == 204 or not raw:
        return None

    try:
        result = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "RWS gaf geen geldige JSON terug."
        ) from e

    if not result.get("Succesvol", False):
        raise RuntimeError(
            f"RWS meldt geen succes: {result}"
        )

    return result


# ------------------------------------------------------------
# PARSEN
# ------------------------------------------------------------

def _parse_response(response):
    """
    Zet RWS response om naar twee lijsten:
    meting en verwachting.
    """

    meting = []
    verwachting = []

    if not response:
        return meting, verwachting

    for reeks in response.get("WaarnemingenLijst", []):

        aquo = reeks.get("AquoMetadata", {})
        proces_type = aquo.get("ProcesType")

        locatie_info = reeks.get("Locatie", {})

        for item in reeks.get("MetingenLijst", []):

            meetwaarde = item.get("Meetwaarde", {})
            waarde = meetwaarde.get("Waarde_Numeriek")

            if waarde is None:
                continue

            tijdstip = item.get("Tijdstip")

            if not tijdstip:
                continue

            record = {
                "tijd": parse_time(tijdstip),
                "waarde": float(waarde),
                "locatie": locatie_info.get("Code"),
            }

            if proces_type == "meting":
                meting.append(record)

            elif proces_type == "verwachting":
                verwachting.append(record)

    meting.sort(key=lambda x: x["tijd"])
    verwachting.sort(key=lambda x: x["tijd"])

    return meting, verwachting


# ------------------------------------------------------------
# HOOFDFUNCTIE
# ------------------------------------------------------------

def get_river_data(
    locatie,
    parameter,
    uren=24,
    tot=None,
):
    """
    Haal RWS-riviergegevens op.

    Parameters
    ----------
    locatie : str
        Bijvoorbeeld 'zutphen.ijssel' of 'olst'.

    parameter : str
        'WATHTE' of 'Q'.

    uren : float
        Aantal uren terug vanaf 'tot'.

    tot : datetime, optional
        Eindtijd. Standaard lokale tijd.

    Returns
    -------
    RiverData
    """

    if locatie not in LOCATIES:
        raise ValueError(
            f"Onbekende locatie: {locatie}"
        )

    if parameter not in PARAMETERS:
        raise ValueError(
            f"Onbekende parameter: {parameter}"
        )

    location = LOCATIES[locatie]

    if tot is None:
        eind = lokale_tijd()
    else:
        eind = tot

        if eind.tzinfo is None:
            eind = eind.astimezone()

    begin = eind - timedelta(hours=uren)

    response = _request(
        location["id"],
        parameter,
        begin,
        eind,
    )

    meting, verwachting = _parse_response(response)

    return RiverData(
        locatie=locatie,
        locatie_id=location["id"],
        parameter=parameter,
        eenheid=PARAMETERS[parameter]["eenheid"],
        meting=meting,
        verwachting=verwachting,
    )


# ------------------------------------------------------------
# EENVOUDIGE TEST
# ------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 70)
    print("RWS API test")
    print("=" * 70)

    print(
        "Lokale tijd:",
        lokale_tijd().isoformat()
    )

    print()

    data = get_river_data(
        "zutphen.ijssel",
        "WATHTE",
        uren=6,
    )

    print("=" * 70)
    print(
        f"{data.locatie} | "
        f"{data.parameter} | "
        f"{data.eenheid}"
    )
    print("=" * 70)

    print()
    print(
        f"METING: {len(data.meting)} records"
    )

    for record in data.meting[-5:]:
        print(
            record["tijd"].isoformat(),
            record["waarde"]
        )

    print()
    print(
        f"VERWACHTING: "
        f"{len(data.verwachting)} records"
    )

    for record in data.verwachting[-5:]:
        print(
            record["tijd"].isoformat(),
            record["waarde"]
        )
