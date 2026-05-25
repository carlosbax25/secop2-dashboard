"""
Dashboard Interactivo - Transparencia en la Contratacion Publica Colombiana
Motor: PySpark (ingesta) + Dash/Plotly (visualizacion)
Filtro dinamico por anios.
"""
import dash
from dash import dcc, html, Input, Output, no_update, dash_table
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import os
import json as json_lib
from spark_etl import ingest_and_process
from pages import build_storytelling, build_analisis_competitividad
from charts import compute_kpis, build_fig1, build_fig2, build_fig3, build_fig4, fmt

# =============================================================================
# DATOS
# =============================================================================
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'secop2_adjudicados_limpio.csv')
GEOJSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'depto.json')

print("Cargando datos...")
df_full = ingest_and_process(DATA_PATH)
df_full['anio_adjudicacion'] = pd.to_numeric(df_full['anio_adjudicacion'], errors='coerce').fillna(0).astype(int)
anios_disponibles = sorted(df_full[df_full['anio_adjudicacion'] > 2000]['anio_adjudicacion'].unique())

with open(GEOJSON_PATH, encoding='utf-8') as f:
    geojson_data = json_lib.load(f)
print(f"  {len(df_full):,} registros | Anios: {anios_disponibles}")

# =============================================================================
# ESTILOS
# =============================================================================
FONDO = '#FAFAFA'
BLANCO = '#FFFFFF'
GRIS_OSCURO = '#212121'
GRIS_MEDIO = '#616161'
GRIS_CLARO = '#BDBDBD'
AZUL_OSCURO = '#08519C'
RESALTADO = '#D94701'
ALERTA_FONDO = '#FBE9E7'

KPI_STYLE = lambda border_color=None, bg=BLANCO: {
    'flex': '1', 'padding': '10px 14px', 'backgroundColor': bg,
    'border': f'1px solid {border_color or "#E0E0E0"}', 'borderRadius': '4px',
    'cursor': 'pointer', 'transition': 'box-shadow 0.2s',
}
CARD_VIZ = {
    'background': BLANCO, 'borderRadius': '10px', 'overflow': 'hidden',
    'border': '1px solid #e2e8f0', 'boxShadow': '0 4px 6px rgba(0,0,0,0.04)',
}
HEADER_VIZ = {'padding': '12px 18px', 'fontWeight': '700', 'color': 'white', 'fontSize': '13px', 'background': '#1e3a8a'}

# =============================================================================
# APP
# =============================================================================
app = dash.Dash(__name__, title="SECOP II - Contratacion Publica Colombia", suppress_callback_exceptions=True)
server = app.server

