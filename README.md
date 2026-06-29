# BRNO SCÉNA

> Plně automatizovaný průvodce brněnskou klubovou a hudební scénou — underground i mainstream na jednom místě.
> **Živě:** [snabba.pages.dev](https://snabba.pages.dev)

Single-page web (vanilla JS, hash routing, dva módy UNDERGROUND / POVRCH) + sada Python grabberů, které **každý den** samy doplňují akce z veřejných zdrojů. Postavené tak, aby běželo **zadarmo** a **bez údržby** — žádný server, žádná databáze běžící 24/7, žádné placené služby v základu.

---

## ✨ Co to umí

- **🤖 Plně automatický grabber.** Denně (GitHub Actions cron) stáhne nadcházející akce z **GoOut entity API** + webů brněnských klubů (Kabinet, Alterna, Exit), namapuje je na podniky a žánry a commitne do webu → Cloudflare nasadí. Nula ruční práce.
- **🛡️ Odolnost + self-monitoring.** Grabber **nikdy nerozbije web** (atomický zápis, sanitace dat proti rozbití JS, validace před uložením). Když zdroj spadne nebo změní strukturu, **nesmaže budoucí akce** a pošle **alert e-mail** — web se hlídá sám.
- **📧 E-mailové notifikace (full-stack).** Uživatel si **sleduje klub nebo DJ-e**; když přibude jejich akce, přijde mu personalizovaný e-mail. Odběratelé žijí v Cloudflare KV (Pages Functions), párování a rozesílání řeší grabber přes Gmail SMTP, s jednoklikovým odhlášením.
- **🔎 SEO & sdílení.** 40 statických klubových stránek, `sitemap.xml`/`robots.txt`, JSON-LD strukturovaná data (`MusicVenue` / `Organization`) na 41 stránkách, OG/Twitter karty.
- **📱 PWA + analytics.** Instalovatelné na mobil (manifest + ikona), Cloudflare Web Analytics (privacy-first, bez cookies).
- **🗓️ User funkce.** Sledování (★) klubů i umělců, sekce „Sleduju", „Přidat do Google Kalendáře", filtry, fulltext, mapa klubů (Leaflet).

---

## 🏗️ Architektura

```
                       ┌─────────────────────────────────────────┐
  veřejné zdroje  ───▶ │  GitHub Actions (denní cron)             │
  GoOut entity API     │   grab_povrch.py / grab_underground.py   │
  weby klubů           │      → akce do public/index.html         │
                       │   notify.py → e-maily odběratelům        │
                       └───────────────┬─────────────────────────┘
                                       │ git push
                                       ▼
                       Cloudflare Pages  ──▶  snabba.pages.dev
                       ├─ statický web (public/)
                       └─ Pages Functions: /subscribe /subscribers /unsubscribe
                                       │
                              Cloudflare KV (odběratelé)
```

**Klíčové rozhodnutí:** web je *statický* (index.html s polem `EVENTS`), takže hosting i CDN jsou zdarma a bleskurychlé. Veškerá „dynamika" (grab, párování notifikací) běží **dávkově v CI**, ne na serveru. Drobné serverless kousky (přihlášení k odběru) řeší Cloudflare Pages Functions + KV.

## 🧩 Tech stack
- **Frontend:** vanilla JS (jeden soubor ~85 KB), hash routing, žádný build krok
- **Grabbery:** Python + `requests` (GoOut entity API = strukturovaný JSON, žádné křehké HTML scrapování), `BeautifulSoup` pro weby klubů
- **Backend (lehký):** Cloudflare Pages Functions + KV (odběratelé), Gmail SMTP (rozesílání)
- **Hosting/CI:** Cloudflare Pages (deploy = `git push`), GitHub Actions (cron + e-mail report/alert)

## 📂 Struktura
```
├── public/
│   ├── index.html        # celá appka (pole EVENTS, id prefix: a=auto, u=underground, i=ruční)
│   ├── klub-*.html        # 40 SEO stránek, manifest.json, sitemap.xml, robots.txt
├── functions/             # Cloudflare Pages Functions (subscribe/subscribers/unsubscribe)
├── grab_povrch.py         # POVRCH grabber (GoOut entity API)
├── grab_underground.py    # UNDERGROUND grabber (GoOut + Kabinet/Alterna/Exit)
├── notify.py              # párování nových akcí ↔ odběratelé → e-mail
└── .github/workflows/grab.yml   # denní cron → commit → deploy + report/alert mail
```

## ▶️ Lokální vývoj
```bash
pip install -r requirements.txt
python grab_povrch.py --dry-run        # vypíše, co by doplnil; NIC nezapíše
python grab_underground.py --dry-run
```
Web je statický — stačí otevřít `public/index.html` (nebo `python -m http.server --directory public`).

## ⚙️ Jak to běží
`git push` do `main` → Cloudflare Pages nasadí. Denní GitHub Action stáhne akce, commitne změny a (jen když něco přibylo / něco selhalo) pošle e-mailový report nebo alert. Grabbery přepisují **jen své** auto-akce (`a`/`u`), ručních (`i`), fotek ani SEO se nedotknou.

---

*Pet/portfolio projekt. Publikum: studenti a mladí v Brně.*
