# Division sûre

Exemple de description d'issue GitHub. Dans la PR, indiquer `Issue liée : #42` en remplaçant 42 par son numéro.

En tant qu'utilisateur de la calculatrice, je veux recevoir une erreur compréhensible
lorsque je divise par zéro, afin de corriger ma saisie.

## Critères d'acceptation

- CA-1 : divide(8, 2) retourne 4.
- CA-2 : divide(8, 0) déclenche ValueError avec le message division par zero.
- CA-3 : divide(-8, 2) retourne -4.

## Contraintes

La signature publique divide(a, b) reste identique. Aucune dépendance supplémentaire.
