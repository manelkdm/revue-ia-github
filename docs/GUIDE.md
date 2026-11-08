# Guide du prototype

## 1. Installer et essayer

Avec Python 3.11 ou plus récent, depuis le dépôt :

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe -m review.cli demo
```

Sur Linux, utiliser `.venv/bin/python`. La démonstration fonctionne sans jeton ni Ollama. Elle enregistre deux fichiers dans `runs/IDENTIFIANT/` : `review.json` et `report.md`.

## 2. Préparer GitHub et Ollama

Copier `.env.example` vers `.env` sans écraser une configuration existante. Renseigner `GITHUB_TOKEN` avec un jeton limité au dépôt concerné et capable de lire les PR et les issues. La publication manuelle nécessite aussi le droit d'écrire un commentaire.

Installer Ollama, puis lancer :

```text
ollama pull qwen2.5-coder:7b
ollama serve
```

Si Ollama fonctionne déjà en arrière-plan, ne pas démarrer un second serveur. Les valeurs par défaut sont `http://localhost:11434`, `qwen2.5-coder:7b` et un délai de 300 secondes par requête, réglable dans `.env`.

## 3. Relier les exigences

Dans la description d'une PR ouverte, prête et provenant du même dépôt :

```text
Issue liée : #42
```

Une URL complète vers une issue du même dépôt est aussi acceptée. Le champ anglais `Requirements issue: #42` reste accepté. Les autres mentions d'issues ne sont pas suivies.

La description de cette unique issue fournit les exigences ; ses commentaires ne sont pas lus. Les divergences avec la PR sont signalées. Sans issue, ou si elle est inaccessible, la revue continue en indiquant la limite.

Un exemple d'issue est fourni dans [examples/ISSUE.md](../examples/ISSUE.md).

## 4. Lancer la revue

```powershell
./.venv/Scripts/python.exe -m review.cli review --repo PROPRIETAIRE/DEPOT --pr 1 --standards examples/STANDARDS.md
```

Pour ajouter les contrôles réels :

```powershell
./.venv/Scripts/python.exe -m review.cli review --repo PROPRIETAIRE/DEPOT --pr 1 --evidence CHEMIN/evidence.json
```

Les preuves doivent correspondre au commit exact de la PR. Sans elles, le programme ne prétend pas avoir exécuté les tests.

Les sept rôles sont conservés :

1. Extraire les exigences de l'issue.
2. Examiner la logique du code.
3. Examiner sa lisibilité et sa maintenabilité.
4. Comparer les exigences au diff et signaler les conflits.
5. Examiner les tests visibles et les preuves fournies.
6. Examiner les risques de sécurité.
7. Rédiger une synthèse courte et repérer les constats répétés.

Le rapport Markdown regroupe les constats. Le JSON conserve les analyses originales et les résultats des outils. Les regroupements sémantiques proposés par le modèle sont limités au même fichier et à la même ligne ; des problèmes distincts doivent rester séparés. Le programme conserve toutes les références, toutes les preuves et la gravité maximale. Les doublons textuels sont regroupés même si l'agent de synthèse échoue. La pertinence des regroupements proposés par l'IA reste à vérifier humainement.

Le code de sortie 2 indique une erreur ou un rapport IA incomplet. Un rapport incomplet est sauvegardé lorsque le contexte a pu être lu : modèle indisponible, exigences absentes ou diff trop long, par exemple. Le modèle n'analyse pas les fichiers inchangés.

## 5. Lire et éventuellement publier

Lire `report.md` avant toute publication. Pour ajouter explicitement un commentaire GitHub :

```powershell
./.venv/Scripts/python.exe -m review.cli publish runs/IDENTIFIANT/review.json
```

Cette commande manuelle vérifie les commits, la description de la PR et les exigences avant l'envoi. Elle refuse les simulations. En cas d'envoi incertain, vérifier le commentaire et `publication.json` avant de réessayer.

À cette étape, chaque nouvelle revue publiée manuellement peut créer un commentaire distinct. La mise à jour d'un commentaire unique, les liens d'artefacts et la gestion des exécutions concurrentes seront ajoutés à l'étape 4.

Les anciens rapports au format 1 ou 2 sont refusés ; relancer la revue pour créer un rapport au format 3.

## Vérifier le programme

```powershell
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Voir [VALIDATION.md](VALIDATION.md) pour les résultats réellement obtenus et [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) pour les contrôles distants.

Références des interfaces utilisées : [issues GitHub](https://docs.github.com/en/rest/issues/issues#get-an-issue), [sorties structurées Ollama](https://docs.ollama.com/capabilities/structured-outputs).
