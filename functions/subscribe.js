// Cloudflare Pages Function: POST /subscribe
// Uloží odběratele {email, koho sleduje} do KV namespace `SUBS`.
// Upsert podle e-mailu (re-odeslání aktualizuje follows). Token = pro odhlášení.

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "špatný JSON" }, 400);
  }
  const email = String(body.email || "").trim().toLowerCase();
  const follows = body.follows || {};
  const venues = Array.isArray(follows.venues) ? follows.venues.slice(0, 100) : [];
  const artists = Array.isArray(follows.artists) ? follows.artists.slice(0, 100) : [];

  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return json({ error: "neplatný e-mail" }, 400);
  if (!body.consent) return json({ error: "chybí souhlas" }, 400);
  if (!venues.length && !artists.length) return json({ error: "nic nesleduješ" }, 400);
  if (!env.SUBS) return json({ error: "úložiště není nastavené" }, 500);

  const key = "sub:" + email;
  const existing = await env.SUBS.get(key, "json");
  const now = new Date().toISOString();
  const rec = {
    email,
    venues,
    artists,
    token: (existing && existing.token) || crypto.randomUUID(),
    created: (existing && existing.created) || now,
    updated: now,
  };
  await env.SUBS.put(key, JSON.stringify(rec));
  return json({ success: true, updated: !!existing });
}
