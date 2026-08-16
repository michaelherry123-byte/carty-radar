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

## Latence

Le cron est réglé sur 5 minutes, mais GitHub retarde régulièrement les jobs planifiés de
5 à 10 minutes sur les plans gratuits, surtout aux heures rondes. **Compte 5 à 15 minutes**
entre la publication d'un pick et l'alerte. Si tu as besoin de quasi-temps-réel, la même
`carty_watch.py` tourne à l'identique sur ton PC via une tâche planifiée toutes les 60 s.

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
