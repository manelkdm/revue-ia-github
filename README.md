# Revue de code avec GitHub et sept agents IA

Version 0.3.0 : une PR GitHub, une issue facultative pour les exigences, et Ollama pour les analyses. Les rapports sont en français.

Les sept agents restent spécialisés : exigences, code, qualité, conformité, tests, sécurité, puis synthèse. Le dernier propose les regroupements de constats similaires. Le rapport final présente une seule liste, en conservant les preuves, les sources et la gravité la plus élevée. Les détails des sept analyses restent dans le JSON.

## Essai sans GitHub ni modèle

Depuis le dépôt, avec Python installé :

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m unittest discover -s tests -v
./.venv/Scripts/python.exe -m review.cli demo
```

Sur Linux, remplacer `.venv/Scripts/python.exe` par `.venv/bin/python`.

La simulation crée `runs/IDENTIFIANT/review.json` et `report.md`. Elle ne contacte aucun service.

## Revue réelle

Copier `.env.example` vers `.env` et renseigner `GITHUB_TOKEN`. Démarrer Ollama et télécharger `qwen2.5-coder:7b`.

Dans la description de la PR, ajouter facultativement :

```text
Issue liée : #42
```

L'issue doit appartenir au même dépôt. Sa description fait autorité pour les exigences. Sans issue, le rapport le signale et la revue du code et des tests continue.

```powershell
./.venv/Scripts/python.exe -m review.cli review --repo PROPRIETAIRE/DEPOT --pr 1 --standards examples/STANDARDS.md
```

Ajouter `--evidence CHEMIN/evidence.json` pour intégrer des résultats de contrôles correspondant au commit. Sans preuves, les tests et la couverture sont indiqués comme inconnus.

La revue réelle ne publie rien automatiquement. La commande manuelle `publish` ajoute un commentaire GitHub ; la mise à jour automatique d'un commentaire unique reste prévue à l'étape 4.

## Périmètre actuel

- Analyse du diff uniquement, limitée à 45 000 caractères. Au-delà, rapport IA incomplet ; preuves d'outils conservées.
- Rapport consultatif, aucune fusion automatique.
- Fichiers JSON/Markdown uniquement : pas de tableau de bord, de base SQLite ni de surveillance périodique.
- Un seul job de tests GitHub sur Ubuntu avec Python 3.12.
- Automatisation des appels Ollama dans Actions à réaliser à l'étape 3.

Voir le [guide](docs/GUIDE.md), les [workflows](docs/GITHUB_ACTIONS.md), les [vérifications](docs/VALIDATION.md) et le [plan](DEVELOPMENT_PLAN.md).
