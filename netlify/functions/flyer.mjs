// Netlify Function: flyer / IG story screenshot -> strukturovaná akce přes Claude vision.
// Klíč drží server (NE prohlížeč). Secrets v Netlify env:
//   ANTHROPIC_API_KEY  (povinné)
//   ADMIN_PW           (povinné — heslo pro upload, ať to nespamuje kdokoliv)
//   ANTHROPIC_MODEL    (volitelné — aktuální vision model; jinak default níže)

const VENUES = `underground: kabinet, alterna, artbar, vodojemy, exit, industra, sklenka, mosilana, perpetuum, sibir, fraktal, enter, malaamerika, pulpit, vibe, teepee
public: fleda, sono, melodka, metro, semilasso, starapekarna, cabaret, boby, twofaces, sedmnebe, caribic, yacht, tabarin, discoxxl, musiclab, pitkin, charlieshat, vnclub, leitner, typos, amfik, spilberk, vankovka`;

const PROMPT = `Jsi extraktor akcí z plakátů a IG stories brněnské hudební scény. Z obrázku vytáhni JEDNU akci a vrať POUZE JSON (žádný další text):
{"title":"…","date":"YYYY-MM-DD","time":"HH:MM","venue":"<id nebo název>","genres":["KONCERT"],"mode":"underground","blurb":"<1 krátká věta>"}
Pravidla:
- Žánry vyber z: KONCERT, RAVE, PÁRTY, TECHNO, HOUSE, PUNK, JAZZ, INDIE, FOLK, AMBIENT, DNB (1–2 tagy).
- Když chybí rok, vezmi nejbližší budoucí. Když chybí čas, dej "20:00".
- venue: zkus napasovat na jedno z těchto ID; když to nejde, vrať název z plakátu:
${VENUES}
- mode: sklepní/DIY/techno/underground = "underground"; velké koncerty/festivaly/diskotéky = "public".
- Když na obrázku žádná akce není, vrať {"error":"na obrázku není akce"}.`;

export default async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  let body;
  try { body = await req.json(); } catch { return json({ error: "špatný JSON" }, 400); }
  const { image, media_type, pw } = body || {};
  if (!process.env.ADMIN_PW || pw !== process.env.ADMIN_PW) return json({ error: "špatné heslo" }, 401);
  if (!image) return json({ error: "chybí obrázek" }, 400);
  if (!process.env.ANTHROPIC_API_KEY) return json({ error: "na serveru chybí ANTHROPIC_API_KEY" }, 500);

  let r;
  try {
    r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": process.env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.ANTHROPIC_MODEL || "claude-3-5-sonnet-latest",
        max_tokens: 600,
        messages: [{
          role: "user",
          content: [
            { type: "image", source: { type: "base64", media_type: media_type || "image/jpeg", data: image } },
            { type: "text", text: PROMPT },
          ],
        }],
      }),
    });
  } catch (e) {
    return json({ error: "síť k LLM selhala: " + e }, 502);
  }
  if (!r.ok) return json({ error: "LLM vrátil " + r.status, detail: (await r.text()).slice(0, 300) }, 502);
  const data = await r.json();
  const text = (data.content && data.content[0] && data.content[0].text) || "";
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) return json({ error: "z odpovědi nešlo vyčíst JSON", raw: text.slice(0, 300) }, 422);
  try {
    return json(JSON.parse(m[0]));
  } catch {
    return json({ error: "neplatný JSON z LLM", raw: m[0].slice(0, 300) }, 422);
  }
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
}
