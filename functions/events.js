// Cloudflare Pages Function: /events — komunitní akce (submit + admin schvalování).
// Ukládá do stejného KV jako odběratelé (binding SUBS), prefixy klíčů:
//   pending:<id>   — odeslaná akce čeká na schválení
//   approved:<id>  — schválená akce (web ji ukáže všem)
// Admin operace ověřují heslo proti env ADMIN_PW (Cloudflare secret, ne v kódu).

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });

async function listByPrefix(env, prefix) {
  const out = [];
  let cursor;
  do {
    const l = await env.SUBS.list({ prefix, cursor });
    for (const k of l.keys) {
      const rec = await env.SUBS.get(k.name, "json");
      if (rec) out.push(rec);
    }
    cursor = l.list_complete ? null : l.cursor;
  } while (cursor);
  return out;
}

// Očisti akci na povolená pole (žádný cizí JS do dat).
function cleanEvent(e) {
  const s = (v, n) => String(v == null ? "" : v).slice(0, n);
  const genres = Array.isArray(e.genres) ? e.genres.slice(0, 4).map((g) => s(g, 20)) : [];
  const lineup = Array.isArray(e.lineup) ? e.lineup.slice(0, 12).map((x) => s(x, 60)) : [];
  return {
    title: s(e.title, 160), date: s(e.date, 10), time: s(e.time, 5) || "20:00",
    venue: s(e.venue, 40), mode: e.mode === "underground" ? "underground" : "public",
    genres, price: s(e.price, 40), ticket: s(e.ticket, 300),
    lineup, blurb: s(e.blurb, 90), desc: s(e.desc, 400),
    venueName: s(e.venueName, 80),
  };
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const pw = new URL(request.url).searchParams.get("pw");
  if (!env.SUBS) return json({ approved: [] });
  if (pw) {
    // admin pohled: pending + approved + odběratelé
    if (!env.ADMIN_PW || pw !== env.ADMIN_PW) return json({ error: "špatné heslo" }, 403);
    return json({
      pending: await listByPrefix(env, "pending:"),
      approved: await listByPrefix(env, "approved:"),
      subscribers: await listByPrefix(env, "sub:"),
    });
  }
  // veřejné: jen schválené akce (web je při načtení přimíchá)
  return json({ approved: await listByPrefix(env, "approved:") });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try { body = await request.json(); } catch { return json({ error: "špatný JSON" }, 400); }
  if (!env.SUBS) return json({ error: "úložiště není nastavené" }, 500);

  if (body.action) {
    // admin akce
    if (!env.ADMIN_PW || body.pw !== env.ADMIN_PW) return json({ error: "špatné heslo" }, 403);
    const id = String(body.id || "");
    if (body.action === "approve") {
      const rec = await env.SUBS.get("pending:" + id, "json");
      if (rec) { await env.SUBS.put("approved:" + id, JSON.stringify(rec)); await env.SUBS.delete("pending:" + id); }
      return json({ ok: true });
    }
    if (body.action === "reject") { await env.SUBS.delete("pending:" + id); return json({ ok: true }); }
    if (body.action === "unpublish") { await env.SUBS.delete("approved:" + id); return json({ ok: true }); }
    if (body.action === "unsub") { await env.SUBS.delete("sub:" + String(body.email || "").toLowerCase()); return json({ ok: true }); }
    return json({ error: "neznámá akce" }, 400);
  }

  // veřejné odeslání akce → pending
  const ev = cleanEvent(body.event || {});
  if (!ev.title || !/^\d{4}-\d{2}-\d{2}$/.test(ev.date)) return json({ error: "chybí název nebo platné datum" }, 400);
  const id = "x" + crypto.randomUUID().slice(0, 12);
  await env.SUBS.put("pending:" + id, JSON.stringify({ id, ...ev, submitted: new Date().toISOString() }));
  return json({ success: true });
}
