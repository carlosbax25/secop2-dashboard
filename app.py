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

# =============================================================================
# INGESTA CON SPARK
# =============================================================================
PARQUET_PATH = os.path.join(os.path.dirname(__file__), 'data', 'secop_completo.parquet')
print("Procesando datos...")
df = ingest_and_process(PARQUET_PATH)
print("Datos listos.\n")

# =============================================================================
# KPIs
# =============================================================================
total_contratos = len(df)
presupuesto_total = df['valor_del_contrato'].sum()
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
    ppto=('valor_del_contrato', 'sum'),
    n=('valor_del_contrato', 'count'),
).reset_index().sort_values('ppto', ascending=False)
total_ppto = df['valor_del_contrato'].sum()
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
# VIZ 2 — COMPLICACIÓN: Barras apiladas 100% por modalidad
# =============================================================================
modalidades_top = df['modalidad_corta'].value_counts().head(6).index.tolist()
df_m = df[df['modalidad_corta'].isin(modalidades_top)].copy()
cross = pd.crosstab(df_m['modalidad_corta'], df_m['rango_oferentes'], normalize='index') * 100
cross = cross.reset_index()

sin_comp_cols = [c for c in ['Sin ofertas', '1 oferente'] if c in cross.columns]
cross['_riesgo'] = cross[sin_comp_cols].sum(axis=1)
cross = cross.sort_values('_riesgo', ascending=True)
cross = cross.drop(columns=['_riesgo'])

cats = ['Sin ofertas', '1 oferente', '2-5 oferentes', '6+ oferentes']
colores_azul = ['#08306B', '#08519C', '#6BAED6', '#BDD7E7']  # Azul secuencial: oscuro a claro

fig2 = go.Figure()
for i, cat in enumerate(cats):
    if cat in cross.columns:
        fig2.add_trace(go.Bar(
            name=cat, y=cross['modalidad_corta'], x=cross[cat],
            orientation='h', marker=dict(color=colores_azul[i], line=dict(width=0)),
            hovertemplate=f'<b>%{{y}}</b><br>{cat}: %{{x:.1f}}%<extra></extra>',
        ))
fig2.update_layout(
    barmode='stack',
    title=dict(text='<b>Contratación directa adjudica sin competencia en la mayoría de casos</b>',
               font=dict(size=12, color=GRIS_OSCURO), x=0, y=0.97),
    xaxis=dict(title=None, showgrid=False, zeroline=False, range=[0, 100],
               tickfont=dict(size=9, color=GRIS_MEDIO), ticksuffix='%'),
    yaxis=dict(showgrid=False, tickfont=dict(size=9, color=GRIS_OSCURO)),
    plot_bgcolor=BLANCO, paper_bgcolor=BLANCO,
    margin=dict(l=0, r=15, t=30, b=35), height=370, bargap=0.25,
    legend=dict(orientation='h', yanchor='top', y=-0.08, xanchor='center', x=0.5,
                font=dict(size=9, color=GRIS_MEDIO), bgcolor='rgba(0,0,0,0)'),
)

# =============================================================================
# VIZ 3 — RESOLUCIÓN: Treemap proveedores baja competencia
# =============================================================================
df_baja = df[df['baja_competencia'] == 1].copy()
top_prov = df_baja.groupby('proveedor_adjudicado').agg(
    ppto=('valor_del_contrato', 'sum'),
    n=('valor_del_contrato', 'count')
).reset_index().sort_values('ppto', ascending=False).head(10)
top_prov['nombre_corto'] = top_prov['proveedor_adjudicado'].str[:30]
top_prov['ppto_fmt'] = top_prov['ppto'].apply(fmt)
total_baja = df_baja['valor_del_contrato'].sum()
pct_top10 = (top_prov['ppto'].sum() / total_baja * 100) if total_baja > 0 else 0

TREEMAP_SCALE_AZUL = [[0,'#EFF3FF'],[0.3,'#BDD7E7'],[0.5,'#6BAED6'],[0.75,'#3182BD'],[1,'#08306B']]

