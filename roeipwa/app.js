function planTrip({ vertrekMinuten, terugkomstMinuten, roeisnelheid, stroomsnelheid, richting }) {
  if (!(terugkomstMinuten > vertrekMinuten)) throw new Error("Terugkomst moet na vertrek liggen");
  if (!(roeisnelheid > 0)) throw new Error("Roeisnelheid moet groter dan 0 zijn");
  if (!(stroomsnelheid >= 0)) throw new Error("Stroomsnelheid mag niet negatief zijn");
  if (richting !== "stroomopwaarts" && richting !== "stroomafwaarts") throw new Error("Ongeldige richting");
  const downstreamFirst = richting === "stroomafwaarts";
  const speedOut = roeisnelheid + (downstreamFirst ? stroomsnelheid : -stroomsnelheid);
  const speedBack = roeisnelheid + (downstreamFirst ? -stroomsnelheid : stroomsnelheid);
  if (speedOut <= 0 || speedBack <= 0) throw new Error("De stroming is te sterk om deze tocht te varen");
  const availableHours = (terugkomstMinuten - vertrekMinuten) / 60;
  const distance = availableHours / (1 / speedOut + 1 / speedBack);
  const outwardMinutes = distance / speedOut * 60;
  const returnMinutes = distance / speedBack * 60;
  return { keerAfstandKm: distance, omkeerMinuten: vertrekMinuten + outwardMinutes, heenMinuten: outwardMinutes, terugMinuten: returnMinutes };
}
const $ = (id) => document.getElementById(id);
const form = $("planner");
const result = $("resultaat");
const pad = (value) => String(value).padStart(2, "0");
const isoDate = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const time = (date) => `${pad(date.getHours())}:${pad(date.getMinutes())}`;
const duration = (minutes) => `${Math.floor(minutes / 60)} u ${Math.round(minutes % 60)} min`;
const weatherUrl = "https://api.open-meteo.com/v1/forecast?latitude=52.1407&longitude=6.1961&hourly=temperature_2m,wind_speed_10m,visibility,weather_code&daily=sunrise,sunset&timezone=Europe%2FAmsterdam&wind_speed_unit=kmh&forecast_days=16";

function fillQuarterOptions(id) {
  const select = $(id);
  for (let hour = 0; hour < 24; hour += 1) {
    for (let minute = 0; minute < 60; minute += 15) {
      const value = `${pad(hour)}:${pad(minute)}`;
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.append(option);
    }
  }
}

function setDateTime(prefix, date) {
  $(`${prefix}Date`).value = isoDate(date);
  $(`${prefix}Time`).value = time(date);
}

function getDateTime(prefix) {
  return new Date(`${$(`${prefix}Date`).value}T${$(`${prefix}Time`).value}:00`);
}

function nextQuarter() {
  const date = new Date();
  date.setSeconds(0, 0);
  date.setMinutes(Math.floor(date.getMinutes() / 15) * 15 + 15);
  return date;
}

function setEndAfterStart() {
  const start = getDateTime("departure");
  if (!Number.isNaN(+start)) setDateTime("arrival", new Date(+start + 2 * 60 * 60 * 1000));
}

fillQuarterOptions("departureTime");
fillQuarterOptions("arrivalTime");
const initialStart = nextQuarter();
setDateTime("departure", initialStart);
setDateTime("arrival", new Date(+initialStart + 2 * 60 * 60 * 1000));
function refreshWeather() {
  const start = getDateTime("departure");
  const end = getDateTime("arrival");
  if (!Number.isNaN(+start) && !Number.isNaN(+end) && end > start) {
    setCheck("daglicht", "Daglichtcontrole wordt geladen...");
    loadWeather(start, end);
  }
}

function refreshEndAndWeather() {
  setEndAfterStart();
  refreshWeather();
}

["departureDate", "departureTime"].forEach((id) => $(id).addEventListener("change", refreshEndAndWeather));
["arrivalDate", "arrivalTime"].forEach((id) => $(id).addEventListener("change", refreshWeather));

function showError(message) {
  result.hidden = false;
  $("tijd").textContent = "Nog niet berekend";
  $("tekst").textContent = message;
}

function setCheck(id, message, state = "") {
  const element = $(id);
  element.textContent = message;
  element.className = state;
}

function beaufort(kmh) {
  return [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118].findIndex((limit) => kmh < limit);
}

function weatherName(code) {
  if ([45, 48].includes(code)) return "mist";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "sneeuw";
  if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return "neerslag";
  if (code >= 95) return "onweer";
  return "droog";
}

function selectedHours(hourly, start, end) {
  return hourly.time.map((value, index) => ({ at: new Date(value), temperature: hourly.temperature_2m[index], wind: hourly.wind_speed_10m[index], visibility: hourly.visibility[index], code: hourly.weather_code[index] })).filter((sample) => sample.at >= new Date(+start - 60 * 60 * 1000) && sample.at <= end);
}

