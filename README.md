# BRNO SCÉNA — off-cloud grabber (GitHub + Netlify)

Týdenní doplňovač POVRCH akcí, který běží **zadarmo na GitHubu** a nasazuje se přes Netlify.
Žádný Claude, žádné tokeny, žádné API klíče, žádná tajemství. Jen Python skript + cron.

## 📂 Co je ve složce
```
brno-grabber/
├── public/                  ← živý web (Netlify odsud deployuje)
│   ├── index.html           ← appka (skript edituje pole EVENTS uvnitř)
│   ├── *.jpg                ← fotky klubů (24)
│   ├── klub-*.html          ← SEO stránky (40)
│   ├── sitemap.xml, robots.txt
├── grab_povrch.py           ← grabber (GoOut → EVENTS v index.html)
├── requirements.txt         ← Python závislosti
├── .github/workflows/grab.yml  ← týdenní cron (pondělí ~9:00)
└── README.md                ← tohle
```
Všechny soubory webu už jsou v `public/` připravené — nemusíš nic stahovat.

## 🛠️ Nastavení (jednorázově, ~10 minut)

### 1. GitHub repo
1. Založ si repo na github.com (klidně **Private**), např. `brno-scena`.
2. Nahraj do něj **obsah téhle složky** (přetáhni soubory v „Add file → Upload files", nebo přes git).
   - Důležité: zachovej strukturu — `public/` jako složka, `.github/workflows/grab.yml` jako cesta.

### 2. Netlify (auto-deploy z repa)
1. Netlify → **Add new site → Import an existing project → GitHub** → vyber repo.
2. Nastav:
   - **Build command:** nech prázdné
   - **Publish directory:** `public`
3. Deploy. Web pojede na nové `*.netlify.app` adrese.
4. (Volitelně, abys zachoval `snabba.netlify.app`): ve starém Netlify Drop webu **Site configuration → Change site name** přejmenuj starý, pak nový pojmenuj `snabba`. Nebo prostě používej novou adresu.

> Od teď: **každý push do repa = automatický deploy.** Ruční nahrávání přes Netlify Drop už nepotřebuješ.

### 3. Hotovo
GitHub Action se spustí **každé pondělí ~9:00** sama: stáhne GoOut, doplní akce do `public/index.html`, commitne → Netlify nasadí.

## ▶️ Test
- **Lokálně (doporučeno první):** v terminálu ve složce repa
  ```
  pip install -r requirements.txt
  python grab_povrch.py --dry-run     # jen vypíše, co by doplnil, NIC nemění
  ```
  Zkontroluj, že to našlo rozumné akce. Když jo, můžeš pustit bez `--dry-run`.
- **Na GitHubu:** záložka **Actions** → workflow „BRNO SCÉNA…" → **Run workflow** (tlačítko). Sleduj log + jestli vznikl commit + Netlify deploy.

## ⚠️ Poznámky a limity
- **GoOut parser je heuristický.** Stránky se občas mění — proto si **první běh pusť s `--dry-run`** a koukni, jestli sedí akce. Když najednou hlásí 0 akcí, GoOut nejspíš změnil strukturu a parser chce drobný tweak (sekce `fetch_events` ve skriptu).
- **Jen POVRCH** (GoOut). Underground kluby mají JS weby (scraper je nepřečte) — ty zatím doplňuj ručně přes formulář na webu, nebo to vyřešíme zvlášť.
- **Bezpečnost dat:** skript NESAHÁ na underground akce, na ručně přidané akce (id „i…"), ani na fotky/SEO — přepisuje jen auto-grab akce (id „a…"). Když by se po úpravě `index.html` porušil (chybí `</html>`), NIC neuloží.
- **Žánry řeší pravidla** (klíčová slova). Hrubší než model, ale zadarmo a bez závislosti na cloudu.

## 📸 Flyer → akce (IG stories z telefonu) — fáze 1
Underground žije na IG stories, které se scrapovat nedají. Řešení: screenshot story → nahraješ na svůj web → **Netlify funkce přečte flyer přes Claude vision** a vytáhne akci.

**Soubory:** `netlify/functions/flyer.mjs` (serverless, drží AI klíč) + `public/flyer.html` (mobilní upload stránka).

**Nastavení (po propojení Netlify s repem):**
1. Netlify → Site configuration → **Environment variables**, přidej:
   - `ANTHROPIC_API_KEY` — tvůj klíč z console.anthropic.com (placené, ale haléře za flyer)
   - `ADMIN_PW` — heslo, ať upload nespamuje kdokoliv
   - `ANTHROPIC_MODEL` — *(volitelné)* aktuální vision model, jinak se použije default ve funkci (ten možná budeš muset aktualizovat)
2. Deploy. Netlify funkci najde sám (`netlify.toml` to nastavuje).

**Použití z telefonu:**
1. Uvidíš story → screenshot.
2. Otevři `tvuj-web/flyer.html` → zadej heslo → nahraj screenshot → **Zpracovat**.
3. Vypíše vytaženou akci (datum/místo/čas/žánr). Zatím ji **přidáš přes formulář** na webu (zkontroluješ ji).

**Fáze 2 (později):** tlačítko „publikovat" přímo z téhle stránky — funkce akci sama commitne do repa a Netlify nasadí. Teď nejdřív ověřujeme, že vision z reálných brněnských flyerů čte správně.

