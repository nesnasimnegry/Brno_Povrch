// Cloudflare Pages Function: /flyer — přečte akci z FOTKY FLYERU přes Workers AI (vision).
// Admin nahraje flyer (z IG stories apod.) → model vytáhne strukturovaná data → předvyplní formulář.
// Zdarma na Workers AI free tieru (~10k neuronů/den). Vyžaduje binding AI (dashboard) + secret ADMIN_PW.
//
// POST { image: "<base64 bez prefixu>", pw: "<ADMIN_PW>" }  →  { event: {...} }  | { error }

const MODEL = "@cf/meta/llama-3.2-11b-vision-instruct";

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });

const PROMPT = `You read a Czech music event flyer (concert, club night, rave, party) from the image.
Extract the event and return ONLY a compact JSON object, no prose, no markdown, with these keys:
"title" (event/headliner name), "date" (as printed, e.g. "14.2." or "14.2.2026" or ""), "time" (HH:MM or ""),
"venue" (club/venue name or ""), "lineup" (array of artist/DJ names, [] if none),
"price" (e.g. "200 Kč", "vstup zdarma" or ""), "genre" (ONE of TECHNO,HOUSE,RAVE,DNB,PÁRTY,KONCERT,PUNK,INDIE,JAZZ,FOLK,AMBIENT,HIPHOP or ""),
"desc" (one short sentence or "").
Czech flyers usually print the date as day.month. Return valid JSON only.`;

// "14.2." / "14. 2. 2026" / "2026-02-14" -> YYYY-MM-DD (chybí-li rok, ber nejbližší budoucí)
function normDate(raw) {
  const s = String(raw || "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const m = s.match(/(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?\s*(\d{4})?/);
  if (!m) return "";
  const d = +m[1], mo = +m[2];
  if (d < 1 || d > 31 || mo < 1 || mo > 12) return "";
  const now = new Date();
  let y = m[3] ? +m[3] : now.getFullYear();
  const iso = (yy) => `${yy}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  if (!m[3] && iso(y) < now.toISOString().slice(0, 10)) y += 1;  // datum v minulosti → příští rok
  return iso(y);
}

// vytáhne první {...} blok a bezpečně naparsuje (model občas obalí prózou)
function parseModel(text) {
  const t = String(text || "");
  const a = t.indexOf("{"), b = t.lastIndexOf("}");
  if (a < 0 || b <= a) return null;
  try { return JSON.parse(t.slice(a, b + 1)); } catch { return null; }
}

function cleanEvent(e) {
  const s = (v, n) => String(v == null ? "" : v).replace(/\s+/g, " ").trim().slice(0, n);
  const lineup = Array.isArray(e.lineup) ? e.lineup.map((x) => s(x, 60)).filter(Boolean).slice(0, 12) : [];
  return {
    title: s(e.title, 160),
    date: normDate(e.date),
    time: /^\d{1,2}:\d{2}$/.test(String(e.time || "")) ? s(e.time, 5) : "",
    venue: s(e.venue, 80),        // volný název — klient dorovná na venue id
    genre: s(e.genre, 20).toUpperCase(),
    price: s(e.price, 40),
    lineup,
    desc: s(e.desc, 300),
  };
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try { body = await request.json(); } catch { return json({ error: "špatný JSON" }, 400); }

  if (!env.ADMIN_PW || body.pw !== env.ADMIN_PW) return json({ error: "špatné heslo" }, 403);
  if (!env.AI) return json({ error: "Workers AI není nabindované (dashboard → binding 'AI')" }, 500);

  const b64 = String(body.image || "").replace(/^data:[^,]*,/, "");
  if (!b64) return json({ error: "chybí obrázek" }, 400);
  let bytes;
  try {
    const bin = atob(b64);
    bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  } catch { return json({ error: "obrázek nejde dekódovat" }, 400); }
  if (bytes.length > 4_000_000) return json({ error: "obrázek je moc velký (zmenši před nahráním)" }, 400);

  let out;
  try {
    out = await env.AI.run(MODEL, { image: [...bytes], prompt: PROMPT, max_tokens: 512 });
  } catch (e) {
    return json({ error: "vision model selhal: " + (e && e.message ? e.message : "neznámá chyba") }, 502);
  }

  const parsed = parseModel(out && out.response);
  if (!parsed) return json({ error: "model nevrátil čitelná data — zkus ostřejší foto", raw: (out && out.response || "").slice(0, 300) }, 422);

  const ev = cleanEvent(parsed);
  if (!ev.title && !ev.date) return json({ error: "z flyeru se nepodařilo nic přečíst" }, 422);
  return json({ event: ev });
}