app.layout = html.Div(style={'display': 'flex', 'minHeight': '100vh', 'fontFamily': "'Segoe UI', sans-serif"}, children=[
    # Store global para anios seleccionados
    dcc.Store(id='store-anios', data=None),

    # SIDEBAR
    html.Div(style={
        'width': '210px', 'minWidth': '210px', 'padding': '24px 16px',
        'backgroundColor': '#08306B', 'color': 'white',
        'display': 'flex', 'flexDirection': 'column',
        'position': 'fixed', 'top': 0, 'left': 0, 'bottom': 0,
        'overflowY': 'auto', 'zIndex': '100',
    }, children=[
        html.Div(style={'marginBottom': '24px'}, children=[
            html.H3("SECOP II", style={'margin': '0', 'fontSize': '15px', 'fontWeight': '800', 'color': 'white'}),
            html.P("VEEDURIA CIUDADANA", style={'margin': '4px 0 0', 'fontSize': '9px', 'color': '#93C5FD', 'letterSpacing': '1.5px'}),
        ]),
        # Filtro de anios GLOBAL en el sidebar
        html.Div(style={'borderTop': '1px solid rgba(255,255,255,0.1)', 'paddingTop': '12px', 'marginBottom': '16px'}, children=[
            html.P("PERIODO", style={'fontSize': '9px', 'color': '#93C5FD', 'letterSpacing': '1px', 'margin': '0 0 8px'}),
            dcc.Dropdown(
                id='filtro-anios-check',
                options=[{'label': str(int(a)), 'value': int(a)} for a in anios_disponibles],
                value=[int(a) for a in anios_disponibles[-3:]],
                multi=True,
                placeholder="Seleccionar anios...",
                optionHeight=30,
                maxHeight=200,
                style={'fontSize': '11px', 'backgroundColor': '#1e3a8a', 'borderRadius': '4px', 'border': '1px solid #3b82f6', 'color': 'white'},
            ),
        ]),
        html.Div(style={'borderTop': '1px solid rgba(255,255,255,0.1)', 'paddingTop': '16px', 'flex': '1'}, children=[
            html.Div(id='nav-storytelling', n_clicks=0, children="Storytelling"),
            html.Div(id='nav-dashboard', n_clicks=0, children="Dashboard"),
            html.Div(id='nav-infografia', n_clicks=0, children="Analisis Competitividad"),
            html.Div(id='nav-documento', n_clicks=0, children="Documento FASE 1"),
        ]),
        html.Div(style={'borderTop': '1px solid rgba(255,255,255,0.1)', 'paddingTop': '12px', 'marginTop': 'auto'}, children=[
            html.P("Tecnologico Comfenalco", style={'fontSize': '9px', 'color': '#93C5FD', 'margin': '0'}),
            html.P("Proyecto Integrador - 2026", style={'fontSize': '9px', 'color': '#93C5FD', 'margin': '3px 0 0'}),
        ]),
    ]),
    # CONTENIDO
    html.Div(id='page-content', style={
        'flex': '1', 'padding': '20px 30px 40px 30px', 'backgroundColor': FONDO,
        'overflowY': 'auto', 'marginLeft': '220px',
    }),
    # MODAL (siempre presente, oculto por defecto)
    html.Div(id='modal-container', style={'display': 'none'}),
])

# =============================================================================
# CALLBACK: Navegacion
# =============================================================================
@app.callback(
    Output('page-content', 'children'),
    Output('nav-storytelling', 'style'),
    Output('nav-dashboard', 'style'),
    Output('nav-infografia', 'style'),
    Output('nav-documento', 'style'),
    Input('nav-storytelling', 'n_clicks'),
    Input('nav-dashboard', 'n_clicks'),
    Input('nav-infografia', 'n_clicks'),
    Input('nav-documento', 'n_clicks'),
    Input('filtro-anios-check', 'value'),
)
def navigate(c1, c2, c3, c4, anios_sel):
    ctx = dash.callback_context
    base = {'display': 'block', 'padding': '10px 14px', 'margin': '4px 0',
            'borderRadius': '6px', 'color': '#93C5FD', 'fontSize': '12px', 'cursor': 'pointer'}
    active = {**base, 'backgroundColor': 'rgba(255,255,255,0.12)', 'color': 'white', 'fontWeight': '600'}

    # Filtrar datos por anios seleccionados
    if not anios_sel:
        anios_sel = [int(a) for a in anios_disponibles[-3:]]
    df_f = df_full[df_full['anio_adjudicacion'].isin(anios_sel)]

    # Determinar que pagina mostrar
    trigger = ''
    if ctx.triggered:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    # Si el trigger es el filtro de anios, mantener la pagina actual
    is_filter = trigger == 'filtro-anios-check'
    if trigger == 'nav-dashboard' or (is_filter and hasattr(navigate, '_last_page') and navigate._last_page == 'dashboard'):
        navigate._last_page = 'dashboard'
        return build_dashboard_content(df_f), base, active, base, base
    elif trigger == 'nav-infografia' or (is_filter and hasattr(navigate, '_last_page') and navigate._last_page == 'infografia'):
        navigate._last_page = 'infografia'
        fig1 = build_fig1(df_f, geojson_data)
        fig2 = build_fig2(df_f)
        fig3, _ = build_fig3(df_f)
        fig4 = build_fig4(df_f)
        return build_analisis_competitividad(df_f, fig1, fig2, fig3, fig4), base, base, active, base
    elif trigger == 'nav-documento' or (is_filter and hasattr(navigate, '_last_page') and navigate._last_page == 'documento'):
        navigate._last_page = 'documento'
        content = html.Div(style={'padding': '20px 0'}, children=[
            html.Iframe(src='/assets/fase1.pdf', style={'width': '100%', 'height': '88vh', 'border': 'none', 'borderRadius': '8px'}),
        ])
        return content, base, base, base, active
    else:
        navigate._last_page = 'storytelling'
        return build_storytelling(df_f), active, base, base, base

