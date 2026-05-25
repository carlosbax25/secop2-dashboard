"""
Dashboard Interactivo — Transparencia en la Contratación Pública Colombiana
Motor: PySpark (ingesta) + Dash/Plotly (visualización)

Pregunta analítica:
¿Cuánto dinero público fue adjudicado en procesos con baja competencia
y en qué modalidades, territorios o entidades prioritarias debería
concentrarse la veeduría ciudadana?

Ejecutar:  python app.py
Abrir:     http://127.0.0.1:8050
"""

import dash
from dash import dcc, html, Input, Output, State, callback, no_update, dash_table
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import os
import json as json_lib
import unicodedata
from spark_etl import ingest_and_process
from pages import build_storytelling, build_analisis_competitividad

# =============================================================================
# INGESTA CON SPARK
# =============================================================================
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'secop2_adjudicados_limpio.csv')
print("Procesando datos...")
df = ingest_and_process(DATA_PATH)
print("Datos listos.\n")

# =============================================================================
# KPIs
# =============================================================================
total_contratos = len(df)
presupuesto_total = df['valor_total_adjudicacion'].sum()
pct_sin_comp = df['baja_competencia'].mean() * 100

def fmt(v):
    if v >= 1e12: return f"${v/1e12:.1f} B"
    if v >= 1e9:  return f"${v/1e9:.1f} mil M"
    if v >= 1e6:  return f"${v/1e6:,.0f} M"
    return f"${v:,.0f}"

print(f"  {total_contratos:,} contratos | {fmt(presupuesto_total)} | Sin competencia: {pct_sin_comp:.0f}%")

# =============================================================================
# PALETA — ColorBrewer2.org (accesible para daltonismo)
# =============================================================================
AZUL_OSCURO = '#08519C'
AZUL_MEDIO = '#3182BD'
AZUL_CLARO = '#6BAED6'
AZUL_MUY_CLARO = '#BDD7E7'

CAT_CRITICO = '#D94701'    # Naranja oscuro: sin ofertas
CAT_ALERTA = '#FD8D3C'     # Naranja claro: 1 oferente
CAT_MEDIO = '#6BAED6'      # Azul claro: 2-5 oferentes
CAT_SEGURO = '#08519C'     # Azul oscuro: 6+ oferentes

RESALTADO = '#D94701'
NEUTRO = '#BDBDBD'

HEATMAP_SCALE = [[0,'#FFFFFF'],[0.25,'#EFF3FF'],[0.5,'#6BAED6'],[0.75,'#2171B5'],[1,'#08306B']]
TREEMAP_SCALE = [[0,'#FEE6CE'],[0.4,'#FDAE6B'],[0.7,'#D94801'],[1,'#7F2704']]

GRIS_OSCURO = '#212121'
GRIS_MEDIO = '#616161'
GRIS_CLARO = '#BDBDBD'
FONDO = '#FAFAFA'
BLANCO = '#FFFFFF'
ALERTA_FONDO = '#FBE9E7'

# =============================================================================
# VIZ 1 — SITUACIÓN: Mapa de burbujas Top 5 (Variables de Bertin: Tamaño + Valor/Tono azul)
# =============================================================================
GEOJSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'depto.json')

# Coordenadas centroides de departamentos colombianos
COORDS_DEPTOS = {
    'AMAZONAS': (-1.0, -71.9), 'ANTIOQUIA': (7.0, -75.5), 'ARAUCA': (7.0, -70.7),
    'ATLANTICO': (10.9, -75.0), 'BOLIVAR': (8.6, -75.1), 'BOYACA': (5.5, -73.4),
    'CALDAS': (5.3, -75.5), 'CAQUETA': (1.5, -75.6), 'CASANARE': (5.3, -71.3),
    'CAUCA': (2.5, -76.8), 'CESAR': (9.3, -73.5), 'CHOCO': (5.7, -76.6),
    'CORDOBA': (8.3, -75.8), 'CUNDINAMARCA': (5.0, -74.0), 'GUAINIA': (2.5, -69.0),
    'GUAVIARE': (2.5, -72.6), 'HUILA': (2.5, -75.5), 'LA GUAJIRA': (11.5, -72.9),
    'MAGDALENA': (10.4, -74.4), 'META': (3.5, -73.0), 'NARINO': (1.3, -77.9),
    'NORTE DE SANTANDER': (7.9, -72.5), 'PUTUMAYO': (0.5, -76.0),
    'QUINDIO': (4.5, -75.7), 'RISARALDA': (5.0, -75.7), 'SAN ANDRES': (12.5, -81.7),
    'SANTANDER': (7.0, -73.1), 'SUCRE': (9.3, -75.4), 'TOLIMA': (4.0, -75.2),
    'VALLE DEL CAUCA': (3.5, -76.5), 'VAUPES': (1.0, -70.2), 'VICHADA': (4.5, -69.5),
    'DISTRITO CAPITAL DE BOGOTA': (4.6, -74.1), 'BOGOTA': (4.6, -74.1),
}

