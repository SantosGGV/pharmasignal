import os
import argostranslate.translate as tr
import pandas as pd
from deltalake import DeltaTable, write_deltalake

CURATED = os.path.expanduser("~/pharmasignal/data/curated")
FUENTES = [("reac_curado", "pt_norm"), ("indi_curado", "indi_pt_norm")]

terminos = set()
for tabla, col in FUENTES:
    ruta = f"{CURATED}/{tabla}"
    if not os.path.isdir(ruta):
        print(f"AVISO: falta {tabla}"); continue
    s = DeltaTable(ruta).to_pandas(columns=[col])[col].dropna().astype(str)
    terminos |= set(s.str.lower().unique())

terminos = sorted(terminos)
print(f"Traduciendo {len(terminos):,} términos EN→ES…")
filas = [{"term_en": x, "term_es": tr.translate(x, "en", "es")} for x in terminos]
write_deltalake(f"{CURATED}/trad_terminos", pd.DataFrame(filas), mode="overwrite")
print("Guardado en curated/trad_terminos")