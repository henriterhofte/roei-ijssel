/*
 * IJssel Roeiplanner
 *
 * Rekenlaag voor:
 *   vertrek -> stroomop/stroomaf -> omkeren -> terugkomst
 *
 * Snelheden in km/u.
 * Tijden in minuten vanaf vertrek.
 */

export function planTrip({
    vertrekMinuten,
    terugkomstMinuten,
    roeisnelheid,
    stroomsnelheid,
    richting
}) {
    if (!Number.isFinite(vertrekMinuten)) {
        throw new Error("Ongeldige vertrektijd");
    }

    if (!Number.isFinite(terugkomstMinuten)) {
        throw new Error("Ongeldige terugkomsttijd");
    }

    if (terugkomstMinuten <= vertrekMinuten) {
        throw new Error(
            "Terugkomst moet na vertrek liggen"
        );
    }

    if (!(roeisnelheid > 0)) {
        throw new Error(
            "Roeisnelheid moet groter dan 0 zijn"
        );
    }

    if (stroomsnelheid < 0) {
        throw new Error(
            "Stroomsnelheid mag niet negatief zijn"
        );
    }

    if (
        richting !== "stroomopwaarts" &&
        richting !== "stroomafwaarts"
    ) {
        throw new Error(
            "Richting moet stroomopwaarts of stroomafwaarts zijn"
        );
    }

    const beschikbareTijd =
        terugkomstMinuten - vertrekMinuten;

    let snelheidHeen;
    let snelheidTerug;

    if (richting === "stroomafwaarts") {
        snelheidHeen =
            roeisnelheid + stroomsnelheid;

        snelheidTerug =
            roeisnelheid - stroomsnelheid;
    } else {
        snelheidHeen =
            roeisnelheid - stroomsnelheid;

        snelheidTerug =
            roeisnelheid + stroomsnelheid;
    }

    if (snelheidHeen <= 0) {
        throw new Error(
            "Stroming is te sterk om stroomopwaarts te varen"
        );
    }

    if (snelheidTerug <= 0) {
        throw new Error(
            "Terugvaren tegen de stroom in is niet mogelijk"
        );
    }

    /*
     * beschikbare tijd =
     *
     *     afstand / snelheidHeen
     *   + afstand / snelheidTerug
     *
     * Alles in uren.
     */
    const beschikbareUren =
        beschikbareTijd / 60;

    const keerAfstand =
        beschikbareUren /
        (
            1 / snelheidHeen +
            1 / snelheidTerug
        );

    const heenUren =
        keerAfstand / snelheidHeen;

    const terugUren =
        keerAfstand / snelheidTerug;

    const omkeerMinuten =
        vertrekMinuten +
        heenUren * 60;

    const terugkomstBerekend =
        omkeerMinuten +
        terugUren * 60;

    return {
        vertrekMinuten,
        terugkomstMinuten,

        omkeerMinuten,

        keerAfstandKm: keerAfstand,

        snelheidHeenKmh: snelheidHeen,
        snelheidTerugKmh: snelheidTerug,

        heenMinuten: heenUren * 60,
        terugMinuten: terugUren * 60,

        terugkomstBerekendMinuten:
            terugkomstBerekend,

        margeMinuten:
            terugkomstMinuten -
            terugkomstBerekend
    };
}


/*
 * Tijdafhankelijke variant.
 *
 * Dit is bewust nog eenvoudig:
 * stroomsnelheid is een functie van tijd.
 *
 * De simulatie loopt in kleine tijdstappen.
 * Daarmee kunnen we later rechtstreeks de
 * 10-minuten RWS-voorspelling gebruiken.
 */

export function simulateTrip({
    vertrekMinuten,
    omkeerMinuten,
    roeisnelheid,
    stroomfunctie,
    richting,
    stapMinuten = 1
}) {
    if (!(stapMinuten > 0)) {
        throw new Error(
            "stapMinuten moet groter dan 0 zijn"
        );
    }

    let afstand = 0;

    for (
        let tijd = vertrekMinuten;
        tijd < omkeerMinuten;
        tijd += stapMinuten
    ) {
        const stroom =
            stroomfunctie(tijd);

        let snelheid;

        if (richting === "stroomafwaarts") {
            snelheid =
                roeisnelheid + stroom;
        } else {
            snelheid =
                roeisnelheid - stroom;
        }

        if (snelheid <= 0) {
            throw new Error(
                "Effectieve snelheid is niet positief"
            );
        }

        afstand +=
            snelheid *
            (stapMinuten / 60);
    }

    return afstand;
}