def norm_dep(t):
    if not t: return ""
    return "".join(c for c in unicodedata.normalize("NFKD", str(t)) if not unicodedata.combining(c)).upper().strip()

dept = df.groupby('departamento_entidad').agg(
    ppto=('valor_total_adjudicacion', 'sum'),
    n=('valor_total_adjudicacion', 'count'),
).reset_index().sort_values('ppto', ascending=False)
total_ppto = df['valor_total_adjudicacion'].sum()
dept['pct'] = (dept['ppto'] / total_ppto * 100).round(1)

# Top 5
top5 = dept.head(5).copy()
pct_top5 = top5['pct'].sum()

# Asignar coordenadas
top5['dep_key'] = top5['departamento_entidad'].apply(norm_dep)
top5['lat'] = top5['dep_key'].apply(lambda x: next((v[0] for k, v in COORDS_DEPTOS.items() if k in x or x in k), None))
top5['lon'] = top5['dep_key'].apply(lambda x: next((v[1] for k, v in COORDS_DEPTOS.items() if k in x or x in k), None))
top5 = top5.dropna(subset=['lat', 'lon'])
top5['ppto_fmt'] = top5['ppto'].apply(fmt)

# Variable de Bertin: TAMAÑO (proporcional al presupuesto)
top5['size'] = (top5['ppto'] / top5['ppto'].max() * 45) + 12

fig1 = go.Figure()

# Capa base: contorno de Colombia con GeoJSON
with open(GEOJSON_PATH, encoding='utf-8') as f:
    geojson_data = json_lib.load(f)

# Burbujas — Bertin: Tamaño (magnitud) + Valor/Tono (intensidad azul secuencial)
fig1.add_trace(go.Scattermapbox(
    lat=top5['lat'], lon=top5['lon'],
    mode='markers+text',
    marker=dict(
        size=top5['size'],
        color=top5['ppto'],
        colorscale=[[0,'#BDD7E7'],[0.3,'#6BAED6'],[0.6,'#3182BD'],[1,'#08519C']],
        showscale=False,
        opacity=0.8,
        sizemode='diameter',
    ),
    text=top5['departamento_entidad'].str.title(),
    textposition='top center',
    textfont=dict(size=9, color=GRIS_OSCURO),
    customdata=np.column_stack([top5['ppto_fmt'], top5['pct'], top5['n']]),
    hovertemplate='<b>%{text}</b><br>Presupuesto: %{customdata[0]}<br>%{customdata[1]}% del total<br>%{customdata[2]:,} contratos<extra></extra>',
))

fig1.update_layout(
    title=dict(text=f'<b>Top 5 departamentos concentran el {pct_top5:.0f}% del presupuesto adjudicado</b>',
               font=dict(size=12, color=GRIS_OSCURO), x=0, y=0.97),
    mapbox=dict(
        style='carto-positron',
        center=dict(lat=5.5, lon=-74.0),
        zoom=4.3,
        layers=[dict(
            source=geojson_data, type='line',
            color='#BDBDBD', line=dict(width=0.5),
            below='traces',
        )]
    ),
    paper_bgcolor=BLANCO, margin=dict(l=0, r=0, t=30, b=0), height=420, showlegend=False,
)

# =============================================================================
# VIZ 2 — COMPLICACIÓN: Barras apiladas 100% por modalidad (3 categorías azul)
# =============================================================================
# Crear 3 rangos de competencia como en la infografía
df['rango_competencia'] = pd.cut(
    df['respuestas_al_procedimiento'].fillna(0).astype(float),
    bins=[-1, 1, 3, 9999],
    labels=['1. Nula (≤1 oferente)', '2. Baja (2-3 oferentes)', '3. Alta (4+ oferentes)']
)

# Top 10 modalidades por volumen — usar nombres originales del dataset
modalidades_top = df['modalidad_de_contratacion'].value_counts().head(10).index.tolist()
df_m = df[df['modalidad_de_contratacion'].isin(modalidades_top)].copy()

cross = pd.crosstab(df_m['modalidad_de_contratacion'], df_m['rango_competencia'], normalize='index') * 100
cross = cross.reset_index()

# Ordenar por % de nula competencia (mayor riesgo arriba)
nula_col = '1. Nula (≤1 oferente)'
if nula_col in cross.columns:
    cross = cross.sort_values(nula_col, ascending=True)

cats_viz2 = ['1. Nula (≤1 oferente)', '2. Baja (2-3 oferentes)', '3. Alta (4+ oferentes)']
colores_viz2 = ['#BDD7E7', '#3182BD', '#08519C']  # Azul claro, azul medio, azul oscuro

fig2 = go.Figure()
for i, cat in enumerate(cats_viz2):
    if cat in cross.columns:
        fig2.add_trace(go.Bar(
            name=cat, y=cross['modalidad_de_contratacion'], x=cross[cat],
            orientation='h', marker=dict(color=colores_viz2[i], line=dict(width=0)),
            hovertemplate=f'<b>%{{y}}</b><br>{cat}: %{{x:.1f}}%<extra></extra>',
        ))
