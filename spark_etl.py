"""
ETL para Dashboard SECOP II.
- LOCAL: Usa PySpark para ingesta y procesamiento distribuido.
- RENDER: Usa Pandas para leer el parquet ya procesado por Spark.

La variable de entorno RENDER=true activa el modo Pandas.
"""
import os
import pandas as pd

RENDER_MODE = os.environ.get('RENDER', 'false').lower() == 'true'


def ingest_and_process(parquet_path):
    """
    Lee el parquet y retorna un DataFrame Pandas listo para visualización.
    En modo Render usa Pandas directo. En local usa PySpark.
    """
    if RENDER_MODE:
        print("  [Pandas] Modo Render — leyendo CSV directo...")
        df = pd.read_csv(parquet_path.replace('.parquet', '.csv'), low_memory=False)
    else:
        print("  [Spark] Modo local — procesamiento distribuido...")
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
        from pyspark.sql.types import DoubleType, IntegerType

        os.environ["JAVA_HOME"] = r"C:\Program Files\Java\jre1.8.0_481"

        spark = SparkSession.builder \
            .appName("VeeduriaCiudadana_SECOP2") \
            .config("spark.driver.memory", "4g") \
            .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
            .config("spark.sql.shuffle.partitions", "8") \
            .getOrCreate()
        spark.sparkContext.setLogLevel("WARN")

        sdf = spark.read.parquet(parquet_path)
        sdf = sdf.withColumn("valor_del_contrato", F.col("valor_del_contrato").cast(DoubleType()))
        sdf = sdf.withColumn("numero_de_oferentes", F.col("numero_de_oferentes").cast(DoubleType()))
        sdf = sdf.withColumn("anio", F.col("anio").cast(IntegerType()))
        sdf = sdf.fillna({"valor_del_contrato": 0.0, "numero_de_oferentes": 0.0, "anio": 0})
        str_cols = ["departamento_entidad", "modalidad_de_contratacion",
                    "proveedor_adjudicado", "nombre_entidad"]
        sdf = sdf.fillna("No Definido", subset=str_cols)
        sdf = sdf.filter(F.col("valor_del_contrato") < 1e13)
        sdf = sdf.filter(F.col("valor_del_contrato") > 0)

        print("  [Spark] Convirtiendo a Pandas...")
        df = sdf.toPandas()

    # Transformaciones comunes (Pandas)
    df['valor_del_contrato'] = pd.to_numeric(df['valor_del_contrato'], errors='coerce').fillna(0)
    df['numero_de_oferentes'] = pd.to_numeric(df['numero_de_oferentes'], errors='coerce').fillna(0)

    # Flag baja competencia
    df['baja_competencia'] = (
        (df['numero_de_oferentes'] <= 1) |
        (df['modalidad_de_contratacion'].str.contains('directa', case=False, na=False))
    ).astype(int)

    # Rango de oferentes
    df['rango_oferentes'] = pd.cut(
        df['numero_de_oferentes'],
        bins=[-1, 0, 1, 5, 9999],
        labels=['Sin ofertas', '1 oferente', '2-5 oferentes', '6+ oferentes']
    )

    # Modalidad corta
    def modalidad_corta(m):
        m = str(m).lower()
        if 'directa' in m: return 'Contratación Directa'
        if 'mínima' in m or 'minima' in m: return 'Mínima Cuantía'
        if 'menor' in m: return 'Selección Abreviada MC'
        if 'licitación' in m or 'licitacion' in m: return 'Licitación Pública'
        if 'concurso' in m: return 'Concurso de Méritos'
        if 'subasta' in m: return 'Subasta Inversa'
        return str(m).title()[:30]

    df['modalidad_corta'] = df['modalidad_de_contratacion'].apply(modalidad_corta)

    # Filtro cordura
    df = df[df['valor_del_contrato'] > 0].copy()
    df = df[df['valor_del_contrato'] < 1e13].copy()

    print(f"  {len(df):,} registros listos.")
    return df
