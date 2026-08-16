#!/usr/bin/env python3
"""
Carty Radar — surveille les picks de Derek Carty (derekcarty) sur ScoresAndOdds
et pousse une alerte dans un groupe Telegram dès qu'un nouveau pick est publié.

Usage:
    python carty_watch.py            # run normal (envoie les nouveaux picks)
    python carty_watch.py --seed     # initialise l'état sans rien envoyer
    python carty_watch.py --dry-run  # affiche les messages sans les envoyer
    python carty_watch.py --test     # envoie un message de test dans le groupe

Variables d'environnement:
    TELEGRAM_BOT_TOKEN   (requis)  token @BotFather
    TELEGRAM_CHAT_ID     (requis)  id du groupe, ex. -1001234567890
    SAO_COOKIE           (option)  cookie de session Premium pour débloquer le
                                   détail du pick au lieu de "My Title"
    WATCH_USERNAMES      (option)  défaut "derekcarty", séparés par des virgules
    WATCH_SPORTS         (option)  défaut la liste complète ci-dessous
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

BASE = "https://www.scoresandodds.com"

DEFAULT_SPORTS = [
    "mlb", "nfl", "ncaaf", "nba", "ncaab", "nhl",
    "wnba", "golf", "nascar", "mma", "soccer",
]

SPORTS = [s.strip().lower() for s in
          os.environ.get("WATCH_SPORTS", ",".join(DEFAULT_SPORTS)).split(",") if s.strip()]

USERNAMES = {u.strip().lower() for u in
             os.environ.get("WATCH_USERNAMES", "derekcarty").split(",") if u.strip()}

STATE_PATH = Path(os.environ.get("STATE_PATH", "state/seen.json"))
LOG_PATH = Path(os.environ.get("LOG_PATH", "data/picks_log.csv"))

TZ = ZoneInfo(os.environ.get("DISPLAY_TZ", "Europe/Paris"))

# Un pick reste "vivant" 3 jours dans l'état, au-delà on purge (évite un fichier
# qui gonfle indéfiniment ; aucun pick ne réapparaît après 3 jours).
STATE_TTL_SECONDS = 3 * 24 * 3600

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

BETTYPE_LABEL = {
    "pp": "Player Prop",
    "gp": "Game Prop",
    "ats": "Spread",
    "tot": "Total",
    "ml": "Moneyline",
    "h2h": "Head to Head",
    "par": "Parlay",
    "tea": "Teaser",
    "fut": "Future",
    "fp": "Fantasy Prop",
}

# --------------------------------------------------------------------------- #
# Scraping
# --------------------------------------------------------------------------- #


def _clean(node) -> str:
    """Texte normalisé d'un noeud BeautifulSoup (ou '' si None)."""
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def parse_cards(html: str, sport: str) -> list[dict]:
    """Extrait tous les pick-cards d'une page /{sport}/picks."""
    soup = BeautifulSoup(html, "html.parser")
    picks: list[dict] = []

    for card in soup.select(".pick-card"):
        username = _clean(card.select_one(".pick-expert-username")).lower()
        if not username:
            continue

        headline = _clean(card.select_one(".pick-expert-name"))

        date_node = card.select_one(".pick-date span[data-value]")
        ts_iso = date_node.get("data-value") if date_node else ""

        icn = card.select_one(".pick-title-icn")
        code = ""
        if icn:
            classes = [c for c in icn.get("class", []) if c != "pick-title-icn"]
            code = classes[0].lower() if classes else ""

        title = _clean(card.select_one(".pick-title-grid h3"))
        stake_txt = _clean(card.select_one(".pick-title-grid span"))

        # "Risking 1u to win 3.3u"
        m = re.search(r"Risking\s+([\d.]+)u\s+to win\s+([\d.]+)u", stake_txt, re.I)
        risk = float(m.group(1)) if m else None
        win = float(m.group(2)) if m else None

        # Corps d'analyse (visible seulement si abonné Premium)
        body = _clean(card.select_one(".pick-analysis, .pick-body, .pick-content"))

        picks.append({
            "sport": sport.upper(),
            "username": username,
            "headline": headline,
            "ts_iso": ts_iso,
            "bettype_code": code,
            "bettype": BETTYPE_LABEL.get(code, code.upper()),
            "title": title,
            "risk": risk,
            "win": win,
            "stake_txt": stake_txt,
            "body": body,
            "url": f"{BASE}/{sport}/picks",
        })

    return picks


