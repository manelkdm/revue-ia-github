# Plan de développement

Statut : développement autorisé. Procéder une étape à la fois, vérifier les résultats et faire un point avant de poursuivre. Étapes 1 et 2 réalisées et vérifiées localement. Étape 3 préparée et testée localement ; essai réel dans Actions encore nécessaire.

## Choix confirmés

- Construire un prototype utile pour `example_app` dans ce dépôt : détecter des problèmes introduits volontairement, expliquer les incertitudes et produire une revue lisible.
- Rester simple : une configuration fixe, peu de composants et des explications claires. Pas de CrewAI.
- Développement et tests locaux sous Windows. GitHub Actions utilise Ubuntu, avec un seul job de tests en Python 3.12.
- Ollama avec `qwen2.5-coder:7b`. Aucun service d'inférence payant en secours.
- **Conserver les sept agents** : exigences, code, qualité, conformité, tests, sécurité et synthèse. La proposition précédente de passer à trois agents est abandonnée.
- Rapports, messages et documentation en **français**.
- Le dernier agent produit une synthèse brève et propose les regroupements de constats similaires. Le programme regroupe aussi les doublons textuels. Le rapport final présente les problèmes une seule fois, tout en conservant les preuves, les sources et la gravité maximale ; le JSON conserve les analyses originales.
- Aucun objectif de durée initial. Garder les réponses brèves, mesurer le temps et la mémoire, réduire le contexte ou la sortie si nécessaire. Un dépassement de délai ne doit jamais devenir un succès.
- Retirer le tableau de bord, SQLite/export historique, la surveillance périodique, OpenProject et la configuration devenue inutile.

## Exigences et contexte

- Le champ `Issue liée : #42` dans la description de la PR désigne une unique issue du même dépôt. Une URL GitHub complète et le champ anglais `Requirements issue: #42` sont aussi acceptés.
- La description de l'issue fait autorité pour les exigences. Ses commentaires sont exclus initialement. Signaler les conflits avec la PR sans les résoudre silencieusement.
- Sans issue liée, le signaler au réviseur et poursuivre le reste de la revue. Distinguer une référence absente, invalide et inaccessible. Ne pas inventer d'exigences.
- Analyser uniquement le diff et signaler le contexte omis. Limite initiale : 45 000 caractères. Au-delà, rapport IA incomplet et conservation des résultats d'outils ; pas de troncature silencieuse ni de découpage automatique.
- Conserver la validation JSON, le masquage des secrets, la distinction modèle/outils et la vérification du commit des preuves.
- Versionner le nouveau schéma de rapport et refuser clairement les anciens rapports incompatibles.

## Contrôles

- Les contrôles de revue viseront l'application prototype et `tests/test_calculator.py`. Les tests du reviewer restent séparés.
- Ruff conserve initialement `E4,E7,E9,F` ; ne pas annoncer une vérification PEP 8 complète.
- Les constats Bandit/Gitleaks font échouer leur contrôle, sauf exception explicitement configurée. Les tests doivent réussir. Un outil absent ou défaillant n'est jamais considéré comme réussi.
- Mesurer la couverture de `example_app` avant de choisir un seuil. Ne pas reprendre automatiquement l'ancien seuil de 80 %.
- Les constats IA restent consultatifs ; la disponibilité du modèle n'est pas un prérequis à la fusion. Les contrôles déterministes deviennent obligatoires une fois leur périmètre et leur référence établis.

## Déclenchement et publication à terme

- Revoir les PR prêtes du même dépôt à l'ouverture, à la réouverture, au passage hors brouillon, aux nouveaux commits et aux modifications de description. Exclure les brouillons et les PR de forks.
- Permettre une relance manuelle avec les mêmes conditions. Les modifications de l'issue nécessitent initialement une relance manuelle.
- Utiliser le reviewer et sa configuration depuis la branche cible ; analyser/tester le prototype au commit exact de la PR. Les tests du reviewer vérifient ses modifications proposées avant fusion.
- Isoler l'exécution du code de PR. Seul un job de publication séparé, qui n'exécute pas ce code, reçoit le droit de commenter.
- Vérifier la provenance des artefacts : dépôt, PR, exécution et commit, pas seulement le JSON et son SHA déclaré.
- Retrouver le commentaire du robot avec un marqueur stable et une recherche paginée. Sérialiser la publication par PR et gérer les réponses d'envoi incertaines.
- Avant publication, revérifier l'éligibilité, les commits de tête/base, la description de PR et les exigences. Refuser les résultats périmés.
- Un commentaire bref, au plus cinq constats prioritaires regroupés, les contrôles, le commit, les limites et les liens vers les rapports complets.
- En cas d'échec de la revue d'un nouveau commit, indiquer que ce dernier n'a pas été complètement revu ; ne pas présenter l'ancien succès comme actuel.

