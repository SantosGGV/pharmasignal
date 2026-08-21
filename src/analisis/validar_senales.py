"""
validar_senales.py

Validacion de la deteccion frente a asociaciones de referencia.

Este script contrasta la salida contra conocimiento externo al proyecto:

  - Controles positivos: asociaciones documentadas por las agencias
    reguladoras. El sistema deberia detectarlas. La proporcion que recupera es
    la sensibilidad.

  - Controles negativos: pares sin relacion farmacologica conocida. El sistema
    no deberia señalarlos. La proporcion que descarta es la especificidad.

"""

import os

import pandas as pd
from deltalake import DeltaTable

CURATED = os.path.expanduser("~/pharmasignal/data/curated")
SALIDA = os.path.expanduser("~/pharmasignal/outputs/validacion_senales.csv")

# Respaldo minimo exigido para considerar una senal detectada. Es el mismo
# criterio con el que la herramienta la muestra en sus vistas.
MIN_CASOS = 20

POSITIVOS = [
    ("ozempic", "impaired gastric emptying",
     "Advertencia incorporada por la FDA en 2023"),
    ("finasteride", "erectile dysfunction",
     "Efecto recogido en ficha tecnica"),
    ("ranitidine", "neoplasm malignant",
     "Retirada mundial en 2020 por contaminacion con NDMA"),
    ("oxycontin", "drug dependence",
     "Efecto de clase de los opioides"),
    ("belantamab mafodotin", "keratopathy",
     "Toxicidad ocular caracteristica"),
]

NEGATIVOS = [
    ("metformin", "keratopathy", "Sin mecanismo sobre el epitelio corneal"),
    ("ibuprofen", "erectile dysfunction", "Sin efecto sobre la funcion erectil"),
    ("omeprazole", "alopecia", "Sin efecto sobre el foliculo piloso"),
    ("atorvastatin", "cataract", "Sin toxicidad sobre el cristalino"),
    ("levothyroxine", "drug dependence", "Sin potencial de dependencia"),
    ("amoxicillin", "neoplasm malignant", "Sin efecto carcinogenico descrito"),
]

def evaluar(senales, farmaco, reaccion):
    fila = senales[(senales["drugname_norm"] == farmaco) &
                   (senales["pt_norm"] == reaccion)]
    if fila.empty:
        return {"casos": 0, "prr": None, "ror": None, "ic_inf": None,
                "chi2": None, "senal": False, "respaldo": False}
    f = fila.iloc[0]
    casos = int(f["casos"])
    return {
        "casos": casos,
        "prr": round(float(f["prr"]), 2),
        "ror": round(float(f["ror"]), 2),
        "ic_inf": round(float(f["ror_ic_inf"]), 2),
        "chi2": round(float(f["chi2"]), 1),
        "senal": bool(f["es_senal"]),
        "respaldo": casos >= MIN_CASOS,
    }

def main():
    senales = DeltaTable(f"{CURATED}/senales_prr_ror").to_pandas()
    # La columna "A" incorpora la correccion de Haldane-Anscombe, medio caso por
    # casilla, que se descuenta para recuperar el recuento real.
    senales["casos"] = (senales["a"] - 0.5).round().astype(int)

    print(f"Combinaciones evaluadas por el sistema: {len(senales):,}")
    print(f"Respaldo minimo exigido: {MIN_CASOS} casos")

    filas = []
    for tipo, lista, esperado in (("Positivo", POSITIVOS, True),
                                  ("Negativo", NEGATIVOS, False)):
        print()
        print("=")
        print(f"CONTROLES {tipo.upper()}S")
        print("=")
        for farmaco, reaccion, motivo in lista:
            r = evaluar(senales, farmaco, reaccion)
            detectada = r["senal"] and r["respaldo"]
            acierto = detectada == esperado
            filas.append({
                "tipo": tipo, "farmaco": farmaco, "reaccion": reaccion,
                "casos": r["casos"], "prr": r["prr"], "ror": r["ror"],
                "ror_ic_inf": r["ic_inf"], "chi2": r["chi2"],
                "detectada": detectada, "esperado": esperado,
                "acierto": acierto, "referencia": motivo,
            })
            marca = "OK " if acierto else "X  "
            prr = f"{r['prr']:>9.2f}" if r["prr"] is not None else "        -"
            print(f"{marca} {farmaco:<22} {reaccion:<28} "
                  f"casos={r['casos']:>6}  PRR={prr}  "
                  f"{'senal' if detectada else 'sin senal'}")

    tabla = pd.DataFrame(filas)
    pos = tabla[tabla["tipo"] == "Positivo"]
    neg = tabla[tabla["tipo"] == "Negativo"]

    print()
    print("=")
    print("RESULTADO")
    print("=")
    print(f"Sensibilidad:  {pos['acierto'].sum()}/{len(pos)}  "
          f"({pos['acierto'].sum() / len(pos) * 100:.0f} %)")
    print(f"Especificidad: {neg['acierto'].sum()}/{len(neg)}  "
          f"({neg['acierto'].sum() / len(neg) * 100:.0f} %)")

    fallos = tabla[~tabla["acierto"]]
    if len(fallos):
        print()
        print("Casos que no se comportan como se esperaba:")
        for _, f in fallos.iterrows():
            print(f"  {f['tipo']}: {f['farmaco']} - {f['reaccion']} "
                  f"(casos={f['casos']}, PRR={f['prr']})")

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    tabla.to_csv(SALIDA, index=False)
    print()
    print(f"Resultados guardados en {SALIDA}")


if __name__ == "__main__":
    main()








