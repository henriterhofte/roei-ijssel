import {
    planTrip,
    simulateTrip
} from "./roeiplanner.js";


function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}


function bijna(a, b, marge = 0.001) {
    return Math.abs(a - b) <= marge;
}


/*
 * TEST 1
 *
 * 3 uur beschikbaar
 * 8 km/u roeien
 * 2 km/u stroom
 * stroomafwaarts
 *
 * heen = 10
 * terug = 6
 *
 * afstand = 11.25 km
 */
{
    const r = planTrip({
        vertrekMinuten: 0,
        terugkomstMinuten: 180,
        roeisnelheid: 8,
        stroomsnelheid: 2,
        richting: "stroomafwaarts"
    });

    assert(
        bijna(r.keerAfstandKm, 11.25),
        `Test 1 afstand: ${r.keerAfstandKm}`
    );

    assert(
        bijna(r.omkeerMinuten, 67.5),
        `Test 1 omkeer: ${r.omkeerMinuten}`
    );

    assert(
        bijna(r.terugkomstBerekendMinuten, 180),
        `Test 1 terugkomst: ${r.terugkomstBerekendMinuten}`
    );
}


/*
 * TEST 2
 *
 * Stroomopwaarts:
 * heen = 6
 * terug = 10
 *
 * Dezelfde totale beschikbare tijd
 * geeft dezelfde afstand.
 */
{
    const r = planTrip({
        vertrekMinuten: 0,
        terugkomstMinuten: 180,
        roeisnelheid: 8,
        stroomsnelheid: 2,
        richting: "stroomopwaarts"
    });

    assert(
        bijna(r.keerAfstandKm, 11.25),
        `Test 2 afstand: ${r.keerAfstandKm}`
    );

    assert(
        bijna(r.omkeerMinuten, 112.5),
        `Test 2 omkeer: ${r.omkeerMinuten}`
    );
}


/*
 * TEST 3
 *
 * Geen stroming.
 * Dan is het keerpunt exact halverwege.
 */
{
    const r = planTrip({
        vertrekMinuten: 0,
        terugkomstMinuten: 120,
        roeisnelheid: 8,
        stroomsnelheid: 0,
        richting: "stroomafwaarts"
    });

    assert(
        bijna(r.keerAfstandKm, 8),
        `Test 3 afstand: ${r.keerAfstandKm}`
    );

    assert(
        bijna(r.omkeerMinuten, 60),
        `Test 3 omkeer: ${r.omkeerMinuten}`
    );
}


/*
 * TEST 4
 *
 * Tijdafhankelijke stroming.
 *
 * Eerste uur 2 km/u,
 * daarna 3 km/u.
 */
{
    const afstand = simulateTrip({
        vertrekMinuten: 0,
        omkeerMinuten: 120,
        roeisnelheid: 8,
        richting: "stroomafwaarts",
        stapMinuten: 1,

        stroomfunctie: (tijd) =>
            tijd < 60 ? 2 : 3
    });

    /*
     * Eerste uur: 10 km
     * Tweede uur: 11 km
     * Totaal: 21 km
     */
    assert(
        bijna(afstand, 21),
        `Test 4 afstand: ${afstand}`
    );
}


console.log(
    "ALLE ROEIPLANNERTESTS GESLAAGD"
);
