---
name: deploy-verify
description: Deploy BRNO SCÉNY na produkci (Cloudflare Pages) a ověření, že se změna propsala. Použij při „nasaď", „deploy", „pushni to", nebo po dokončení featury/fixu, co má jít živě. Deploy = git push do main; hlídá kolizi s denním botem (pull --rebase) a potvrdí změnu na živém snabba.pages.dev.
---

# Deploy & ověření

**Deploy = `git push` do `main`.** Cloudflare Pages nasadí sám (~1–2 min). Repo `nesnasimnegry/Brno_Povrch`, tahle složka je gitový klon, auth přes Git Credential Manager funguje. Živě na https://snabba.pages.dev

## Postup
1. **Commituj cíleně** — jen soubory dané změny (`git add public/index.html`), ne `git add -A`. Untracked balast (např. CLAUDE.md) nech být, pokud o něj nejde.
2. Commit message: prefix stylu repa (`feat:`/`fix:`/`perf:`/`tweak:`/`chore:`), česky (bez diakritiky v subjectu je OK). Přidej `Co-Authored-By: Claude ...`.
3. **Před pushem `git pull --rebase origin main`** — denní bot (~9:00) commituje do main; když push odmítne, rebase a znovu.
4. `git push origin main`.

## Ověř, že je to živě (~1–2 min po pushi)
Grepni na produkci něco, co tvoje změna přidala/odebrala, s cache-bustem:
```bash
curl -s "https://snabba.pages.dev/?cb=$(date +%s)" | grep -o 'HLEDANY_RETEZEC'
```
Potvrď, že produkce sedí (změna je vidět / stará věc zmizela).

## Pozor
- **Nikdy `--no-verify`, nikdy force push do main.**
- Grabbery/`notify.py` deploy neřeš ručně — jedou přes GitHub workflow (denní cron → commit → deploy). Tohle je pro ruční změny webu.
- KV binding / env změny (SUBS, ADMIN_PW) se projeví až po **novém deployi**.
- Editaci webu před pushem prožeň přes [[safe-index-edit]].
