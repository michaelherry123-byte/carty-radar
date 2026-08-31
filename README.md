# Carty Radar

Surveille les picks de **Derek Carty** (`derekcarty`) sur ScoresAndOdds et envoie une alerte
dans ton groupe Telegram dès qu'un nouveau pick est publié. Tourne en cloud sur GitHub Actions,
ton PC peut rester éteint.

## Ce que tu reçois

```
🎯 Derek Carty — MLB
Max Clark Prop
Type : Player Prop
🔒 Détail verrouillé (SAO Premium)
💰 Risking 1u to win 3.3u  (+330 · 23.3% implicite)

🕒 16/08 15:29  ·  voir sur SAO
```

**Important :** sans abonnement SAO Premium, le site masque le détail du pick (le titre affiché
est littéralement « My Title »). L'alerte te donne donc le **joueur**, le **type de pari**, la
**mise** et la **cote** — mais pas le sens (over/under). Si tu as un compte Premium, ajoute le
secret `SAO_COOKIE` et le vrai pick apparaît dans le message (`Logan Henderson o5.5 Strikeouts (+119)`).

Sports surveillés : MLB, NFL, NCAAF, NBA, NCAAB, NHL, WNBA, Golf, NASCAR, MMA, Soccer.
En août seul MLB est actif ; NFL se remplira tout seul en septembre.

---

## Destination Telegram — déjà configurée

| Élément | Valeur |
|---|---|
| Bot | **Serious Business Bot** — `@serious_business_alerts_bot` |
| Groupe | **Serious business** (groupe basique, 4 membres) |
| `TELEGRAM_CHAT_ID` | `-4893336798` |
| `TELEGRAM_BOT_TOKEN` | fourni par @BotFather — **jamais dans ce repo**, uniquement en secret GitHub |

Le bot est membre du groupe et n'a besoin d'aucun droit d'admin pour y écrire.

