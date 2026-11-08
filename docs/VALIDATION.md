# Vérifications et limites du prototype

## Étape 3 : raccordement à GitHub Actions

Vérification locale : **76 tests, 75 réussis et un ignoré** (privilège Windows pour les liens symboliques). Le YAML et la syntaxe Bash des commandes du workflow ont été vérifiés.

Les nouveaux tests vérifient le périmètre du prototype, le refus d'un fichier de tests extérieur/absent, les chemins des constats Gitleaks, la provenance des preuves (dépôt, PR, base, exécution et tentative), et le refus de lancer le modèle si les commits attendus ont changé. La normalisation remplace la provenance déclarée par le conteneur par celle du workflow.

**L'exécution réelle dans Actions reste à faire.** Docker n'est pas installé localement ; Ollama est présent avec le modèle 14b, mais le modèle prévu est 7b. Aucun autre modèle n'a été substitué. Aucun jeton GitHub n'est configuré dans l'environnement ou le fichier de configuration de cette session pour appeler Actions.

Les changements doivent d'abord être intégrés à la branche cible, utilisée comme source du reviewer. Le premier essai doit produire les rapports, vérifier les sept agents et les regroupements, puis examiner les durées et les échantillons de mémoire. Les échantillons toutes les dix secondes ne constituent pas une mesure exacte du pic mémoire.

Une panne de téléchargement/démarrage d'Ollama permet quand même de tenter la production d'un rapport incomplet. Un échec de récupération du contexte GitHub, des preuves invalides ou l'expiration du délai global peuvent empêcher la production d'un rapport ; l'échec du job doit alors rester visible. Ne pas confondre validation locale et validation de ce parcours distant.

## Étape 2 : sept agents et rapport sans répétitions

Vérification locale sous Windows, Python 3.14.6 et Pydantic 2.14.1 : **72 tests, dont 71 réussis et un ignoré**. Le test ignoré nécessite le droit Windows de créer un lien symbolique.

Les tests couvrent notamment :

- Les sept résultats d'agents et le refus des anciens rapports incompatibles.
- Une issue GitHub liée, absente, invalide ou inaccessible ; les conflits entre les exigences et la PR.
- La conservation des critères non évalués et des résultats d'outils, même si le modèle échoue.
- Les doublons textuels, les reformulations regroupées sur proposition de l'agent 7 et les groupes qui se recouvrent.
- La conservation de toutes les références, des preuves et de la gravité maximale ; le refus des références inventées et des regroupements entre emplacements différents.
- Une synthèse défaillante : les constats restent disponibles et les doublons textuels restent regroupés.
- Un commentaire limité à cinq constats regroupés, avec un rapport complet qui conserve les autres.
- Le diff trop long, le JSON modèle invalide, la sortie tronquée et les preuves d'un mauvais commit.
- Les commandes de revue avec ou sans issue, sans publication implicite.
- Le refus d'une publication simulée ou périmée et l'absence de nouvelle tentative aveugle après un envoi incertain.
- Les protections contre les redirections de jetons, le masquage, les artefacts invalides et les problèmes d'encodage.

La démonstration en ligne de commande fonctionne et les exemples JSON/Markdown ont été régénérés au format 3. Les rapports sont en français, sans SQLite.

Ces essais utilisent des réponses simulées. Ils valident le regroupement et la conservation des constats ; **ils ne prouvent pas que le modèle réel reconnaît tous les doublons sémantiques ou détecte tous les bugs**. Ces évaluations restent à faire avec Ollama aux étapes 3 et 5.

## Reproduire

Depuis la racine du dépôt, avec le projet installé dans l'environnement virtuel :

```powershell
./.venv/Scripts/python.exe -m unittest discover -s tests -v
./.venv/Scripts/python.exe -m review.cli demo --out artifacts/milestone-2-demo
```

Sur cette machine, la commande `python` pointe vers un alias Windows inutilisable ; `.venv/Scripts/python.exe` fonctionne. Sous Linux, utiliser `.venv/bin/python`.

## Référence de l'étape 1

Avant correction : 51 tests, 47 réussis et quatre erreurs liées à `/tmp`, aux privilèges de liens symboliques et au décodage/à la fermeture de SQLite.

Après correction de l'étape 1 : 52 tests, 51 réussis et un ignoré. Les trois tests du prototype couvraient les quatre instructions exécutables de `example_app` (100 %). Cette petite mesure ne démontre pas une qualité générale de la revue. SQLite a ensuite été retiré à l'étape 2.

Pour mesurer à nouveau la couverture, installer `pytest>=8,<10` et `pytest-cov>=6,<8`, puis :

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
./.venv/Scripts/python.exe -m pytest -p pytest_cov tests/test_calculator.py --cov=example_app --cov-report=term-missing --cov-report=json:artifacts/prototype-coverage.json
```

## Ce qui reste à vérifier

- Exécution distante sur Ubuntu/Python 3.12 : le workflow reste un seul job, sans matrice.
- Inférence réelle Ollama : qualité des constats, regroupements sémantiques, durée et mémoire.
- Construction/exécution réelle du conteneur d'analyse et provenance des preuves.
- Appels réels GitHub et publication : aucun commentaire n'a été envoyé pendant ces vérifications.
- Mise à jour automatique d'un commentaire unique et concurrence : prévues à l'étape 4.

La publication actuelle est manuelle et peut créer un commentaire pour chaque nouvelle revue. Les preuves doivent être liées au commit exact, mais un JSON valide ne garantit pas leur authenticité.

L'analyse porte sur le diff ; elle n'inspecte pas le contexte complet du dépôt. Le masquage des secrets et les regroupements IA ont des limites. Une validation humaine reste nécessaire.

Le [plan de développement](../DEVELOPMENT_PLAN.md) décrit la suite.
