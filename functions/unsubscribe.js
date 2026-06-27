// Cloudflare Pages Function: GET /unsubscribe?e=<email>&t=<token>
// Odhlásí odběratele (odkaz z e-mailu). Vrátí jednoduchou HTML stránku.

const page = (msg) =>
  new Response(
    `<!doctype html><html lang="cs"><head><meta charset="utf-8">` +
      `<meta name="viewport" content="width=device-width,initial-scale=1">` +
      `<title>BRNO SCÉNA — odhlášení</title></head>` +
      `<body style="background:#0c0b0a;color:#efeae0;font-family:system-ui,-apple-system,sans-serif;max-width:520px;margin:64px auto;padding:0 20px;text-align:center;line-height:1.6">` +
      `<h1 style="color:#ecc400;letter-spacing:.04em">BRNO SCÉNA</h1>` +
      `<p style="font-size:18px">${msg}</p>` +
      `<p><a href="/" style="color:#ecc400">← zpět na web</a></p></body></html>`,
    { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } }
  );

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const email = String(url.searchParams.get("e") || "").trim().toLowerCase();
  const token = url.searchParams.get("t") || "";

  if (!email || !token || !env.SUBS) return page("Neplatný odhlašovací odkaz.");
  const key = "sub:" + email;
  const rec = await env.SUBS.get(key, "json");
  if (rec && rec.token === token) {
    await env.SUBS.delete(key);
    return page("Odhlášeno. Už ti nebudeme posílat e-maily. 👋");
  }
  return page("Tento odkaz už neplatí — možná ses už odhlásil.");
}
