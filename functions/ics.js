// Cloudflare Pages Function: GET /ics?t=&d=&tm=&loc=&url=&desc=
// Vrátí .ics se správným Content-Type → Apple Kalendář (iOS/macOS), Outlook desktop
// i ostatní klienti akci rovnou nabídnou k přidání (ne "stažení souboru").

const esc = (s) =>
  String(s || "").replace(/\\/g, "\\\\").replace(/([;,])/g, "\\$1").replace(/\r?\n/g, "\\n");

// Minimální VTIMEZONE pro Prahu — ať klient trefí správný čas i přes letní/zimní čas.
const VTIMEZONE = [
  "BEGIN:VTIMEZONE",
  "TZID:Europe/Prague",
  "BEGIN:DAYLIGHT",
  "TZOFFSETFROM:+0100",
  "TZOFFSETTO:+0200",
  "TZNAME:CEST",
  "DTSTART:19700329T020000",
  "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
  "END:DAYLIGHT",
  "BEGIN:STANDARD",
  "TZOFFSETFROM:+0200",
  "TZOFFSETTO:+0100",
  "TZNAME:CET",
  "DTSTART:19701025T030000",
  "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
  "END:STANDARD",
  "END:VTIMEZONE",
];

export async function onRequestGet(context) {
  const q = new URL(context.request.url).searchParams;
  const title = (q.get("t") || "Akce").slice(0, 200);
  const date = (q.get("d") || "").trim();          // YYYY-MM-DD
  const time = (q.get("tm") || "20:00").trim();    // HH:MM
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{1,2}:\d{2}$/.test(time)) {
    return new Response("Neplatné datum akce.", { status: 400 });
  }
  const [hh, mm] = time.split(":");
  const day = date.replace(/-/g, "");
  const start = `${day}T${hh.padStart(2, "0")}${mm}00`;
  const end = `${day}T${String((+hh + 3) % 24).padStart(2, "0")}${mm}00`;
  // akce po půlnoci končí další den
  const endDay = +hh + 3 >= 24
    ? new Date(Date.UTC(+date.slice(0, 4), +date.slice(5, 7) - 1, +date.slice(8, 10) + 1))
        .toISOString().slice(0, 10).replace(/-/g, "")
    : day;

  const stamp = new Date().toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//BRNO SCENA//CS",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    ...VTIMEZONE,
    "BEGIN:VEVENT",
    `UID:${day}-${Math.random().toString(36).slice(2)}@snabba.pages.dev`,
    `DTSTAMP:${stamp}`,
    `DTSTART;TZID=Europe/Prague:${start}`,
    `DTEND;TZID=Europe/Prague:${endDay}T${end.split("T")[1]}`,
    `SUMMARY:${esc(title)}`,
    `LOCATION:${esc(q.get("loc") || "Brno")}`,
    `DESCRIPTION:${esc(q.get("desc") || "")}`,
    `URL:${esc(q.get("url") || "https://snabba.pages.dev/")}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");

  return new Response(ics, {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": 'attachment; filename="brno-akce.ics"',
      "Cache-Control": "public, max-age=3600",
    },
  });
}
