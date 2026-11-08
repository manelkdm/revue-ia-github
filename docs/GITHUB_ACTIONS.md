# Les workflows GitHub Actions

## Ce qui se passe

Le workflow de tests du programme reste inchangé : **un job Ubuntu avec Python 3.12**, qui installe le projet, lance les tests puis la démonstration.

Le workflow **Revue de la Pull Request** (`evidence.yml`) comporte deux parties :

1. **Contrôles du prototype** : Ruff, Bandit et Gitleaks analysent `example_app` ; pytest exécute `tests/test_calculator.py` et mesure sa couverture.
2. **Revue IA consultative** : Ollama télécharge `qwen2.5-coder:7b`, les sept agents analysent le diff et les preuves, puis les rapports sont enregistrés.

Un contrôle en échec peut donc être expliqué par les agents. Une panne du modèle reste distincte du résultat des contrôles. **Aucun commentaire n'est publié automatiquement à cette étape.**

## Quand la revue démarre

- PR ouverte ou rouverte, nouveau commit, sortie du mode brouillon.
- Modification du titre ou de la description.
- Relance manuelle avec un numéro de PR.

Les brouillons, PR fermées et PR provenant d'un fork sont exclus. Un passage en brouillon annule une revue en cours. Les modifications de l'issue liée nécessitent une relance manuelle.

Pour une relance : dans l'onglet **Actions**, sélectionner **Revue de la Pull Request**, puis **Run workflow**, choisir la branche par défaut et indiquer le numéro de PR.

## Où lire le résultat

Ouvrir l'exécution dans **Actions**, puis télécharger ses fichiers :

- `preuves-COMMIT-TENTATIVE` contient les résultats des contrôles.
- `revue-COMMIT-TENTATIVE` contient les rapports disponibles, les preuves, `durees.txt` et `memoire-ollama.txt`.

Le fichier `report.md` est le rapport lisible ; `review.json` conserve le détail des sept agents. La mémoire d'Ollama est échantillonnée pendant la revue ; ce n'est pas une mesure exacte de son pic.

Si le modèle échoue, les agents concernés sont marqués incomplets. Si le contexte GitHub ne peut pas être lu, si les preuves sont invalides ou si le délai global expire, il peut ne pas y avoir de rapport : consulter alors le résumé et les journaux du job.

## Premier essai à effectuer

**Ce workflow est préparé, mais son exécution réelle reste à valider.** Il faut d'abord intégrer ces changements sur la branche cible : le reviewer utilisé vient volontairement de cette branche, pas de la PR en cours d'analyse.

Ensuite :

1. Ouvrir une petite PR sur `example_app` dans le même dépôt.
2. Ajouter facultativement `Issue liée : #NUMERO` dans sa description.
3. Vérifier les deux parties de l'exécution et télécharger le rapport.
4. Confirmer que le rapport concerne le bon commit, contient les sept résultats et regroupe les répétitions.
5. Examiner la durée et la mémoire avant d'ajuster le contexte ou la sortie du modèle.

Aucun jeton personnel ni installation locale d'Ollama n'est nécessaire pour ce workflow : il utilise le jeton temporaire de GitHub en lecture et démarre Ollama sur son runner Ubuntu.

## Protections conservées

Le collecteur et le reviewer proviennent du commit de la branche cible. Les tests de la PR tournent dans un conteneur sans réseau et sans secrets. Le job IA ne récupère pas et n'exécute pas le code de la PR : il lit le diff via GitHub.

Les preuves sont récupérées par leur identifiant d'artefact dans la même exécution. Leur dépôt, PR, commit de tête/base, exécution et tentative sont contrôlés avant utilisation. Cette provenance ne prouve pas que les tests écrits dans la PR sont pertinents.

Ruff garde `E4,E7,E9,F`. Les outils absents/en erreur, les constats, les tests absents/échoués et la couverture inconnue rendent le contrôle non réussi. Aucun seuil minimal de couverture n'est imposé pour le moment.

La préparation d'Ollama est bornée à 30 minutes, chaque requête à 900 secondes et le job IA à 240 minutes : ce sont des limites d'exécution, pas des objectifs de performance. Les mesures du premier essai permettront de les ajuster.

Si des contrôles obligatoires sont configurés dans GitHub, utiliser **Contrôles du prototype** et les tests du programme ; la **Revue IA consultative** ne doit pas devenir une condition obligatoire de fusion.

La publication et la mise à jour d'un commentaire unique restent prévues à l'étape 4.

Références : [déclencheurs GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [Ollama dans Docker](https://docs.ollama.com/docker).