fig3 = go.Figure(go.Treemap(
    labels=top_prov['nombre_corto'], values=top_prov['ppto'],
    parents=[''] * len(top_prov),
    marker=dict(colors=top_prov['ppto'],
                colorscale=TREEMAP_SCALE_AZUL,
                line=dict(width=1, color=BLANCO)),
    texttemplate='<b>%{label}</b><br>%{customdata[0]}<br>%{customdata[1]} contratos',
    customdata=top_prov[['ppto_fmt', 'n']].values,
    hovertemplate='<b>%{label}</b><br>%{customdata[0]}<br>%{customdata[1]} contratos<extra></extra>',
    textfont=dict(size=9),
    insidetextfont=dict(color='white'),
    outsidetextfont=dict(color=GRIS_OSCURO),
))
fig3.update_layout(
    title=dict(text=f'<b>10 contratistas concentran el {pct_top10:.0f}% del gasto sin competencia</b>',
               font=dict(size=12, color=GRIS_OSCURO), x=0, y=0.97),
    paper_bgcolor=BLANCO, margin=dict(l=0, r=0, t=30, b=0), height=370,
)

# =============================================================================
# VIZ 4 — LLAMADO A LA ACCIÓN: Heatmap entidades vs departamentos
# =============================================================================
de = df.groupby(['departamento_entidad', 'nombre_entidad']).agg(
    procesos=('valor_del_contrato', 'count'),
    ppto=('valor_del_contrato', 'sum'),
    sin_comp=('baja_competencia', 'sum'),
).reset_index()
de['pct_sin'] = (de['sin_comp'] / de['procesos'] * 100).round(0)
de = de[de['procesos'] >= 5].copy()