function renderWeather(samples) {
  const violations = [];
  const worstWind = Math.max(...samples.map((sample) => sample.wind));
  const lowestTemperature = Math.min(...samples.map((sample) => sample.temperature));
  const lowestVisibility = Math.min(...samples.map((sample) => sample.visibility));
  if (worstWind >= 29) violations.push(`windkracht ${beaufort(worstWind)} (${Math.round(worstWind)} km/u)`);
  if (lowestTemperature <= 0) violations.push(`vorst (${lowestTemperature.toFixed(1)} &deg;C)`);
  if (lowestVisibility < 200) violations.push(`zicht ${Math.round(lowestVisibility)} m`);
  const rows = samples.map((sample) => `<p class="weerregel ${sample.wind >= 29 || sample.temperature <= 0 || sample.visibility < 200 ? "afkeur" : ""}"><span>${time(sample.at)} &middot; ${weatherName(sample.code)}</span><span>${sample.temperature.toFixed(1)} &deg;C &middot; ${beaufort(sample.wind)} Bft &middot; ${Math.round(sample.visibility)} m</span></p>`).join("");
  $("weer").innerHTML = `<p class="${violations.length ? "afkeur" : ""}">${violations.length ? violations.join("; ") : "Weersverwachting voldoet aan de vaargrenzen."}</p>${rows}`;
}

function checkDaylight(data, start, end) {
  const startIndex = data.daily.time.indexOf(isoDate(start));
  const endIndex = data.daily.time.indexOf(isoDate(end));
  if (startIndex < 0 || endIndex < 0) return setCheck("daglicht", "Zonsopkomst en zonsondergang zijn voor deze datum niet beschikbaar.", "waarschuwing");
  const sunrise = new Date(data.daily.sunrise[startIndex]);
  const sunset = new Date(data.daily.sunset[endIndex]);
  setCheck("daglicht", `Daglicht: zonsopkomst ${time(sunrise)}, zonsondergang ${time(sunset)}.`, start < sunrise || end > sunset ? "afkeur" : "");
}

async function loadWeather(start, end) {
  $("weer").innerHTML = "<p>Weerverwachting wordt geladen...</p>";
  try {
    const response = await fetch(weatherUrl);
    if (!response.ok) throw new Error("Weersverwachting niet beschikbaar");
    const data = await response.json();
    checkDaylight(data, start, end);
    const samples = selectedHours(data.hourly, start, end);
    if (!samples.length) throw new Error("Voor deze datum is geen weersverwachting beschikbaar.");
    renderWeather(samples);
  } catch (error) {
    setCheck("daglicht", "Daglichtcontrole kon niet worden geladen.", "waarschuwing");
    $("weer").innerHTML = `<p class="waarschuwing">${error.message}</p>`;
  }
}

refreshWeather();

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const start = getDateTime("departure");
  const end = getDateTime("arrival");
  const rowing = +$("roei").value;
  const current = +$("nu").value;
  const expected = +$("later").value;
  const averageCurrent = (current + expected) / 2;
  const minutes = (end - start) / 60000;
  if (Number.isNaN(+start) || Number.isNaN(+end) || !(minutes > 0)) return showError("Kies een aankomsttijd na je vertrek.");
  if (!(rowing > averageCurrent && averageCurrent >= 0)) return showError("Je roeisnelheid moet hoger zijn dan de gemiddelde stroomsnelheid.");
  try {
    const trip = planTrip({ vertrekMinuten: 0, terugkomstMinuten: minutes, roeisnelheid: rowing, stroomsnelheid: averageCurrent, richting: form.elements.richting.value });
    const turn = new Date(+start + trip.omkeerMinuten * 60000);
    result.hidden = false;
    $("tijd").textContent = time(turn);
    $("tekst").textContent = `Keer dan om om uiterlijk om ${time(end)} terug te zijn.`;
    $("heen").textContent = duration(trip.heenMinuten);
    $("terugreis").textContent = duration(trip.terugMinuten);
    $("afstand").textContent = `${trip.keerAfstandKm.toFixed(1)} km`;
    setCheck("reservering", `Reservering: ${duration(minutes)} van ${time(start)} tot ${time(end)}.${minutes > 120 ? " Dit is langer dan de standaard 2 uur." : ""}`, minutes > 120 ? "waarschuwing" : "");
    setCheck("daglicht", "Daglichtcontrole wordt geladen...");
    localStorage.setItem("ijssel-roei", JSON.stringify({ rowing, current, expected }));
    loadWeather(start, end);
  } catch (error) { showError(error.message); }
});

const saved = JSON.parse(localStorage.getItem("ijssel-roei") || "null");
if (saved) { $("roei").value = saved.rowing; $("nu").value = saved.current; $("later").value = saved.expected; }
if (location.protocol !== "file:" && "serviceWorker" in navigator) navigator.serviceWorker.register("./service-worker.js");