> ⚠️ Si le groupe est un jour converti en **supergroupe** (ajout de beaucoup de membres,
> activation de l'historique public, des sujets…), Telegram lui attribue un **nouvel id**
> au format `-100…`. Les alertes s'arrêteront avec une erreur `chat not found` : il faudra
> refaire un `getUpdates` et mettre à jour le secret.

Pour retrouver le token plus tard : @BotFather → `/mybots` → Serious Business Bot → **API Token**.
Pour le régénérer s'il fuite : `/revoke`.

### Créer le repo GitHub

```bash
cd carty-radar
git init && git add . && git commit -m "Carty Radar"
gh repo create carty-radar --private --source=. --push
```

> Repo **privé** de préférence : le log des picks et l'état restent chez toi.
> Note : sur un repo privé, les minutes Actions sont plafonnées (2 000/mois sur le plan gratuit).
> Ce workflow consomme ~40 s par run × 288 runs/jour ≈ bien plus que le quota — **passe le repo
> en public** (Actions illimitées) ou espace le cron à `*/15` (~96 runs/jour). Voir « Coût » plus bas.

### Renseigner les secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret** :

| Nom | Valeur |
|---|---|
| `TELEGRAM_BOT_TOKEN` | le token de @BotFather (colle-le directement ici, nulle part ailleurs) |
| `TELEGRAM_CHAT_ID` | `-4893336798` |
| `SAO_COOKIE` | *(facultatif)* ton cookie de session SAO Premium |

### Amorcer, puis vérifier

Onglet **Actions → Carty Radar → Run workflow** :

1. mode `test` → un message de confirmation doit arriver dans le groupe.
2. mode `seed` → marque les picks déjà en ligne comme vus (sinon la première exécution
   spammerait le groupe avec tous les picks du jour).

Ensuite le cron prend le relais tout seul.

---

## Moteur de déclenchement : cron-job.org (et pourquoi pas le cron GitHub)

Le cron natif de GitHub Actions **n'est pas fiable** pour de l'alerting. Mesuré sur ce repo
entre le 23 et le 31 août 2026, avec un `cron: "*/15"` (96 runs/jour attendus) :

| Jour | Runs réels |
|---|---|
| 24/08 | 27 |
| 25/08 | 29 |
| 26/08 | 19 |
| 27/08 | 2 |
| 28/08 | 3 |
| 29/08 | 6 |
| 30/08 | 6 |

Écarts entre deux runs sur les dernières 24 h : de 131 à 371 minutes. Aucun run en échec —
ils ne sont simplement jamais déclenchés. GitHub déprioritise les workflows planifiés des
repos publics gratuits, et la dégradation s'aggrave avec le temps.

**Solution : un déclencheur externe.** cron-job.org envoie un `repository_dispatch` toutes
les 2 minutes ; ce type d'événement n'est pas soumis à l'étranglement.

### Configuration de cron-job.org

1. Crée un **fine-grained PAT** sur github.com → Settings → Developer settings →
   Personal access tokens → Fine-grained tokens :
   - *Repository access* : uniquement `carty-radar`
   - *Permissions* → Repository permissions → **Contents: Read and write**
   - Expiration : 1 an (note la date, le radar s'arrêtera à l'expiration)
2. Sur [cron-job.org](https://cron-job.org), crée un job :
   - URL : `https://api.github.com/repos/michaelherry123-byte/carty-radar/dispatches`
   - Méthode : **POST**
   - Intervalle : toutes les 2 minutes
   - Headers :
     - `Authorization: Bearer <ton PAT>`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - Body : `{"event_type":"carty-tick"}`
3. **Active la notification e-mail en cas d'échec** (case à cocher dans le job). cron-job.org
   désactive automatiquement un job qui échoue 25 fois d'affilée : c'est précisément ce qui
   arrivera le jour où le PAT expirera, et sans cette notification le radar s'éteint en silence.
4. Le job doit renvoyer **204 No Content**. Diagnostic des erreurs :
   - `401` → PAT invalide ou expiré
   - `404` → PAT valide mais sans la permission *Contents: Read and write* sur le repo
     (GitHub renvoie 404 et non 403 pour ne pas divulguer l'existence du dépôt)
   - `403 Request forbidden by administrative rules` → problème de `User-Agent`.
     cron-job.org **ignore** les headers `User-Agent` et `Connection` que tu configures ;
     il envoie le sien, ce qui suffit normalement à l'API GitHub.

cron-job.org est gratuit sans palier payant, financé par dons, open source, minimum 1 minute
d'intervalle, nombre de jobs illimité. Nos 720 appels/jour restent dans leur usage normal.

Le cron GitHub `*/15` reste actif en filet de sécurité si cron-job.org tombe.

## Latence

Avec cron-job.org toutes les 2 minutes : **latence réelle 2 à 3 minutes** entre la
publication d'un pick et l'alerte Telegram (le job lui-même prend ~25 s).

Si cron-job.org tombe et qu'on retombe sur le seul cron GitHub : compte 2 à 6 heures.
C'est le mode dégradé, pas le mode nominal.

## Coût / quotas

| Cron | Runs/jour | Minutes/mois (~40 s/run) |
|---|---|---|
| `*/5` | 288 | ~5 800 |
| `*/15` | 96 | ~1 900 |

Repo **public** → Actions gratuites et illimitées, garde `*/5`.
Repo **privé** → 2 000 min/mois inclus, passe à `*/15` (ligne `cron` dans le workflow).

## Utilisation en local

```bash
pip install -r requirements.txt
set TELEGRAM_BOT_TOKEN=...
set TELEGRAM_CHAT_ID=-100...
python carty_watch.py --dry-run   # affiche les messages sans envoyer
python carty_watch.py --seed      # initialise l'état
python carty_watch.py             # run normal
python tests/test_parse.py        # vérifie le parseur
```

## Ajouter d'autres tipsters

Repo → **Settings → Secrets and variables → Actions → Variables** → `WATCH_USERNAMES`
avec les pseudos séparés par des virgules, par ex. :

```
derekcarty,stlcardinals84,gneiffer07,propmodel
```

`propmodel` est le seul dont les picks sont **entièrement publics** (titre + analyse visibles
sans abonnement) — utile pour tester le rendu complet des messages.

## Fichiers

```
carty_watch.py                    scraper + envoi Telegram
requirements.txt
.github/workflows/carty-watch.yml cron 5 min + persistance de l'état
state/seen.json                   picks déjà alertés (auto-généré, purge à 3 jours)
data/picks_log.csv                historique complet (auto-généré)
tests/test_parse.py               test du parseur sur HTML réel
tests/fixture_pick_card.html      extrait HTML capturé le 16/08/2026
```

`data/picks_log.csv` s'accumule tout seul : dans quelques semaines tu auras de quoi mesurer
le CLV de Carty et vérifier son `+31.72u` annoncé sur des données que tu as horodatées toi-même.

## Si ça casse

Le scraper dépend des classes CSS de ScoresAndOdds (`.pick-card`, `.pick-expert-username`,
`.pick-date span[data-value]`). Si le site refond son HTML, le workflow ne plantera pas — il
comptera simplement 0 pick. Surveillance : le log du job affiche `mlb  19 picks · 4 surveillé(s)`.
Si tu vois `0 picks` sur MLB en pleine saison, les sélecteurs sont à mettre à jour dans
`parse_cards()`.