fig2.update_layout(
    barmode='stack',
    xaxis=dict(title='Procesos adjudicados', showgrid=False, zeroline=False, range=[0, 100],
               tickfont=dict(size=9, color=GRIS_MEDIO)),
    yaxis=dict(title='modalidad contratación', showgrid=False, tickfont=dict(size=9, color=GRIS_OSCURO), automargin=True),
    plot_bgcolor=BLANCO, paper_bgcolor=BLANCO,
    margin=dict(l=0, r=15, t=10, b=35), height=400, bargap=0.25,
    legend=dict(orientation='h', yanchor='top', y=-0.12, xanchor='center', x=0.5,
                font=dict(size=9, color=GRIS_MEDIO), bgcolor='rgba(0,0,0,0)'),
)

# =============================================================================
# VIZ 3 — RESOLUCIÓN: Treemap proveedores baja competencia (azul secuencial)
# =============================================================================
df_baja = df[df['baja_competencia'] == 1].copy()
df_baja = df_baja[df_baja['nombre_del_proveedor'].notna()]
df_baja = df_baja[df_baja['nombre_del_proveedor'] != 'No Definido']
top_prov = df_baja.groupby('nombre_del_proveedor').agg(
    ppto=('valor_total_adjudicacion', 'sum'),
    n=('valor_total_adjudicacion', 'count')
).reset_index().sort_values('ppto', ascending=False).head(20)

def fmt_milm(v):
    """Formato mil M como en la infografía."""
    if v >= 1e9: return f"{v/1e9:,.0f} mil M"
    if v >= 1e6: return f"{v/1e6:,.0f} M"
    return f"${v:,.0f}"

top_prov['ppto_fmt'] = top_prov['ppto'].apply(fmt_milm)
total_baja = df_baja['valor_total_adjudicacion'].sum()
pct_top = (top_prov['ppto'].sum() / total_baja * 100) if total_baja > 0 else 0

# Treemap con padre "Proveedores" (como en la infografía)
labels = ['Proveedores'] + top_prov['nombre_del_proveedor'].tolist()
parents = [''] + ['Proveedores'] * len(top_prov)
values = [0] + top_prov['ppto'].tolist()
custom_fmt = [''] + top_prov['ppto_fmt'].tolist()

TREEMAP_SCALE_AZUL = [[0,'#EFF3FF'],[0.25,'#BDD7E7'],[0.5,'#6BAED6'],[0.75,'#3182BD'],[1,'#08519C']]

fig3 = go.Figure(go.Treemap(
    labels=labels, values=values, parents=parents,
    marker=dict(
        colors=[0] + top_prov['ppto'].tolist(),
        colorscale=TREEMAP_SCALE_AZUL,
        line=dict(width=1, color=BLANCO),
    ),
    texttemplate='<b>%{label}</b><br>%{customdata}',
    customdata=custom_fmt,
    hovertemplate='<b>%{label}</b><br>%{customdata}<extra></extra>',
    textfont=dict(size=10),
    insidetextfont=dict(color='#0f172a'),
    outsidetextfont=dict(color=GRIS_OSCURO),
    pathbar=dict(visible=True),
))
fig3.update_layout(
    paper_bgcolor=BLANCO, margin=dict(l=0, r=0, t=10, b=0), height=400,
)

# =============================================================================
# VIZ 4 — LLAMADO A LA ACCIÓN: Heatmap entidades vs departamentos
# =============================================================================
de = df.groupby(['departamento_entidad', 'entidad']).agg(
    procesos=('valor_total_adjudicacion', 'count'),
    ppto=('valor_total_adjudicacion', 'sum'),
    sin_comp=('baja_competencia', 'sum'),
).reset_index()
de['pct_sin'] = (de['sin_comp'] / de['procesos'] * 100).round(0)
de = de[de['procesos'] >= 5].copy()

top_depts = df.groupby('departamento_entidad')['valor_total_adjudicacion'].sum().nlargest(8).index.tolist()
rows = []
for d in top_depts:
    sub = de[de['departamento_entidad'] == d].nlargest(2, 'ppto')
    rows.append(sub)
hm = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

