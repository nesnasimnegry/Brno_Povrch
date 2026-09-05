# IG grabber na Raspberry Pi 1 Model B+ (autonomní trickle uzel)

Cíl: přesunout IG scrape z tvého PC na **always-on Pi** (rezidenční IP → IG neblokuje jako cloud),
který **kapátkem** (trickle) scrapuje po jednom účtu v náhodný čas → mizí burst = hlavní spouštěč
bloku `feedback_required`. Cloud (GitHub Actions) dál řeší strukturované zdroje (RA/smsticket/
koncertbrno/GoOut). Pi jen dojídá IG (feed + reels + stories + Gemini vize).

> **Pi 1 B+ realita:** ARMv6, 512 MB RAM, 700 MHz, **bez wifi**. Na HTTP scrape bohatě stačí.
> NEpojede tu prohlížeč (Playwright/Chromium) ani curl_cffi — **nepotřebujeme je** (stories jdou
> přes HTTP API + vizi). Použij `html.parser` (už v kódu), NE lxml (kompilace na ARMv6 je peklo).

## 0. Co budeš potřebovat
- Pi 1 B+, microSD (≥8 GB), microUSB napájení
- **ethernet kabel do routeru** (Pi 1 B+ nemá wifi; USB wifi dongle jde taky, ale kabel je jistota)
- GitHub **Personal Access Token** (na `git push`) — vytvoř na github.com → Settings → Developer
  settings → Tokens (classic), scope `repo`
- soubory z PC: **instaloader session** `session-ig.grabber` a **`ig_ai.key`** (Gemini klíč)

## 1. OS na kartu
V **Raspberry Pi Imager**: OS → „Raspberry Pi OS **Lite (32-bit)**" (bez desktopu; ARMv6 kompatibilní).
V ozubeném kolečku (⚙️) přednastav: **hostname** (`brnopi`), **zapni SSH** (heslo), **uživatele**
(`pi`), případně wifi (jen když máš dongle). Zapiš na kartu, vlož do Pi, připoj ethernet + napájení.
(Pi 1 bootuje pomalu, klidně 1–2 min.)

## 2. Přihlášení + základ
```bash
ssh pi@brnopi.local           # nebo ssh pi@<IP z routeru>
sudo apt update && sudo apt install -y git python3-venv python3-pip
```

## 3. Repo + Python prostředí
```bash
git clone https://github.com/nesnasimnegry/Brno_Povrch.git brno-grabber
cd brno-grabber
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install requests beautifulsoup4 instaloader   # piwheels dá ARM wheely; NE lxml/playwright
```

## 4. Git push identita (jednou)
```bash
git config user.name  "brnopi"
git config user.email "gpuagency@gmail.com"
git config credential.helper store     # PAT se uloží po prvním pushi (plaintext v ~/.git-credentials)
```
Při prvním `git push` zadáš username = tvůj GitHub login, heslo = **PAT**. Pak si to pamatuje.

## 5. IG session + klíče (ze svého PC)
Session je vázaná na IP — Pi je na **stejné domácí IP** jako PC, takže zkopírovaný soubor funguje.
Na **PC** je session v `%LOCALAPPDATA%\Instaloader\session-ig.grabber`. Přenes ji na Pi:
```bash
# na Pi vytvoř složku:
mkdir -p ~/.config/instaloader
# z PC (PowerShell) přes scp, nebo přes USB/scp klienta:
#   scp "$env:LOCALAPPDATA\Instaloader\session-ig.grabber" pi@brnopi.local:~/.config/instaloader/
```
Gemini klíč (vize):
```bash
# zkopíruj obsah ig_ai.key z PC do stejného souboru na Pi (je v .gitignore, negituje se):
nano ~/brno-grabber/ig_ai.key      # vlož klíč, ulož
```
(Až session vyprší, buď ji na PC obnov `ig_session.py` a znovu zkopíruj, nebo na Pi:
`.venv/bin/python -m instaloader --login=ig.grabber` a projdi výzvu.)

## 6. Test (jeden účet)
```bash
cd ~/brno-grabber
PYTHONIOENCODING=utf-8 .venv/bin/python ig_trickle.py ig.grabber 1
```
Očekávané: `session 'ig.grabber' načtena` + scrape jednoho účtu. Když vidíš `feedback_required`,
IP je zrovna v ranku (odezní hodiny) — zkus později. Když `400` na všech, session vypršela (bod 5).

## 7. Cron — trickle každých ~30 min s jitterem
```bash
crontab -e
```
přidej řádek (jitter 0–15 min → nepravidelný čas; K=1 účet za běh → za ~10 h projede všech 21):
```cron
*/30 * * * * cd /home/pi/brno-grabber && sleep $(shuf -i0-900 -n1) && .venv/bin/python ig_trickle.py ig.grabber 1 >> /home/pi/ig_trickle.log 2>&1
```
`ig_trickle.py` sám drží frontu (`data/ig_queue.json`), a **až projede celé kolo, jednou pushne**
cache → denní cloud grab (~9:00) ji roznese na web. Log sleduj: `tail -f ~/ig_trickle.log`.

## 8. Co ještě pomůže proti bloku (mimo kód)
- **`ig.grabber` ať SLEDUJE (follow) všech ~21 klubů/promotérů** — čtení jejich feedu pak vypadá
  organicky, ne jako scrape cizích účtů. Druhý hlavní faktor po burstu.
- Nech Pi **zapnuté a na síti** 24/7 (spotřeba ~2 W).
- Na blok **neretryovat** — trickle to řeší sám (další účet příště).

## Hotovo
Tvé hlavní PC už nemusí být zapnuté. Pi kapátkem sype IG do cache, cloud roznáší.
Strukturované zdroje (RA/smsticket/koncertbrno/GoOut) jedou v cloudu nezávisle.