top_depts = df.groupby('departamento_entidad')['valor_del_contrato'].sum().nlargest(8).index.tolist()
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
    hm['ent_corta'] = hm['nombre_entidad'].str[:38]
    pivot = hm.pivot_table(index='ent_corta', columns='dept', values='pct_sin', aggfunc='mean').fillna(0)

    fig4 = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=HEATMAP_SCALE, zmin=0, zmax=100,
        hovertemplate='<b>%{y}</b><br>%{x}<br>Sin competencia: %{z:.0f}%<extra></extra>',
        colorbar=dict(title=dict(text='%', font=dict(size=9, color=GRIS_MEDIO)),
                      thickness=10, len=0.7, tickfont=dict(size=8)),
    ))
    fig4.update_layout(
        title=dict(text='<b>Alerta: entidades con mayor concentración de adjudicaciones sin competencia</b>',
                   font=dict(size=12, color=GRIS_OSCURO), x=0, y=0.97),
        xaxis=dict(showgrid=False, tickfont=dict(size=8, color=GRIS_MEDIO), tickangle=-30),
        yaxis=dict(showgrid=False, tickfont=dict(size=7, color=GRIS_OSCURO), autorange='reversed'),
        plot_bgcolor=BLANCO, paper_bgcolor=BLANCO,
        margin=dict(l=0, r=5, t=30, b=5), height=370,
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

app.layout = html.Div(style={
    'backgroundColor': FONDO, 'fontFamily': "'Segoe UI', sans-serif",
    'maxWidth': '1200px', 'margin': '0 auto', 'padding': '0 24px 40px',
}, children=[

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
            html.P(f"{df['departamento_entidad'].nunique()} Dptos + Bogotá D.C.",
                   style={'margin': '2px 0 0', 'fontSize': '14px', 'fontWeight': '700', 'color': GRIS_OSCURO}),
            html.P("▸ Clic para detalle", style={'margin': '2px 0 0', 'fontSize': '8px', 'color': GRIS_CLARO}),
        ]),
        html.Div(id='kpi-competencia', n_clicks=0, style=KPI_STYLE(RESALTADO, ALERTA_FONDO), children=[
            html.P("Sin Competencia", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
            html.P(f"{pct_sin_comp:.0f}%", style={'margin': '2px 0 0', 'fontSize': '16px', 'fontWeight': '700', 'color': RESALTADO}),
            html.P("▸ Clic para detalle", style={'margin': '2px 0 0', 'fontSize': '8px', 'color': RESALTADO}),
        ]),
    ]),

    # VIZ 1
    html.Div(style={'margin': '18px 0'}, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '4px'}, children=[
            html.Span("1", style=BADGE(AZUL_OSCURO)),
            html.Span("SITUACIÓN", style=LABEL),
            html.Span("— Distribución territorial del presupuesto", style=SUBLABEL),
        ]),
        html.Div(style=CARD, children=[dcc.Graph(id='graph-situacion', figure=fig1, config={'displayModeBar': False})]),
    ]),

    # VIZ 2
    html.Div(style={'margin': '18px 0'}, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '4px'}, children=[
            html.Span("2", style=BADGE(CAT_ALERTA)),
            html.Span("COMPLICACIÓN", style=LABEL),
            html.Span("— Competitividad por modalidad contractual", style=SUBLABEL),
        ]),
        html.Div(style=CARD, children=[dcc.Graph(id='graph-complicacion', figure=fig2, config={'displayModeBar': False})]),
    ]),

    # VIZ 3 + VIZ 4
    html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '14px', 'margin': '18px 0'}, children=[
        html.Div(children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '4px'}, children=[
                html.Span("3", style=BADGE(RESALTADO)),
                html.Span("RESOLUCIÓN", style=LABEL),
            ]),
            html.Div(style=CARD, children=[dcc.Graph(id='graph-resolucion', figure=fig3, config={'displayModeBar': False})]),
        ]),
        html.Div(children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '4px'}, children=[
                html.Span("4", style=BADGE('#08306B')),
                html.Span("LLAMADO A LA ACCIÓN", style=LABEL),
            ]),
            html.Div(style=CARD, children=[dcc.Graph(id='graph-accion', figure=fig4, config={'displayModeBar': False})]),
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
            Presupuesto=('valor_del_contrato', 'sum'),
            Contratos=('valor_del_contrato', 'count'),
        ).reset_index().sort_values('Presupuesto', ascending=False)
        data['Presupuesto'] = data['Presupuesto'].apply(fmt)
        data.columns = ['Departamento', 'Presupuesto', 'Contratos']
        return crear_modal("Presupuesto adjudicado por departamento", tabla_dash(data, 20)), {'display': 'block'}

    # KPI Contratos
    if trigger == 'kpi-contratos':
        data = df.groupby('modalidad_corta').agg(
            Contratos=('valor_del_contrato', 'count'),
            Presupuesto=('valor_del_contrato', 'sum'),
        ).reset_index().sort_values('Contratos', ascending=False)
        data['Presupuesto'] = data['Presupuesto'].apply(fmt)
        data.columns = ['Modalidad', 'Contratos', 'Presupuesto']
        return crear_modal("Contratos adjudicados por modalidad", tabla_dash(data)), {'display': 'block'}

    # KPI Cobertura
    if trigger == 'kpi-cobertura':
        data = df.groupby('departamento_entidad').agg(
            Contratos=('valor_del_contrato', 'count'),
            Entidades=('nombre_entidad', 'nunique'),
            Proveedores=('proveedor_adjudicado', 'nunique'),
        ).reset_index().sort_values('Contratos', ascending=False)
        data.columns = ['Departamento', 'Contratos', 'Entidades', 'Proveedores']
        return crear_modal("Cobertura territorial — Detalle por departamento", tabla_dash(data, 33)), {'display': 'block'}

    # KPI Sin Competencia
    if trigger == 'kpi-competencia':
        data = df[df['baja_competencia'] == 1].groupby('modalidad_corta').agg(
            Contratos=('valor_del_contrato', 'count'),
            Presupuesto=('valor_del_contrato', 'sum'),
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
        # Buscar en el dataframe (el texto viene en Title Case)
        data = df[df['departamento_entidad'].str.lower() == depto.lower()]
        if data.empty:
            data = df[df['departamento_entidad'].str.contains(depto[:10], case=False, na=False)]
        if not data.empty:
            depto_name = data['departamento_entidad'].iloc[0]
            tabla = data[
                ['nombre_entidad', 'proveedor_adjudicado', 'modalidad_corta', 'valor_del_contrato', 'numero_de_oferentes']
            ].sort_values('valor_del_contrato', ascending=False).head(20).copy()
            tabla['valor_del_contrato'] = tabla['valor_del_contrato'].apply(fmt)
            tabla.columns = ['Entidad', 'Proveedor', 'Modalidad', 'Valor', 'Oferentes']
            return crear_modal(f"Top 20 contratos en {depto_name}", tabla_dash(tabla, 20)), {'display': 'block'}

    # Clic en Viz 2 (modalidad)
    if trigger == 'graph-complicacion' and click_g2:
        modalidad = click_g2['points'][0]['y']
        data_mod = df[df['modalidad_corta'] == modalidad]
        resumen = data_mod.groupby('rango_oferentes').agg(
            Contratos=('valor_del_contrato', 'count'),
            Presupuesto=('valor_del_contrato', 'sum'),
        ).reset_index()
        resumen['Presupuesto'] = resumen['Presupuesto'].apply(fmt)
        resumen.columns = ['Rango Oferentes', 'Contratos', 'Presupuesto']
        return crear_modal(f"Detalle de competencia — {modalidad}", tabla_dash(resumen)), {'display': 'block'}

    # Clic en Viz 3 (treemap/proveedor)
    if trigger == 'graph-resolucion' and click_g3:
        label = click_g3['points'][0]['label']
        prov_match = df_baja[df_baja['proveedor_adjudicado'].str[:30] == label]
        if prov_match.empty:
            prov_match = df_baja[df_baja['proveedor_adjudicado'].str.contains(label[:15], case=False, na=False)]
        data = prov_match[
            ['nombre_entidad', 'departamento_entidad', 'modalidad_corta', 'valor_del_contrato']
        ].sort_values('valor_del_contrato', ascending=False).head(15).copy()
        data['valor_del_contrato'] = data['valor_del_contrato'].apply(fmt)
        data.columns = ['Entidad', 'Departamento', 'Modalidad', 'Valor']
        return crear_modal(f"Contratos de: {label}", tabla_dash(data, 15)), {'display': 'block'}

    # Clic en Viz 4 (heatmap)
    if trigger == 'graph-accion' and click_g4:
        entidad_corta = click_g4['points'][0]['y']
        ent_match = df[df['nombre_entidad'].str[:38] == entidad_corta]
        if not ent_match.empty:
            total = len(ent_match)
            sin_comp = ent_match['baja_competencia'].sum()
            pct = sin_comp / total * 100 if total > 0 else 0
            data = ent_match[
                ['proveedor_adjudicado', 'modalidad_corta', 'valor_del_contrato', 'numero_de_oferentes']
            ].sort_values('numero_de_oferentes', ascending=True).head(20).copy()
            data['valor_del_contrato'] = data['valor_del_contrato'].apply(fmt)
            data.columns = ['Proveedor', 'Modalidad', 'Valor', 'Oferentes']
            resumen = html.Div(style={'marginBottom': '12px', 'padding': '10px', 'backgroundColor': '#F5F5F5', 'borderRadius': '4px'}, children=[
                html.P(f"Total contratos: {total} | Sin competencia: {sin_comp} ({pct:.0f}%) | Presupuesto: {fmt(ent_match['valor_del_contrato'].sum())}",
                       style={'margin': '0', 'fontSize': '11px', 'color': GRIS_OSCURO}),
            ])
            return crear_modal(f"Detalle: {ent_match['nombre_entidad'].iloc[0][:50]}", html.Div([resumen, tabla_dash(data, 20)])), {'display': 'block'}

    return [], {'display': 'none'}

# =============================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    print(f"\n  Dashboard SECOP II — http://127.0.0.1:{port}\n")
    app.run(debug=False, host='0.0.0.0', port=port)