def pick_id(p: dict) -> str:
    """Clé de déduplication stable : sport + tipster + horodatage de publication."""
    raw = f"{p['sport']}|{p['username']}|{p['ts_iso'] or p['headline']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def fetch_sport(session: requests.Session, sport: str) -> list[dict]:
    url = f"{BASE}/{sport}/picks"
    for attempt in range(3):
        try:
            r = session.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200:
                return parse_cards(r.text, sport)
            print(f"  ! {sport}: HTTP {r.status_code}", file=sys.stderr)
        except requests.RequestException as exc:
            print(f"  ! {sport}: {exc}", file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return []


# --------------------------------------------------------------------------- #
# Mise en forme du message
# --------------------------------------------------------------------------- #


def american_odds(risk: float | None, win: float | None) -> str:
    if not risk or not win:
        return ""
    dec = 1 + win / risk
    am = round((dec - 1) * 100) if dec >= 2 else round(-100 / (dec - 1))
    prob = 100 / dec
    sign = "+" if am > 0 else ""
    return f"{sign}{am} · {prob:.1f}% implicite"


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def local_time(ts_iso: str) -> str:
    if not ts_iso:
        return "?"
    try:
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).astimezone(TZ)
        return dt.strftime("%d/%m %H:%M")
    except ValueError:
        return ts_iso


def format_message(p: dict) -> str:
    # "Derek Carty has a Max Clark Prop Today!" -> "Max Clark Prop"
    subject = re.sub(r"^.*?\bhas an?\b\s*", "", p["headline"], flags=re.I)
    subject = re.sub(r"\s*Today!?\s*$", "", subject).strip() or p["headline"]

    expert = p["headline"].split(" has a")[0].split(" has an")[0].strip() or p["username"]

    lines = [
        f"🎯 <b>{esc(expert)}</b> — {esc(p['sport'])}",
        f"<b>{esc(subject)}</b>",
    ]

    if p["bettype"]:
        lines.append(f"Type : {esc(p['bettype'])}")

    # Titre réel du pick si le compte est Premium ; sinon placeholder du site
    if p["title"] and p["title"].lower() not in ("my title", ""):
        lines.append(f"👉 <b>{esc(p['title'])}</b>")
    else:
        lines.append("🔒 <i>Détail verrouillé (SAO Premium)</i>")

    if p["stake_txt"]:
        odds = american_odds(p["risk"], p["win"])
        lines.append(f"💰 {esc(p['stake_txt'])}" + (f"  ({odds})" if odds else ""))

    if p["body"]:
        body = p["body"]
        lines.append(f"\n{esc(body[:400])}{'…' if len(body) > 400 else ''}")

    lines.append(f"\n🕒 {local_time(p['ts_iso'])}  ·  <a href=\"{p['url']}\">voir sur SAO</a>")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #


def send_telegram(text: str, token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code == 200:
                return True
            if r.status_code == 429:
                retry = r.json().get("parameters", {}).get("retry_after", 5)
                time.sleep(retry + 1)
                continue
            print(f"  ! Telegram {r.status_code}: {r.text[:300]}", file=sys.stderr)
        except requests.RequestException as exc:
            print(f"  ! Telegram: {exc}", file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return False


# --------------------------------------------------------------------------- #
# État + log
# --------------------------------------------------------------------------- #


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("  ! état illisible, réinitialisation", file=sys.stderr)
    return {}


def save_state(state: dict) -> None:
    now = time.time()
    pruned = {k: v for k, v in state.items() if now - v.get("seen_at", now) < STATE_TTL_SECONDS}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(pruned, indent=1, sort_keys=True), encoding="utf-8")


def append_log(picks: list[dict]) -> None:
    """Historique CSV : utile pour mesurer le CLV / backtester Carty plus tard."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_file = not LOG_PATH.exists()
    with LOG_PATH.open("a", encoding="utf-8", newline="") as fh:
        if new_file:
            fh.write("detected_at,ts_iso,sport,username,headline,bettype,title,risk,win\n")
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for p in picks:
            row = [
                stamp, p["ts_iso"], p["sport"], p["username"],
                p["headline"].replace('"', "'"), p["bettype"],
                p["title"].replace('"', "'"),
                "" if p["risk"] is None else f"{p['risk']}",
                "" if p["win"] is None else f"{p['win']}",
            ]
            fh.write(",".join(f'"{c}"' for c in row) + "\n")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true",
                    help="marque les picks actuels comme vus, sans alerte")
    ap.add_argument("--dry-run", action="store_true",
                    help="affiche les messages sans les envoyer ni écrire l'état")
    ap.add_argument("--test", action="store_true",
                    help="envoie un message de test dans le groupe puis quitte")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if args.test:
        if not token or not chat_id:
            print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID manquants", file=sys.stderr)
            return 2
        ok = send_telegram(
            "✅ <b>Carty Radar</b> est connecté à ce groupe.\n"
            "Vous recevrez une alerte à chaque nouveau pick de Derek Carty.",
            token, chat_id)
        print("test envoyé" if ok else "échec de l'envoi")
        return 0 if ok else 1

    if not args.dry_run and not args.seed and (not token or not chat_id):
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID manquants", file=sys.stderr)
        return 2

    session = requests.Session()
    cookie = os.environ.get("SAO_COOKIE", "").strip()
    if cookie:
        session.headers["Cookie"] = cookie

    all_picks: list[dict] = []
    for sport in SPORTS:
        cards = fetch_sport(session, sport)
        watched = [c for c in cards if c["username"] in USERNAMES]
        print(f"  {sport:7s} {len(cards):3d} picks · {len(watched)} surveillé(s)")
        all_picks.extend(watched)
        time.sleep(1.0)  # on reste poli avec le site

    state = load_state()
    first_run = not state and not STATE_PATH.exists()

    new_picks = [p for p in all_picks if pick_id(p) not in state]
    print(f"\n{len(all_picks)} pick(s) surveillé(s) au total, {len(new_picks)} nouveau(x)")

    if args.seed or (first_run and not args.dry_run):
        for p in all_picks:
            state[pick_id(p)] = {"seen_at": time.time(), "ts": p["ts_iso"]}
        save_state(state)
        append_log(all_picks)
        print("État initialisé — aucune alerte envoyée pour les picks déjà en ligne.")
        if token and chat_id and not args.dry_run:
            send_telegram(
                "📡 <b>Carty Radar</b> armé.\n"
                f"{len(all_picks)} pick(s) déjà en ligne ignoré(s). "
                "Les prochains déclencheront une alerte.", token, chat_id)
        return 0

    if not new_picks:
        print("Rien de neuf.")
        return 0

    # Du plus ancien au plus récent
    new_picks.sort(key=lambda p: p["ts_iso"] or "")

    sent = 0
    for p in new_picks:
        msg = format_message(p)
        if args.dry_run:
            print("\n--- message ---\n" + msg)
            sent += 1
            continue
        if send_telegram(msg, token, chat_id):
            state[pick_id(p)] = {"seen_at": time.time(), "ts": p["ts_iso"]}
            sent += 1
            time.sleep(1.2)  # limite Telegram : ~20 msg/min par groupe

    if not args.dry_run:
        save_state(state)
        append_log(new_picks)

    print(f"{sent}/{len(new_picks)} alerte(s) envoyée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