## Étape 1 : fiabiliser le fonctionnement local

Corriger les chemins temporaires, UTF-8, la fermeture des ressources et les tests dépendant de Windows. Garder le workflow simple : installer le projet, lancer les tests et la démonstration sur Ubuntu/Python 3.12. Mesurer la couverture localement.

Vérification : tests locaux et simulation réussis ; résultats Ubuntu à confirmer dans Actions.

Résultats locaux : Python 3.14.6 / Pydantic 2.14.1, 52 tests dont 51 réussis et un ignoré faute de privilège Windows pour créer un lien symbolique. Les trois tests du prototype couvrent les quatre instructions exécutables (100 %). Aucun nouveau seuil imposé.

## Étape 2 : simplifier les composants et améliorer la synthèse

Conserver les sept agents et supprimer les répétitions dans le rapport final. Remplacer OpenProject par GitHub et une issue facultative. Adapter les schémas, commandes, consignes et rapports. Retirer les composants, dépendances et commandes obsolètes ; garder les guides cohérents.

Réutiliser le collecteur de preuves existant, la validation Ollama, le masquage et les contrôles de fraîcheur. Stocker uniquement les rapports JSON/Markdown.

Vérification : simulations couvrant issue présente/absente, conflits d'exigences, preuves manquantes, panne du modèle, JSON invalide, diff trop long, doublons exacts/sémantiques et échec de synthèse. Aucun constat d'outil ne disparaît ; aucun constat distinct ne doit être supprimé. Les anciens rapports sont refusés clairement. Les regroupements sémantiques restent une proposition IA à vérifier humainement.

## Étape 3 : exécuter les contrôles et Ollama dans Actions

Adapter le collecteur existant au prototype. Ajouter les déclencheurs convenus, installer Ollama et produire les rapports réels, y compris partiels si possible. Garder l'isolation du code de PR et la provenance des preuves explicites.

Vérification : une PR d'exemple produit des résultats d'outils et une revue réelle ; mesurer durée, mémoire, validité des sorties et visibilité des échecs.

## Étape 4 : mettre à jour un commentaire unique

Ajouter la recherche/mise à jour du commentaire, la sérialisation, les contrôles de fraîcheur, les liens de commit/artefacts et la reprise des envois incertains.

Vérification : nouveaux commits et relances mettent à jour le même commentaire ; aucune duplication ni écrasement par une ancienne exécution ; les échecs de la dernière revue sont visibles.

## Étape 5 : valider l'utilité et finaliser les guides

Essayer des bugs connus, changements corrects, conflits d'exigences, issues absentes et pannes. Ajuster les consignes et paramètres. Vérifier les guides, exemples et modèle de PR.

Vérification : constats brefs et étayés, limites honnêtes, procédure reproductible et limites opérationnelles documentées.

## Reprise du travail

- Dépôt d'origine : `C:/Users/manel/Desktop/AQL/revue-ia-github`.
- Dépôt cible : `C:/Users/manel/Desktop/AQL/revue-ia-fork`.
- Étape 1 réalisée localement ; exécution distante non vérifiée.
- Étape 2 réalisée avec sept agents et sorties françaises : 72 tests, 71 réussis et un ignoré faute de privilège Windows pour les liens symboliques. Démonstration et exemples de rapports validés. Les regroupements sémantiques sont testés avec des réponses simulées ; l'évaluation avec Ollama reste à faire.
- Étape 3 : workflow existant étendu avec deux jobs Ubuntu (contrôles du prototype, revue IA consultative), déclenchement automatique/manuellement, Ollama 7b, rapports même incomplets, durée et mémoire échantillonnée. Provenance et commits vérifiés avant l'analyse. 76 tests locaux : 75 réussis, un ignoré ; YAML et commandes Bash vérifiés. Aucun essai réel Actions ni mesure du modèle 7b réalisé depuis cette session : cette validation reste ouverte.
- Pour le premier essai, intégrer d'abord ces changements sur la branche cible, car le workflow utilise son reviewer. Deux commits antérieurs sont également encore en avance sur origin/main dans le checkout local. Aucun push ni changement distant effectué pendant cette étape.
- Étapes 4 et 5 non commencées. La publication actuelle reste une commande manuelle ; elle ne met pas encore à jour un commentaire unique.
