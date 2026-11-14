"""Carty Radar — outils GitHub à jour (14/11/2026, Michael : « Ok pour les 3 angles »).

GitHub avertissait à chaque passage : actions/checkout@v4 et actions/setup-python@v5 tournent sur Node.js 20
(forcées sur Node 24), et « ubuntu-latest » bascule vers Ubuntu 26 depuis le 19/10/2026. Ce test rougit si le
workflow revient à ces versions ou à une machine flottante qui peut changer sans prévenir.
Lancer : python -m unittest tests/test_workflow_outils.py   (ou pytest)
"""
import pathlib
import re
import unittest

WF = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows" / "carty-watch.yml"


class OutilsAJour(unittest.TestCase):
    def setUp(self):
        self.t = WF.read_text(encoding="utf-8")

    def test_machine_figee(self):
        self.assertRegex(self.t, r"(?m)^\s+runs-on:\s*ubuntu-24\.04\s*$")
        self.assertNotIn("ubuntu-latest", self.t)

    def test_actions_recentes(self):
        def majeure(nom):
            m = re.search(r"uses:\s*actions/" + nom + r"@v(\d+)", self.t)
            self.assertIsNotNone(m, nom + " absente")
            return int(m.group(1))
        self.assertGreaterEqual(majeure("checkout"), 7)
        self.assertGreaterEqual(majeure("setup-python"), 7)

    def test_declencheurs_intacts(self):
        # le moteur (repository_dispatch carty-tick toutes les 2 min) et le filet de sécurité ne bougent pas
        self.assertIn("types: [carty-tick]", self.t)
        self.assertIn('- cron: "*/15 * * * *"', self.t)


if __name__ == "__main__":
    unittest.main()
