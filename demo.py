"""Démonstration : route Outremont selon le scénario 'réseau artériel' et
affiche les indicateurs clés. Livrable « script de démonstration » (sujet ERO1).

Usage : python demo.py
"""
from scenarios import run_scenario, SECTORS

PLACE = SECTORS["outremont"]


def main():
    print(f"Secteur : {PLACE}")
    print("Scénario : réseau artériel (déblaiement prioritaire des grandes voies)\n")
    r = run_scenario(PLACE, "arteriel")
    print(f"  Coût total journalier        : {r['cout_total']} $")
    print(f"  Km parcourus                 : {r['km_total']} km")
    print(f"  Heures totales               : {r['heures_total']} h")
    print(f"  Part à vide                  : {r['part_a_vide'] * 100:.1f} %")
    print(f"  Véhicules pour finir en <=8h : {r['nb_vehicules_8h']}")
    print(f"  T1 (réseau prioritaire dégagé): {r['T1_reseau_prioritaire_h']} h")
    print(f"  Couverture prioritaire (1/2/4h): {r['couverture_prioritaire']}")
    print("\nDémonstration OK.")


if __name__ == "__main__":
    main()