navigate._last_page = 'storytelling'

# =============================================================================
# DASHBOARD PAGE (con filtro de anios)
# =============================================================================
def build_dashboard_page():
    """Construye la pagina del dashboard con datos filtrados."""
    # Este metodo ya no se usa directamente, se usa build_dashboard_content
    return build_dashboard_content(df_full)


def build_dashboard_content(df_f):
    """Construye el contenido del dashboard con datos ya filtrados."""
    kpis = compute_kpis(df_f)
    fig1 = build_fig1(df_f, geojson_data)
    fig2 = build_fig2(df_f)
    fig3, _ = build_fig3(df_f)
    fig4 = build_fig4(df_f)

    return html.Div([
        # Header
        html.Div(style={'padding': '10px 0 12px', 'borderBottom': f'2px solid {AZUL_OSCURO}'}, children=[
            html.H1("Transparencia en la Contratacion Publica Colombiana",
                    style={'margin': '0', 'fontSize': '18px', 'fontWeight': '700', 'color': GRIS_OSCURO}),
            html.P("Los datos se actualizan segun los anios seleccionados en el filtro lateral.",
                   style={'margin': '3px 0 0', 'fontSize': '11px', 'color': GRIS_MEDIO}),
        ]),
        # KPIs
        html.Div(style={'display': 'flex', 'gap': '10px', 'margin': '14px 0'}, children=[
            html.Div(style=KPI_STYLE(), children=[
                html.P("Presupuesto Adjudicado", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
                html.P(fmt(kpis['presupuesto_total']), style={'margin': '2px 0 0', 'fontSize': '16px', 'fontWeight': '700', 'color': AZUL_OSCURO}),
            ]),
            html.Div(style=KPI_STYLE(), children=[
                html.P("Contratos Adjudicados", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
                html.P(f"{kpis['total_contratos']:,}", style={'margin': '2px 0 0', 'fontSize': '16px', 'fontWeight': '700', 'color': GRIS_OSCURO}),
            ]),
            html.Div(style=KPI_STYLE(), children=[
                html.P("Cobertura", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
                html.P("32 Dptos + Bogota D.C.", style={'margin': '2px 0 0', 'fontSize': '14px', 'fontWeight': '700', 'color': GRIS_OSCURO}),
            ]),
            html.Div(style=KPI_STYLE(RESALTADO, ALERTA_FONDO), children=[
                html.P("Sin Competencia", style={'margin': '0', 'fontSize': '9px', 'color': GRIS_MEDIO}),
                html.P(f"{kpis['pct_sin_comp']}%", style={'margin': '2px 0 0', 'fontSize': '16px', 'fontWeight': '700', 'color': RESALTADO}),
            ]),
        ]),
        # Graficas
        html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '20px', 'margin': '20px 0'}, children=[
            html.Div(style=CARD_VIZ, children=[
                html.Div("1. Distribucion Geografica del Presupuesto", style=HEADER_VIZ),
                html.Div(style={'padding': '16px'}, children=[dcc.Graph(id='g-situacion', figure=fig1, config={'displayModeBar': False})]),
            ]),
            html.Div(style=CARD_VIZ, children=[
                html.Div("2. Modalidades y Nivel de Competencia", style=HEADER_VIZ),
                html.Div(style={'padding': '16px'}, children=[dcc.Graph(id='g-complicacion', figure=fig2, config={'displayModeBar': False})]),
            ]),
            html.Div(style=CARD_VIZ, children=[
                html.Div("3. Concentracion de Proveedores", style=HEADER_VIZ),
                html.Div(style={'padding': '16px'}, children=[dcc.Graph(id='g-resolucion', figure=fig3, config={'displayModeBar': False})]),
            ]),
            html.Div(style=CARD_VIZ, children=[
                html.Div("4. Entidades Estatales Prioritarias", style=HEADER_VIZ),
                html.Div(style={'padding': '16px'}, children=[dcc.Graph(id='g-accion', figure=fig4, config={'displayModeBar': False})]),
            ]),
        ]),
    ])


# =============================================================================
# CALLBACKS: Modales interactivos al hacer clic en graficos
# =============================================================================
MODAL_OVERLAY = {
    'position': 'fixed', 'top': 0, 'left': 0, 'width': '100%', 'height': '100%',
    'backgroundColor': 'rgba(0,0,0,0.5)', 'zIndex': 1000,
    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
}
MODAL_CONTENT = {
    'backgroundColor': BLANCO, 'borderRadius': '8px', 'padding': '24px',
    'maxWidth': '900px', 'width': '90%', 'maxHeight': '80vh', 'overflowY': 'auto',
    'boxShadow': '0 4px 20px rgba(0,0,0,0.15)', 'position': 'relative',
}

def crear_modal(titulo, contenido):
    return html.Div(style=MODAL_OVERLAY, children=[
        html.Div(style=MODAL_CONTENT, children=[
            html.Button("X", id='modal-close', style={
                'position': 'absolute', 'top': '12px', 'right': '16px',
                'fontSize': '18px', 'cursor': 'pointer', 'color': GRIS_MEDIO,
                'border': 'none', 'background': 'none', 'fontWeight': '700',
            }),
            html.H3(titulo, style={'margin': '0 0 12px', 'fontSize': '15px', 'color': GRIS_OSCURO}),
            contenido,
        ])
    ])

def tabla_modal(dataframe, max_rows=20):
    return dash_table.DataTable(
        data=dataframe.head(max_rows).to_dict('records'),
        columns=[{'name': c, 'id': c} for c in dataframe.columns],
        style_table={'overflowX': 'auto'},
        style_header={'backgroundColor': '#FAFAFA', 'fontWeight': '600', 'fontSize': '10px',
                      'color': GRIS_OSCURO, 'border': 'none', 'borderBottom': '2px solid #BDBDBD'},
        style_cell={'fontSize': '10px', 'padding': '6px 10px', 'border': 'none',
                    'borderBottom': '1px solid #EEEEEE', 'textAlign': 'left',
                    'maxWidth': '200px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#F9F9F9'}],
    )

