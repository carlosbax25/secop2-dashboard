"""
ETL para Dashboard SECOP II.
Usa el dataset limpio (secop2_adjudicados_limpio.csv).
"""
import os
import pandas as pd

def ingest_and_process(data_path):
    """Lee el CSV limpio y retorna DataFrame Pandas listo."""
    print(f"  [Pandas] Leyendo: {data_path}")
    df = pd.read_csv(data_path, low_memory=False)
    print(f"  {len(df):,} registros listos.")
    return df
