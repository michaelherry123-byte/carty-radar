#!/bin/sh
# Carty Radar sur le serveur Contabo (14/11/2026, Michael : « Ok pour les 3 angles ») : un passage toutes les
# 2 minutes, sans dépendre de GitHub Actions ni de cron-job.org. L'état (picks déjà vus) est gardé dans un volume ;
# au tout premier démarrage il reprend celui du dépôt, pour ne renvoyer aucun ancien pick.
set -u
D=${DOSSIER_DONNEES:-/donnees}
mkdir -p "$D"
if [ ! -f "$D/seen.json" ] && [ -f state/seen.json ]; then cp state/seen.json "$D/seen.json" && echo "carty: etat initial repris du depot"; fi
if [ ! -f "$D/picks_log.csv" ] && [ -f data/picks_log.csv ]; then cp data/picks_log.csv "$D/picks_log.csv"; fi
export STATE_PATH="$D/seen.json" LOG_PATH="$D/picks_log.csv"
INTERVALLE=${INTERVALLE_S:-120}
n=0
while [ -z "${PASSAGES_MAX:-}" ] || [ "$n" -lt "$PASSAGES_MAX" ]; do
  debut=$(date +%s)
  python carty_watch.py; code=$?
  [ "$code" = 0 ] || echo "carty: passage en echec (code $code)"
  n=$((n + 1))
  reste=$((INTERVALLE - ($(date +%s) - debut)))
  if [ "$reste" -gt 0 ] && { [ -z "${PASSAGES_MAX:-}" ] || [ "$n" -lt "$PASSAGES_MAX" ]; }; then sleep "$reste"; fi
done