@app.callback(
    Output('modal-container', 'children'),
    Output('modal-container', 'style'),
    Input('g-situacion', 'clickData'),
    Input('g-complicacion', 'clickData'),
    Input('g-resolucion', 'clickData'),
    Input('g-accion', 'clickData'),
    Input('modal-container', 'n_clicks'),
    Input('filtro-anios-check', 'value'),
    prevent_initial_call=True,
)
def manejar_modales(click_g1, click_g2, click_g3, click_g4, click_overlay, anios_sel):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update, {'display': 'none'}

    trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    # Cerrar modal
    if trigger in ('modal-container', 'filtro-anios-check'):
        return [], {'display': 'none'}

    # Filtrar datos por anios actuales
    if not anios_sel:
        anios_sel = [int(a) for a in anios_disponibles[-3:]]
    df_f = df_full[df_full['anio_adjudicacion'].isin(anios_sel)]
    df_baja = df_f[df_f['baja_competencia'] == 1]

    # Clic en Viz 1 (mapa - departamento)
    if trigger == 'g-situacion' and click_g1:
        point = click_g1['points'][0]
        depto = point.get('text', '')
        data = df_f[df_f['departamento_entidad'].str.lower() == depto.lower()]
        if data.empty:
            data = df_f[df_f['departamento_entidad'].str.contains(depto[:10], case=False, na=False)]
        if not data.empty:
            tabla = data[['entidad', 'nombre_del_proveedor', 'modalidad_de_contratacion', 'valor_total_adjudicacion']
            ].sort_values('valor_total_adjudicacion', ascending=False).head(20).copy()
            tabla['valor_total_adjudicacion'] = tabla['valor_total_adjudicacion'].apply(fmt)
            tabla.columns = ['Entidad', 'Proveedor', 'Modalidad', 'Valor']
            return crear_modal(f"Top contratos en {depto}", tabla_modal(tabla)), {'display': 'block'}

    # Clic en Viz 2 (modalidad)
    if trigger == 'g-complicacion' and click_g2:
        modalidad = click_g2['points'][0]['y']
        data_mod = df_f[df_f['modalidad_de_contratacion'] == modalidad]
        if not data_mod.empty:
            resumen = data_mod.groupby('rango_oferentes').agg(
                Contratos=('valor_total_adjudicacion', 'count'),
                Presupuesto=('valor_total_adjudicacion', 'sum'),
            ).reset_index()
            resumen['Presupuesto'] = resumen['Presupuesto'].apply(fmt)
            resumen.columns = ['Rango Oferentes', 'Contratos', 'Presupuesto']
            return crear_modal(f"Competencia en: {modalidad}", tabla_modal(resumen)), {'display': 'block'}

    # Clic en Viz 3 (treemap proveedor)
    if trigger == 'g-resolucion' and click_g3:
        label = click_g3['points'][0].get('label', '')
        if label and label != 'Proveedores':
            prov_match = df_baja[df_baja['nombre_del_proveedor'] == label]
            if prov_match.empty:
                prov_match = df_baja[df_baja['nombre_del_proveedor'].str.contains(label[:20], case=False, na=False)]
            if not prov_match.empty:
                tabla = prov_match[['entidad', 'departamento_entidad', 'modalidad_de_contratacion', 'valor_total_adjudicacion']
                ].sort_values('valor_total_adjudicacion', ascending=False).head(15).copy()
                tabla['valor_total_adjudicacion'] = tabla['valor_total_adjudicacion'].apply(fmt)
                tabla.columns = ['Entidad', 'Departamento', 'Modalidad', 'Valor']
                return crear_modal(f"Contratos de: {label[:50]}", tabla_modal(tabla)), {'display': 'block'}

    # Clic en Viz 4 (barras entidades)
    if trigger == 'g-accion' and click_g4:
        entidad = click_g4['points'][0]['y']
        ent_match = df_baja[df_baja['entidad'] == entidad]
        if not ent_match.empty:
            total = len(ent_match)
            ppto = fmt(ent_match['valor_total_adjudicacion'].sum())
            tabla = ent_match[['nombre_del_proveedor', 'modalidad_de_contratacion', 'valor_total_adjudicacion']
            ].sort_values('valor_total_adjudicacion', ascending=False).head(20).copy()
            tabla['valor_total_adjudicacion'] = tabla['valor_total_adjudicacion'].apply(fmt)
            tabla.columns = ['Proveedor', 'Modalidad', 'Valor']
            resumen = html.P(f"Total contratos: {total} | Presupuesto: {ppto}",
                           style={'margin': '0 0 12px', 'fontSize': '11px', 'color': GRIS_OSCURO, 'padding': '10px', 'backgroundColor': '#F5F5F5', 'borderRadius': '4px'})
            return crear_modal(f"{entidad[:50]}", html.Div([resumen, tabla_modal(tabla)])), {'display': 'block'}

    return [], {'display': 'none'}


# =============================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    print(f"\n  Dashboard SECOP II - http://127.0.0.1:{port}\n")
    app.run(debug=False, host='0.0.0.0', port=port)