if not hm.empty:
    dept_corto = {'Distrito Capital de Bogotá': 'Bogotá D.C.', 'Distrito Capital De Bogotá': 'Bogotá D.C.',
                  'Valle del Cauca': 'Valle', 'Valle Del Cauca': 'Valle',
                  'Norte de Santander': 'N. Santander', 'Norte De Santander': 'N. Santander'}
    hm['dept'] = hm['departamento_entidad'].map(dept_corto).fillna(hm['departamento_entidad'])
    hm['ent_corta'] = hm['entidad'].str[:38]
    pivot = hm.pivot_table(index='ent_corta', columns='dept', values='pct_sin', aggfunc='mean').fillna(0)

    fig4 = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=HEATMAP_SCALE, zmin=0, zmax=100,
        hovertemplate='<b>%{y}</b><br>%{x}<br>Sin competencia: %{z:.0f}%<extra></extra>',
        colorbar=dict(title=dict(text='%', font=dict(size=9, color=GRIS_MEDIO)),
                      thickness=10, len=0.7, tickfont=dict(size=8)),
    ))
    fig4.update_layout(
        xaxis=dict(showgrid=False, tickfont=dict(size=8, color=GRIS_MEDIO), tickangle=-30),
        yaxis=dict(showgrid=False, tickfont=dict(size=7, color=GRIS_OSCURO), autorange='reversed'),
        plot_bgcolor=BLANCO, paper_bgcolor=BLANCO,
        margin=dict(l=0, r=5, t=10, b=5), height=370,
    )
else:
    fig4 = go.Figure()
    fig4.update_layout(paper_bgcolor=BLANCO, plot_bgcolor=BLANCO, height=370)

# =============================================================================
# LAYOUT
# =============================================================================
CARD = {'backgroundColor': BLANCO, 'borderRadius': '4px', 'padding': '16px 20px', 'border': '1px solid #E0E0E0'}
BADGE = lambda c: {'backgroundColor': c, 'color': 'white', 'borderRadius': '50%',
                   'width': '22px', 'height': '22px', 'display': 'inline-flex',
                   'alignItems': 'center', 'justifyContent': 'center', 'fontSize': '11px', 'fontWeight': '700'}
LABEL = {'fontSize': '10px', 'fontWeight': '600', 'letterSpacing': '1.5px', 'color': GRIS_MEDIO, 'textTransform': 'uppercase'}
SUBLABEL = {'fontSize': '10px', 'color': GRIS_MEDIO, 'fontStyle': 'italic'}

KPI_STYLE = lambda border_color=None, bg=BLANCO: {
    'flex': '1', 'padding': '10px 14px', 'backgroundColor': bg,
    'border': f'1px solid {border_color or "#E0E0E0"}', 'borderRadius': '4px',
    'cursor': 'pointer', 'transition': 'box-shadow 0.2s',
}

MODAL_OVERLAY = {
    'position': 'fixed', 'top': 0, 'left': 0, 'width': '100%', 'height': '100%',
    'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': 1000,
    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
}
MODAL_CONTENT = {
    'backgroundColor': BLANCO, 'borderRadius': '8px', 'padding': '24px',
    'maxWidth': '900px', 'width': '90%', 'maxHeight': '80vh', 'overflowY': 'auto',
    'boxShadow': '0 4px 20px rgba(0,0,0,0.15)',
}
MODAL_CLOSE = {
    'position': 'absolute', 'top': '12px', 'right': '16px',
    'fontSize': '20px', 'cursor': 'pointer', 'color': GRIS_MEDIO,
    'border': 'none', 'background': 'none', 'fontWeight': '700',
}

app = dash.Dash(__name__, title="SECOP II — Contratación Pública Colombia",
               suppress_callback_exceptions=True)
server = app.server

# Leer PDF path para iframe
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')

# ─── APP LAYOUT ───
app.layout = html.Div(style={'display': 'flex', 'minHeight': '100vh', 'fontFamily': "'Segoe UI', sans-serif"}, children=[

    # Store para página activa
    dcc.Store(id='active-page', data='dashboard'),

    # ─── SIDEBAR ───
    html.Div(id='sidebar', style={
        'width': '200px', 'minWidth': '200px', 'padding': '24px 16px',
        'backgroundColor': '#08306B', 'color': 'white',
        'display': 'flex', 'flexDirection': 'column', 'gap': '0',
        'position': 'sticky', 'top': 0, 'height': '100vh', 'overflowY': 'auto',
    }, children=[
        html.Div(style={'marginBottom': '24px'}, children=[
            html.H3("SECOP II", style={'margin': '0', 'fontSize': '15px', 'fontWeight': '800', 'color': 'white', 'letterSpacing': '-0.5px'}),
            html.P("VEEDURÍA CIUDADANA", style={'margin': '4px 0 0', 'fontSize': '9px', 'color': '#93C5FD', 'letterSpacing': '1.5px'}),
        ]),
        html.Div(style={'borderTop': '1px solid rgba(255,255,255,0.1)', 'paddingTop': '16px', 'flex': '1'}, children=[
            html.Div(id='nav-dashboard', n_clicks=0, children="📊  Dashboard"),
            html.Div(id='nav-storytelling', n_clicks=0, children="📖  Storytelling"),
            html.Div(id='nav-infografia', n_clicks=0, children="📈  Análisis Competitividad"),
            html.Div(id='nav-documento', n_clicks=0, children="📄  FASE 1 - Documento"),
        ]),
        html.Div(style={'borderTop': '1px solid rgba(255,255,255,0.1)', 'paddingTop': '12px', 'marginTop': 'auto'}, children=[
            html.P("Tecnológico Comfenalco", style={'fontSize': '9px', 'color': '#93C5FD', 'margin': '0'}),
            html.P("Proyecto Integrador · 2026", style={'fontSize': '9px', 'color': '#93C5FD', 'margin': '3px 0 0'}),
        ]),
    ]),

    # ─── CONTENIDO PRINCIPAL ───
    html.Div(id='page-content', style={
        'flex': '1', 'padding': '0 24px 40px', 'backgroundColor': FONDO,
        'overflowY': 'auto',
    }),
])

