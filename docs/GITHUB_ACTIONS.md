# Les workflows GitHub Actions

## Tests du programme

`.github/workflows/tests.yml` reste simple : un job sur `ubuntu-latest`, avec Python 3.12.

Il récupère le dépôt, installe Python et le projet, exécute les tests unitaires, puis lance la démonstration simulée. Il se déclenche sur les mises à jour de `main`, sur les PR et manuellement. Il ne lance pas Ollama et ne publie pas de commentaire.

## Collecte des preuves existante

`.github/workflows/evidence.yml` prépare le collecteur depuis le commit de la branche cible, puis examine le commit exact de la PR. Les outils tournent dans un conteneur sans réseau et sans jeton transmis aux tests.

Le collecteur produit des résultats Ruff, Bandit, Gitleaks, pytest et couverture. Le fichier est validé et conservé dans l'artefact `review-evidence-SHA` avant le contrôle final. Un contrôle absent, en erreur, avec constats, ou des tests absents/échoués rendent ce contrôle final non réussi. La couverture doit être connue ; aucun seuil minimal n'est actuellement imposé par défaut.

Les chemins actuels sont configurés par `REVIEW_SCAN_PATH` et `REVIEW_COVERAGE_SOURCE`, tous deux à `example_app` par défaut. **La collecte existante découvre encore tous les tests et Gitleaks parcourt tout le dépôt.** Le recentrage complet sur l'application prototype appartient à l'étape 3.

Ruff utilise les règles `E4,E7,E9,F`, pas l'ensemble des règles PEP 8. Les preuves portent un SHA mais ne sont pas une attestation d'authenticité ; vérifier leur provenance et la pertinence des tests.

## Utiliser les preuves localement

Télécharger l'artefact du bon commit, puis :

```text
python -m review.cli review --repo PROPRIETAIRE/DEPOT --pr 1 --evidence CHEMIN/evidence.json
```

Le programme refuse un SHA différent de celui de la PR.

## Prochaines étapes

L'étape 3 ajoutera la revue réelle avec Ollama dans Actions. L'étape 4 ajoutera la publication automatique dans un commentaire unique, avec vérification des données et protection contre les résultats périmés.

Le code de la PR ne doit pas être exécuté dans le job disposant du droit de publier. Les tests du reviewer restent indépendants des avis consultatifs de l'IA.

L'exécution distante de ces workflows reste à vérifier dans le dépôt GitHub.
