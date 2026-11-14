"""Carty Radar sur le serveur Contabo (14/11/2026) : la boucle reprend l'état du dépôt au premier démarrage
(aucun ancien pick renvoyé), le garde ensuite dans le volume, et relance un passage même après un échec.
Lancer : python -m unittest tests/test_serveur.py
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

RACINE = pathlib.Path(__file__).resolve().parent.parent


class BoucleServeur(unittest.TestCase):
    def lancer(self, faux_script, passages=2):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "serveur").mkdir()
        shutil.copy(RACINE / "serveur" / "boucle.sh", tmp / "serveur" / "boucle.sh")
        (tmp / "state").mkdir()
        (tmp / "state" / "seen.json").write_text('{"deja": 1}')
        (tmp / "carty_watch.py").write_text(faux_script)
        donnees = tmp / "volume"
        env = dict(os.environ, DOSSIER_DONNEES=str(donnees), INTERVALLE_S="0", PASSAGES_MAX=str(passages))
        r = subprocess.run(["sh", "serveur/boucle.sh"], cwd=tmp, env=env, capture_output=True, text=True, timeout=30)
        return r, donnees

    def test_etat_repris_puis_garde_dans_le_volume(self):
        script = ("import os,json,pathlib\n"
                  "p=pathlib.Path(os.environ['STATE_PATH']); d=json.loads(p.read_text()); d['n']=d.get('n',0)+1; p.write_text(json.dumps(d))\n")
        r, donnees = self.lancer(script, passages=3)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("etat initial repris du depot", r.stdout)
        import json
        etat = json.loads((donnees / "seen.json").read_text())
        self.assertEqual(etat["deja"], 1, "les picks déjà vus du dépôt sont repris")
        self.assertEqual(etat["n"], 3, "3 passages ont écrit dans le volume")

    def test_un_passage_en_echec_ne_stoppe_pas_la_boucle(self):
        r, _ = self.lancer("import sys; print('passage'); sys.exit(3)\n", passages=2)
        self.assertEqual(r.stdout.count("passage\n"), 2)
        self.assertIn("passage en echec (code 3)", r.stdout)

    def test_image(self):
        d = (RACINE / "Dockerfile").read_text()
        self.assertIn("serveur/boucle.sh", d)
        self.assertIn("tzdata", d)
        self.assertIn("INTERVALLE_S:-120", (RACINE / "serveur" / "boucle.sh").read_text())


if __name__ == "__main__":
    unittest.main()
