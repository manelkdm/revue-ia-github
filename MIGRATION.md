# Migration OpenProject → GitHub Issues, sans supprimer les sept agents

## Modifié

- `review/connectors.py` : OpenProject supprimé du chemin actif ; lecture de l'issue GitHub via `GET /repos/{owner}/{repo}/issues/{number}`, association à la PR via sa description.
- `review/cli.py` : `--issue` remplace `--ticket`, numéro auto-détecté à partir de `Closes #N`. `--publish` est possible sur `review`. Pas d'obligation de `.env`.
- `review/publish.py` : publication **uniquement sur la PR**, avec vérification SHA/issue et journal local. Les relances mettent à jour le commentaire du bot.
- `review/watch.py` : conserve la surveillance facultative sans OpenProject.
- `review/report.py`, `review/agents/agent1_requirements.py` : vocabulaire GitHub Issue.
- `.github/pull_request_template.md` : lien à l'issue dans la description.
- `tests/` : tests API et publication adaptés.

## Ajouté

- `.github/workflows/ai-review.yml` : déclenché par `workflow_run` à la fin de la collecte des preuves, après fusion sur `main`. Aucune exécution du code non fiable de la PR avec token à permission d'écriture.

## Préservé

- Les **sept agents**, leurs fonctions, consignes et la recommandation déterministe.
- Modèles Pydantic `Context`, `Evidence`, `Review` (le champ `issue_id` représente désormais une issue).
- Collecteur Docker isolé, tests, Ruff, Bandit, Gitleaks, validation SHA et gate.
- Rapports Markdown/JSON, historique SQLite, CSV, dashboard, démo et surveillance optionnelle.

## Restant facultatif/legacy

- `compose.yaml` et `scripts/init_env.py` étaient destinés au labo OpenProject. Ils ne sont pas utilisés par les nouveaux workflows et pourront être supprimés après validation si désiré.
- Les guides historiques dans `docs/` documentent en partie l'ancienne architecture ; ce README et ce fichier décrivent le nouveau parcours.
- La revue automatique ne prend en charge que les PRs de branches du même dépôt.
