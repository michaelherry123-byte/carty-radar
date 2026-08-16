"""Test du parseur sur un extrait HTML réel. Lancer : python tests/test_parse.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carty_watch import parse_cards, pick_id, format_message, american_odds  # noqa: E402

html = (Path(__file__).parent / "fixture_pick_card.html").read_text(encoding="utf-8")
cards = parse_cards(html, "mlb")
carty = [c for c in cards if c["username"] == "derekcarty"]

assert len(cards) == 4, f"4 cards attendues, {len(cards)} trouvées"
assert len(carty) == 3, f"3 picks Carty attendus, {len(carty)} trouvés"

first = carty[0]
assert first["headline"] == "Derek Carty has a Max Clark Prop Today!", first["headline"]
assert first["ts_iso"] == "2026-08-16T13:29:00Z", first["ts_iso"]
assert first["bettype"] == "Player Prop", first["bettype"]
assert first["risk"] == 1.0 and first["win"] == 3.3, (first["risk"], first["win"])

# Dédup : identifiants distincts entre picks, stable sur un même pick
ids = [pick_id(c) for c in carty]
assert len(set(ids)) == 3, "collision d'identifiants"
assert pick_id(parse_cards(html, "mlb")[0]) == ids[0], "identifiant instable"

# Cotes
assert american_odds(1, 3.3).startswith("+330"), american_odds(1, 3.3)
assert american_odds(1.55, 1).startswith("-155"), american_odds(1.55, 1)

# Pick débloqué (compte Premium) : le vrai titre remplace le cadenas
unlocked = [c for c in carty if c["title"] != "My Title"][0]
msg_unlocked = format_message(unlocked)
assert "Logan Henderson o5.5 Strikeouts" in msg_unlocked
assert "🔒" not in msg_unlocked

msg_locked = format_message(first)
assert "🔒" in msg_locked and "Max Clark Prop" in msg_locked

print("--- message verrouillé (sans abonnement) ---")
print(msg_locked)
print("\n--- message débloqué (avec SAO_COOKIE) ---")
print(msg_unlocked)
print("\n✅ tous les tests passent")
