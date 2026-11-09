# Revue de code GitHub — 7 agents IA

Cette version conserve **les sept agents spécialisés**, les contrôles Ruff, Bandit, Gitleaks et pytest, les rapports Markdown/JSON, le CSV, le tableau de bord et la démo. **GitHub Issues remplace OpenProject**. Un workflow GitHub Actions exécute la revue sans installation locale.

## Démarrage rapide (GitHub uniquement)

1. Fusionnez le changement qui ajoute les workflows à la branche par défaut. Les workflows `workflow_run` doivent se trouver sur cette branche pour fonctionner.
2. Créez une **GitHub Issue** décrivant vos exigences et critères d'acceptation.
3. Créez une branche **dans le même dépôt**, faites vos modifications et ouvrez une Pull Request.
4. Ajoutez `Closes #12` dans la description de votre PR (remplacez 12 par le numéro de votre issue).
5. Dans **Actions**, suivez `Preuves de la Pull Request`, puis `Revue IA (sept agents)`.

**Aucun `.env`, token personnel, Docker local ou installation de Python n'est requis.** Le workflow utilise le `GITHUB_TOKEN` automatique et démarre Ollama sur un runner GitHub temporaire.

Par défaut, le modèle est `qwen2.5-coder:1.5b`, pour limiter le coût CPU. Vous pouvez le remplacer via **Settings → Secrets and variables → Actions → Variables** : `REVIEW_OLLAMA_MODEL=qwen2.5-coder:7b` (plus lent, résultats potentiellement meilleurs). Le service GitHub Actions doit disposer des permissions `issues: write` prévues dans le workflow ; les règles de dépôt/organisation peuvent restreindre la publication.

### Déroulement

- `tests.yml` : tests unitaires du robot.
- `evidence.yml` : collecte isolée des preuves sur le code de la PR et les publie comme artefact lié au SHA exact.
- `ai-review.yml` : après le workflow de preuves, lit une issue GitHub et le diff, exécute les **7 agents d'origine** avec Ollama, puis publie/met à jour un seul commentaire dans la PR. Les rapports complets sont sauvegardés comme artefacts (14 jours).
- La décision est une **recommandation uniquement** : aucune approbation automatique, aucune fusion.

Le gate des preuves peut échouer ; l'artefact de preuves est néanmoins créé avant le gate, afin que les agents puissent examiner les échecs. Les résultats d'analyse incomplets sont affichés comme incomplets, jamais comme une réussite.

### Limitations

- **PRs de la même repository uniquement** pour les publications automatiques. Les contributions externes (forks) sont volontairement ignorées par le workflow privilégié.
- Une PR doit être liée à une issue avec `Closes #N`, `Fixes #N` ou `Resolves #N`. Une seule issue est analysée.
- Le diff est limité à 45 000 caractères ; la description de l'issue à 15 000 caractères. Aucune troncature silencieuse.
- Ollama sur CPU (7 agents) peut être lent. Les runs GitHub ont une durée maximale de 60 minutes. Le téléchargement du modèle nécessite Internet. Les versions des actions et du modèle devraient être épinglées après validation.
- Ruff, Bandit et pytest ciblent `example_app` par défaut. Pour votre application, adaptez `REVIEW_SCAN_PATH`, `REVIEW_COVERAGE_SOURCE` et les dépendances du runner d'analyse.
- Le workflow `workflow_run` ne doit jamais exécuter le code d'une branche PR avec son jeton à permission d'écriture. Le script approuvé est obtenu depuis la branche par défaut. Les preuves restent des données non fiables.
- Revue fondée sur le diff, les critères de l'issue et les preuves disponibles ; elle ne remplace pas un humain.

## Mode local facultatif

Vous pouvez toujours lancer la démo sans service externe :

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m review.cli demo
```

Pour analyser une PR manuellement, fournissez `GITHUB_TOKEN` (avec permissions minimales) et lancez Ollama, puis :

```bash
python -m review.cli review --repo OWNER/REPO --pr 2 --issue 12 --standards examples/STANDARDS.md
# ou : python -m review.cli review --repo OWNER/REPO --pr 2 --publish
```

`--issue` est facultatif lorsque la description de la PR référence explicitement une issue. En mode local, fournissez les variables d'environnement directement ; aucun fichier `.env` n'est chargé.

La surveillance `python -m review.watch`, le tableau de bord `dashboard.py` et l'export `python -m review.cli export` restent disponibles en mode local. Les rapports conservent le champ `issue_id`, qui correspond désormais au **numéro d'issue GitHub** (compatibilité schéma 2).

## Contenu conservé

- `review/agents/agent1_requirements.py` à `agent7_synthesis.py` : sept rôles distincts et prompts existants.
- `review/orchestrator.py`, `models.py`, `llm.py`, `report.py` : orchestration, Pydantic, Ollama et rapports.
- `review/ci.py`, `scripts/collect_evidence.py`, `Dockerfile.runner` : analyses déterministes et validation SHA.
- `review/watch.py`, `dashboard.py`, `example_app/`, `tests/` : outils facultatifs, exemple et tests.

Voir [MIGRATION.md](MIGRATION.md) pour le détail des modifications.