dashboard_content = html.Div(children=[
    # HEADER
    html.Div(style={'padding': '20px 0 12px', 'borderBottom': f'2px solid {AZUL_OSCURO}'}, children=[
        html.H1("Transparencia en la Contratación Pública Colombiana",
                style={'margin': '0', 'fontSize': '18px', 'fontWeight': '700', 'color': GRIS_OSCURO}),
        html.P("¿Cuánto dinero público fue adjudicado en procesos con baja competencia y en qué modalidades, territorios o entidades prioritarias debería concentrarse la veeduría ciudadana?",
               style={'margin': '3px 0 0', 'fontSize': '11px', 'color': GRIS_MEDIO}),
    ]),

    # KPIs
    html.Div(style={'display': 'flex', 'gap': '10px', 'margin': '14px 0'}, children=[
        html.Div(id='kpi-presupuesto', n_clicks=0, style=KPI_STYLE(), children=[
            html.P("Presupuesto Adjudicado", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
            html.P(fmt(presupuesto_total), style={'margin': '2px 0 0', 'fontSize': '16px', 'fontWeight': '700', 'color': AZUL_OSCURO}),
            html.P("▸ Clic para detalle", style={'margin': '2px 0 0', 'fontSize': '8px', 'color': GRIS_CLARO}),
        ]),
        html.Div(id='kpi-contratos', n_clicks=0, style=KPI_STYLE(), children=[
            html.P("Contratos Adjudicados", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
            html.P(f"{total_contratos:,}", style={'margin': '2px 0 0', 'fontSize': '16px', 'fontWeight': '700', 'color': GRIS_OSCURO}),
            html.P("▸ Clic para detalle", style={'margin': '2px 0 0', 'fontSize': '8px', 'color': GRIS_CLARO}),
        ]),
        html.Div(id='kpi-cobertura', n_clicks=0, style=KPI_STYLE(), children=[
            html.P("Cobertura", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
            html.P("32 Dptos + Bogotá D.C.",
                   style={'margin': '2px 0 0', 'fontSize': '14px', 'fontWeight': '700', 'color': GRIS_OSCURO}),
            html.P("▸ Clic para detalle", style={'margin': '2px 0 0', 'fontSize': '8px', 'color': GRIS_CLARO}),
        ]),
        html.Div(id='kpi-competencia', n_clicks=0, style=KPI_STYLE(RESALTADO, ALERTA_FONDO), children=[
            html.P("Sin Competencia", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
            html.P(f"{pct_sin_comp:.0f}%", style={'margin': '2px 0 0', 'fontSize': '16px', 'fontWeight': '700', 'color': RESALTADO}),
            html.P("▸ Clic para detalle", style={'margin': '2px 0 0', 'fontSize': '8px', 'color': RESALTADO}),
        ]),
    ]),

    # ─── VISUALIZACIONES (estilo cards con header azul) ───
    html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '20px', 'margin': '20px 0'}, children=[
        # VIZ 1
        html.Div(style={'background': BLANCO, 'borderRadius': '10px', 'overflow': 'hidden', 'border': '1px solid #e2e8f0', 'boxShadow': '0 4px 6px rgba(0,0,0,0.04)'}, children=[
            html.Div("1. Distribución Geográfica del Presupuesto", style={'padding': '12px 18px', 'fontWeight': '700', 'color': 'white', 'fontSize': '13px', 'background': '#1e3a8a'}),
            html.Div(style={'padding': '16px'}, children=[
                html.P("¿Cómo se distribuye geográficamente el presupuesto total contratado?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '12px', 'margin': '0 0 6px'}),
                html.P("El mapa dimensiona el tamaño del mercado de contratación pública a nivel departamental.", style={'fontSize': '11px', 'color': '#64748b', 'margin': '0 0 12px', 'lineHeight': '1.4'}),
                dcc.Graph(id='graph-situacion', figure=fig1, config={'displayModeBar': False}),
            ]),
        ]),
        # VIZ 2
        html.Div(style={'background': BLANCO, 'borderRadius': '10px', 'overflow': 'hidden', 'border': '1px solid #e2e8f0', 'boxShadow': '0 4px 6px rgba(0,0,0,0.04)'}, children=[
            html.Div("2. Modalidades y Nivel de Competencia", style={'padding': '12px 18px', 'fontWeight': '700', 'color': 'white', 'fontSize': '13px', 'background': '#1d4ed8'}),
            html.Div(style={'padding': '16px'}, children=[
                html.P("¿Qué modalidades de contratación presentan estructuralmente una menor cantidad de oferentes?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '12px', 'margin': '0 0 6px'}),
                html.P("Al estandarizar las barras al 100%, se compara visualmente la proporción interna de competencia (Baja vs Alta) entre modalidades. Evidencia que la Contratación Directa opera como una anomalía de pluralidad.", style={'fontSize': '11px', 'color': '#64748b', 'margin': '0 0 12px', 'lineHeight': '1.4'}),
                dcc.Graph(id='graph-complicacion', figure=fig2, config={'displayModeBar': False}),
            ]),
        ]),
        # VIZ 3
        html.Div(style={'background': BLANCO, 'borderRadius': '10px', 'overflow': 'hidden', 'border': '1px solid #e2e8f0', 'boxShadow': '0 4px 6px rgba(0,0,0,0.04)'}, children=[
            html.Div("3. Concentración de Proveedores", style={'padding': '12px 18px', 'fontWeight': '700', 'color': 'white', 'fontSize': '13px', 'background': '#2563eb'}),
            html.Div(style={'padding': '16px'}, children=[
                html.P("¿Cuáles proveedores absorben la mayor cantidad de dinero en escenarios de baja competencia?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '12px', 'margin': '0 0 6px'}),
                html.P("El tamaño de las áreas representa la magnitud del presupuesto adjudicado. Facilita la identificación inmediata de los principales contratistas en entornos sin pluralidad, priorizando su seguimiento.", style={'fontSize': '11px', 'color': '#64748b', 'margin': '0 0 12px', 'lineHeight': '1.4'}),
                dcc.Graph(id='graph-resolucion', figure=fig3, config={'displayModeBar': False}),
            ]),
        ]),
        # VIZ 4
        html.Div(style={'background': BLANCO, 'borderRadius': '10px', 'overflow': 'hidden', 'border': '1px solid #e2e8f0', 'boxShadow': '0 4px 6px rgba(0,0,0,0.04)'}, children=[
            html.Div("4. Entidades Estatales Prioritarias", style={'padding': '12px 18px', 'fontWeight': '700', 'color': 'white', 'fontSize': '13px', 'background': '#334155'}),
            html.Div(style={'padding': '16px'}, children=[
                html.P("¿Qué entidades concentran los mayores montos bajo alertas de baja competencia?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '12px', 'margin': '0 0 6px'}),
                html.P("El ordenamiento descendente actúa como una lista de prioridades o \"ruta de auditoría\" directa para el control social, filtrando el ruido visual y enfocando la atención en las instituciones más críticas.", style={'fontSize': '11px', 'color': '#64748b', 'margin': '0 0 12px', 'lineHeight': '1.4'}),
                dcc.Graph(id='graph-accion', figure=fig4, config={'displayModeBar': False}),
            ]),
        ]),
    ]),

    # FOOTER
    html.Div(style={'borderTop': '1px solid #E0E0E0', 'padding': '10px 0', 'marginTop': '16px'}, children=[
        html.P("Fuente: SECOP II · Agencia Nacional de Contratación Pública · datos.gov.co · API OData",
               style={'margin': '0', 'fontSize': '9px', 'color': GRIS_CLARO, 'textAlign': 'center'}),
        html.P("Proyecto Integrador · Visualización de Datos Masivos · Tecnológico Comfenalco · 2026",
               style={'margin': '2px 0 0', 'fontSize': '9px', 'color': GRIS_CLARO, 'textAlign': 'center'}),
    ]),

    # MODAL CONTAINER
    html.Div(id='modal-container', style={'display': 'none'}),
])

# =============================================================================
# CALLBACKS — Navegación sidebar (estilo activo + contenido)
# =============================================================================
@app.callback(
    Output('page-content', 'children'),
    Output('nav-dashboard', 'style'),
    Output('nav-storytelling', 'style'),
    Output('nav-infografia', 'style'),
    Output('nav-documento', 'style'),
    Input('nav-dashboard', 'n_clicks'),
    Input('nav-storytelling', 'n_clicks'),
    Input('nav-infografia', 'n_clicks'),
    Input('nav-documento', 'n_clicks'),
)
def navigate(c1, c2, c3, c4):
    ctx = dash.callback_context
    
    # Estilos de nav items
    base = {'display': 'block', 'padding': '10px 14px', 'margin': '4px 0',
            'borderRadius': '6px', 'color': '#93C5FD', 'fontSize': '12px',
            'cursor': 'pointer', 'transition': 'all 0.2s'}
    active = {**base, 'backgroundColor': 'rgba(255,255,255,0.12)', 'color': 'white', 'fontWeight': '600'}
    
    # Default: dashboard
    if not ctx.triggered or ctx.triggered[0]['prop_id'] == 'nav-dashboard.n_clicks':
        return dashboard_content, active, base, base, base
    
    trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger == 'nav-storytelling':
        content = build_storytelling(df)
        return content, base, active, base, base
    
    elif trigger == 'nav-infografia':
        content = build_analisis_competitividad(df, fig1, fig2, fig3, fig4)
        return content, base, base, active, base
    
    elif trigger == 'nav-documento':
        content = html.Div(style={'padding': '20px 0'}, children=[
            html.Iframe(src='/assets/fase1.pdf', style={
                'width': '100%', 'height': '88vh', 'border': 'none',
                'borderRadius': '8px', 'boxShadow': '0 1px 3px rgba(0,0,0,0.08)',
            }),
        ])
        return content, base, base, base, active
    
    return dashboard_content, active, base, base, base

# =============================================================================
# CALLBACKS — Modales dinámicos
# =============================================================================
def crear_modal(titulo, contenido):
    return html.Div(style=MODAL_OVERLAY, children=[
        html.Div(style={**MODAL_CONTENT, 'position': 'relative'}, children=[
            html.Button("✕", id='modal-close', style=MODAL_CLOSE),
            html.H3(titulo, style={'margin': '0 0 12px', 'fontSize': '15px', 'color': GRIS_OSCURO}),
            contenido,
        ])
    ])

def tabla_dash(dataframe, max_rows=15):
    return dash_table.DataTable(
        data=dataframe.head(max_rows).to_dict('records'),
        columns=[{'name': c, 'id': c} for c in dataframe.columns],
        style_table={'overflowX': 'auto'},
        style_header={'backgroundColor': FONDO, 'fontWeight': '600', 'fontSize': '10px',
                      'color': GRIS_OSCURO, 'border': 'none', 'borderBottom': f'2px solid {GRIS_CLARO}'},
        style_cell={'fontSize': '10px', 'padding': '6px 10px', 'border': 'none',
                    'borderBottom': '1px solid #EEEEEE', 'textAlign': 'left',
                    'maxWidth': '200px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#F9F9F9'}],
    )

@app.callback(
    Output('modal-container', 'children'),
    Output('modal-container', 'style'),
    Input('kpi-presupuesto', 'n_clicks'),
    Input('kpi-contratos', 'n_clicks'),
    Input('kpi-cobertura', 'n_clicks'),
    Input('kpi-competencia', 'n_clicks'),
    Input('graph-situacion', 'clickData'),
    Input('graph-complicacion', 'clickData'),
    Input('graph-resolucion', 'clickData'),
    Input('graph-accion', 'clickData'),
    Input('modal-container', 'n_clicks'),
    prevent_initial_call=True,
)
def manejar_modales(click_ppto, click_cont, click_cob, click_comp,
                    click_g1, click_g2, click_g3, click_g4, click_overlay):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update, {'display': 'none'}

    trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger == 'modal-container':
        return [], {'display': 'none'}

    # KPI Presupuesto
    if trigger == 'kpi-presupuesto':
        data = df.groupby('departamento_entidad').agg(
            Presupuesto=('valor_total_adjudicacion', 'sum'),
            Contratos=('valor_total_adjudicacion', 'count'),
        ).reset_index().sort_values('Presupuesto', ascending=False)
        data['Presupuesto'] = data['Presupuesto'].apply(fmt)
        data.columns = ['Departamento', 'Presupuesto', 'Contratos']
        return crear_modal("Presupuesto adjudicado por departamento", tabla_dash(data, 20)), {'display': 'block'}

    # KPI Contratos
    if trigger == 'kpi-contratos':
        data = df.groupby('modalidad_de_contratacion').agg(
            Contratos=('valor_total_adjudicacion', 'count'),
            Presupuesto=('valor_total_adjudicacion', 'sum'),
        ).reset_index().sort_values('Contratos', ascending=False)
        data['Presupuesto'] = data['Presupuesto'].apply(fmt)
        data.columns = ['Modalidad', 'Contratos', 'Presupuesto']
        return crear_modal("Contratos adjudicados por modalidad", tabla_dash(data)), {'display': 'block'}

    # KPI Cobertura
    if trigger == 'kpi-cobertura':
        data = df.groupby('departamento_entidad').agg(
            Contratos=('valor_total_adjudicacion', 'count'),
            Entidades=('entidad', 'nunique'),
            Proveedores=('nombre_del_proveedor', 'nunique'),
        ).reset_index().sort_values('Contratos', ascending=False)
        data.columns = ['Departamento', 'Contratos', 'Entidades', 'Proveedores']
        return crear_modal("Cobertura territorial — Detalle por departamento", tabla_dash(data, 33)), {'display': 'block'}

    # KPI Sin Competencia
    if trigger == 'kpi-competencia':
        data = df[df['baja_competencia'] == 1].groupby('modalidad_de_contratacion').agg(
            Contratos=('valor_total_adjudicacion', 'count'),
            Presupuesto=('valor_total_adjudicacion', 'sum'),
        ).reset_index().sort_values('Presupuesto', ascending=False)
        data['Presupuesto'] = data['Presupuesto'].apply(fmt)
        data.columns = ['Modalidad', 'Contratos sin competencia', 'Presupuesto']
        return crear_modal("Contratos adjudicados SIN competencia (0-1 oferentes)", tabla_dash(data)), {'display': 'block'}

    # Clic en Viz 1 (departamento)
    if trigger == 'graph-situacion' and click_g1:
        point = click_g1['points'][0]
        depto = point.get('text', '')
        if not depto:
            depto = point.get('hovertext', '')
        data = df[df['departamento_entidad'].str.lower() == depto.lower()]
        if data.empty:
            data = df[df['departamento_entidad'].str.contains(depto[:10], case=False, na=False)]
        if not data.empty:
            depto_name = data['departamento_entidad'].iloc[0]
            tabla = data[
                ['entidad', 'nombre_del_proveedor', 'modalidad_de_contratacion', 'valor_total_adjudicacion', 'respuestas_al_procedimiento']
            ].sort_values('valor_total_adjudicacion', ascending=False).head(20).copy()
            tabla['valor_total_adjudicacion'] = tabla['valor_total_adjudicacion'].apply(fmt)
            tabla.columns = ['Entidad', 'Proveedor', 'Modalidad', 'Valor', 'Oferentes']
            return crear_modal(f"Top 20 contratos en {depto_name}", tabla_dash(tabla, 20)), {'display': 'block'}

    # Clic en Viz 2 (modalidad)
    if trigger == 'graph-complicacion' and click_g2:
        modalidad = click_g2['points'][0]['y']
        data_mod = df[df['modalidad_de_contratacion'] == modalidad]
        resumen = data_mod.groupby('rango_competencia').agg(
            Contratos=('valor_total_adjudicacion', 'count'),
            Presupuesto=('valor_total_adjudicacion', 'sum'),
        ).reset_index()
        resumen['Presupuesto'] = resumen['Presupuesto'].apply(fmt)
        resumen.columns = ['Rango Oferentes', 'Contratos', 'Presupuesto']
        return crear_modal(f"Detalle de competencia — {modalidad}", tabla_dash(resumen)), {'display': 'block'}

    # Clic en Viz 3 (treemap/proveedor)
    if trigger == 'graph-resolucion' and click_g3:
        label = click_g3['points'][0]['label']
        prov_match = df_baja[df_baja['nombre_del_proveedor'] == label]
        if prov_match.empty:
            prov_match = df_baja[df_baja['nombre_del_proveedor'].str.contains(label[:20], case=False, na=False)]
        data = prov_match[
            ['entidad', 'departamento_entidad', 'modalidad_de_contratacion', 'valor_total_adjudicacion']
        ].sort_values('valor_total_adjudicacion', ascending=False).head(15).copy()
        data['valor_total_adjudicacion'] = data['valor_total_adjudicacion'].apply(fmt)
        data.columns = ['Entidad', 'Departamento', 'Modalidad', 'Valor']
        return crear_modal(f"Contratos de: {label[:50]}", tabla_dash(data, 15)), {'display': 'block'}

    # Clic en Viz 4 (heatmap)
    if trigger == 'graph-accion' and click_g4:
        entidad_corta = click_g4['points'][0]['y']
        ent_match = df[df['entidad'].str[:38] == entidad_corta]
        if not ent_match.empty:
            total = len(ent_match)
            sin_comp = ent_match['baja_competencia'].sum()
            pct = sin_comp / total * 100 if total > 0 else 0
            data = ent_match[
                ['nombre_del_proveedor', 'modalidad_de_contratacion', 'valor_total_adjudicacion', 'respuestas_al_procedimiento']
            ].sort_values('respuestas_al_procedimiento', ascending=True).head(20).copy()
            data['valor_total_adjudicacion'] = data['valor_total_adjudicacion'].apply(fmt)
            data.columns = ['Proveedor', 'Modalidad', 'Valor', 'Oferentes']
            resumen = html.Div(style={'marginBottom': '12px', 'padding': '10px', 'backgroundColor': '#F5F5F5', 'borderRadius': '4px'}, children=[
                html.P(f"Total contratos: {total} | Sin competencia: {sin_comp} ({pct:.0f}%) | Presupuesto: {fmt(ent_match['valor_total_adjudicacion'].sum())}",
                       style={'margin': '0', 'fontSize': '11px', 'color': GRIS_OSCURO}),
            ])
            return crear_modal(f"Detalle: {ent_match['entidad'].iloc[0][:50]}", html.Div([resumen, tabla_dash(data, 20)])), {'display': 'block'}

    return [], {'display': 'none'}

# =============================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    print(f"\n  Dashboard SECOP II — http://127.0.0.1:{port}\n")
    app.run(debug=False, host='0.0.0.0', port=port)
