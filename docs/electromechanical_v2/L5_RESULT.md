# Résultat de réception L5

| Champ | Valeur |
|---|---|
| Exigence et contrôle | `CAB-CARTO-001`, `MEC-INT-001`, `METH-001` → `T-EM-ENGINE-L5` |
| Exécution | 14 novembre 2026, Windows amd64, FreeCAD 1.1.3 |
| Verdict | `L5_PASS` · `GO` · banc numérique |
| Sélection | `lateral-service` · L1 latéral et L2 direct |
| Rétrovalidation | 13/13 contrôles L4 · deux processus neufs · L1 et L2 |
| Mesures | 221,4159265359 mm de câble · 10,9927088741 mm de cote haute · 7 mm de garde minimale d’extraction |
| Budget consommé | 7/12 variantes détaillées · 3/3 corrections locales · 3 familles examinées · 2/2 consolidations natives |
| Reprise | Pause après 8 étapes, reprise au même emplacement, manifeste inchangé, T0 valide |

| Portefeuille | Constat |
|---|---|
| `conflicting-routes` | Deux affectations différentes de L1. Fusion refusée avant construction. |
| `shared-service` | Décisions locales admissibles. L4 rejette la garde de 0 mm entre L1 et L2. |
| `lateral-service` | Seul élément du front de Pareto des copies consolidées admissibles. |
| `upper-service` | Tentative écartée à l’épuisement du budget de consolidation. |

[Preuve et empreintes](../verification/electromechanical_convergence_l5.json) ·
[Configuration et recette](../../convergence_manager/README.md) ·
[Portée et critères proposés pour GO2bis, GO3A et GO3B](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l5)
