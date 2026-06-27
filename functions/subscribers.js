// Cloudflare Pages Function: GET /subscribers?secret=…
// Vrátí všechny odběratele jako JSON. JEN pro grabber — chráněno SUBS_SECRET.

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  if (!env.SUBS_SECRET || url.searchParams.get("secret") !== env.SUBS_SECRET) {
    return new Response("Forbidden", { status: 403 });
  }
  const headers = { "Content-Type": "application/json", "Cache-Control": "no-store" };
  if (!env.SUBS) return new Response("[]", { headers });

  const out = [];
  let cursor;
  do {
    const list = await env.SUBS.list({ prefix: "sub:", cursor });
    for (const k of list.keys) {
      const rec = await env.SUBS.get(k.name, "json");
      if (rec) out.push(rec);
    }
    cursor = list.list_complete ? null : list.cursor;
  } while (cursor);

  return new Response(JSON.stringify(out), { headers });
}
