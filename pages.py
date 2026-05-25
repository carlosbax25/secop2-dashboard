"""
Páginas dinámicas del dashboard: Storytelling y Análisis de Competitividad.
Se alimentan del mismo dataset que el dashboard principal.
"""
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd


def fmt(v):
    if v >= 1e12: return f"${v/1e12:.1f} B"
    if v >= 1e9: return f"${v/1e9:.1f} mil M"
    if v >= 1e6: return f"${v/1e6:,.0f} M"
    return f"${v:,.0f}"


def fmt_billones(v):
    return f"{v/1e12:.2f} Billones COP"


def build_storytelling(df):
    """Genera la página de Storytelling con datos reales del dataset."""
    # Calcular KPIs reales
    total_valor = df['valor_total_adjudicacion'].sum()
    df_baja = df[df['baja_competencia'] == 1]
    valor_baja = df_baja['valor_total_adjudicacion'].sum()
    pct_baja = (valor_baja / total_valor * 100) if total_valor > 0 else 0

    # Top proveedor en baja competencia
    top_prov = df_baja.groupby('nombre_del_proveedor')['valor_total_adjudicacion'].sum().sort_values(ascending=False)
    mega_contratista = top_prov.index[0] if len(top_prov) > 0 else "N/A"
    mega_valor = top_prov.iloc[0] if len(top_prov) > 0 else 0

    # Top entidad en baja competencia
    top_ent = df_baja.groupby('entidad')['valor_total_adjudicacion'].sum().sort_values(ascending=False)
    foco_entidad = top_ent.index[0] if len(top_ent) > 0 else "N/A"
    foco_valor = top_ent.iloc[0] if len(top_ent) > 0 else 0

    # Estilos inline
    card_style = {
        'background': '#ffffff', 'borderRadius': '16px', 'padding': '30px',
        'borderLeft': '6px solid #3b82f6', 'boxShadow': '0 10px 25px rgba(0,0,0,0.05)',
        'borderTop': '1px solid #f1f5f9', 'borderRight': '1px solid #f1f5f9',
        'borderBottom': '1px solid #f1f5f9',
    }

    return html.Div(style={'background': '#f8fafc', 'padding': '40px', 'minHeight': '90vh'}, children=[
        html.Div(style={'maxWidth': '1000px', 'margin': '0 auto'}, children=[
            # Header
            html.Div(style={'textAlign': 'center', 'marginBottom': '50px', 'borderBottom': '1px solid #e2e8f0', 'paddingBottom': '30px'}, children=[
                html.H1("Alerta de Pluralidad: SECOP II", style={
                    'fontSize': '2.5rem', 'fontWeight': '900', 'margin': '0',
                    'color': '#1d4ed8', 'letterSpacing': '-1px',
                }),
                html.H3("Análisis del déficit de competencia en la adjudicación de recursos públicos", style={
                    'color': '#64748b', 'fontWeight': '400', 'fontSize': '1.1rem', 'marginTop': '15px',
                }),
            ]),

            # KPIs Grid
            html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '30px', 'marginBottom': '30px'}, children=[
                # KPI 1: Exposición Financiera
                html.Div(style=card_style, children=[
                    html.P("EXPOSICIÓN FINANCIERA", style={'fontSize': '0.8rem', 'textTransform': 'uppercase', 'letterSpacing': '1.5px', 'color': '#64748b', 'fontWeight': '600', 'marginBottom': '15px'}),
                    html.P(fmt_billones(valor_baja), style={'fontSize': '2.8rem', 'fontWeight': '900', 'color': '#0f172a', 'lineHeight': '1', 'marginBottom': '10px'}),
                    html.P([
                        "Adjudicados a procesos con ",
                        html.Span("1 o ningún oferente competitivo", style={'color': '#2563eb', 'fontWeight': '700'}),
                        "."
                    ], style={'fontSize': '1rem', 'color': '#475569', 'lineHeight': '1.5'}),
                ]),

                # KPI 2: Déficit de Competencia
                html.Div(style=card_style, children=[
                    html.P("DÉFICIT DE COMPETENCIA", style={'fontSize': '0.8rem', 'textTransform': 'uppercase', 'letterSpacing': '1.5px', 'color': '#64748b', 'fontWeight': '600', 'marginBottom': '15px'}),
                    html.P(f"{pct_baja:.1f}%", style={'fontSize': '2.8rem', 'fontWeight': '900', 'color': '#0f172a', 'lineHeight': '1', 'marginBottom': '10px'}),
                    html.P("Del presupuesto total analizado se asignó sin garantizar pluralidad de mercado.", style={'fontSize': '1rem', 'color': '#475569', 'lineHeight': '1.5'}),
                ]),

                # KPI 3: Mega-Contratista (span 2 columnas)
                html.Div(style={**card_style, 'gridColumn': 'span 2', 'borderLeftColor': '#60a5fa'}, children=[
                    html.P("MEGA-CONTRATISTA SIN COMPETENCIA", style={'fontSize': '0.8rem', 'textTransform': 'uppercase', 'letterSpacing': '1.5px', 'color': '#64748b', 'fontWeight': '600', 'marginBottom': '15px'}),
                    html.P(mega_contratista, style={'fontSize': '2rem', 'fontWeight': '900', 'color': '#0f172a', 'lineHeight': '1.2', 'marginBottom': '10px'}),
                    html.P([
                        "Ha recibido ",
                        html.Span(fmt_billones(mega_valor), style={'color': '#2563eb', 'fontWeight': '700'}),
                        " en procesos con 1 o ningún oferente. Identificar a los mayores receptores de fondos en estos escenarios es vital para mapear posibles monopolios o direccionamientos."
                    ], style={'fontSize': '1rem', 'color': '#475569', 'lineHeight': '1.5'}),
                ]),

                # Target Card (span 2 columnas)
                html.Div(style={
                    'background': 'linear-gradient(135deg, #1e3a8a, #1d4ed8)',
                    'borderRadius': '16px', 'padding': '40px', 'textAlign': 'center',
                    'gridColumn': 'span 2', 'boxShadow': '0 15px 35px rgba(29, 78, 216, 0.2)',
                }, children=[
                    html.P("FOCO DE AUDITORÍA PRIORITARIA (ENTIDAD)", style={'fontSize': '0.9rem', 'textTransform': 'uppercase', 'letterSpacing': '2px', 'color': '#93c5fd', 'fontWeight': '800', 'marginBottom': '15px'}),
                    html.P(foco_entidad, style={'fontSize': '1.8rem', 'fontWeight': '900', 'color': '#ffffff', 'marginBottom': '10px', 'lineHeight': '1.2'}),
                    html.P(f"{fmt_billones(foco_valor)} adjudicados sin pluralidad", style={'fontSize': '1.3rem', 'color': '#bfdbfe', 'fontWeight': '600'}),
                ]),
            ]),

            # Footer
            html.P("Este reporte focaliza la exposición de la contratación estatal ante escenarios de bajo concurso. Diseñado para control interno y veeduría especializada.",
                   style={'textAlign': 'center', 'color': '#94a3b8', 'marginTop': '40px', 'fontSize': '0.9rem'}),
        ]),
    ])


def build_analisis_competitividad(df, fig1, fig2, fig3, fig4):
    """Genera la página de Análisis de Competitividad con datos reales y gráficos dinámicos."""

    card_context_style = {
        'background': 'white', 'borderRadius': '8px', 'padding': '20px',
        'boxShadow': '0 4px 6px rgba(0,0,0,0.05)', 'borderTop': '4px solid #3b82f6',
    }
    card_style = {
        'background': 'white', 'borderRadius': '10px', 'overflow': 'hidden',
        'boxShadow': '0 10px 15px -3px rgba(0,0,0,0.05)', 'border': '1px solid #e2e8f0',
    }

    return html.Div(style={'background': '#f8fafc', 'padding': '40px', 'minHeight': '90vh', 'color': '#1e293b'}, children=[
        # Header
        html.Div(style={'textAlign': 'center', 'marginBottom': '40px'}, children=[
            html.H1("Análisis de Competitividad: SECOP II", style={'fontWeight': '700', 'fontSize': '2rem', 'color': '#0f172a', 'margin': '0', 'letterSpacing': '-0.5px'}),
            html.H3("Concentración del Presupuesto Público y Riesgos de Pluralidad", style={'fontWeight': '400', 'color': '#475569', 'marginTop': '10px', 'fontSize': '1.1rem'}),
        ]),

        # Context cards (3 columnas)
        html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(3, 1fr)', 'gap': '20px', 'marginBottom': '40px'}, children=[
            html.Div(style=card_context_style, children=[
                html.H4("Descripción del Dataset", style={'marginTop': '0', 'color': '#1e40af', 'fontSize': '1rem', 'fontWeight': '700', 'marginBottom': '12px'}),
                html.P(f"Fuente: Agencia Nacional de Contratación Pública (Colombia Compra Eficiente). El análisis se realizó sobre {len(df):,} contratos electrónicos de SECOP II, con variables asociadas a competitividad y modalidad contractual.",
                       style={'fontSize': '0.85rem', 'color': '#475569', 'lineHeight': '1.5', 'margin': '0'}),
            ]),
            html.Div(style=card_context_style, children=[
                html.H4("Problema Analítico", style={'marginTop': '0', 'color': '#1e40af', 'fontSize': '1rem', 'fontWeight': '700', 'marginBottom': '12px'}),
                html.P("Una parte significativa del presupuesto público se adjudica en procesos con escasa o nula pluralidad de oferentes. Este análisis identifica patrones de baja competitividad en la contratación estatal.",
                       style={'fontSize': '0.85rem', 'color': '#475569', 'lineHeight': '1.5', 'margin': '0'}),
            ]),
            html.Div(style=card_context_style, children=[
                html.H4("Objetivo del Análisis", style={'marginTop': '0', 'color': '#1e40af', 'fontSize': '1rem', 'fontWeight': '700', 'marginBottom': '12px'}),
                html.P("Diseñado para facilitar la labor de Veeduría Ciudadana. Provee hallazgos estructurados que permiten identificar y focalizar auditorías en las entidades y regiones con mayor concentración de contratos sin pluralidad.",
                       style={'fontSize': '0.85rem', 'color': '#475569', 'lineHeight': '1.5', 'margin': '0'}),
            ]),
        ]),

        # Hallazgo Principal
        html.Div(style={'background': '#eff6ff', 'borderLeft': '6px solid #2563eb', 'padding': '25px', 'borderRadius': '6px', 'marginBottom': '40px'}, children=[
            html.P("HALLAZGO PRINCIPAL", style={'fontWeight': '700', 'color': '#1d4ed8', 'textTransform': 'uppercase', 'fontSize': '0.85rem', 'letterSpacing': '1px', 'marginBottom': '8px'}),
            html.P("La contratación directa y los procesos de oferente único concentran una alta proporción del presupuesto público adjudicado, aislando la competencia y consolidando a contratistas específicos como los mayores receptores de fondos.",
                   style={'fontSize': '1.1rem', 'color': '#1e3a8a', 'lineHeight': '1.4', 'margin': '0'}),
        ]),

        # Gráficos Grid 2x2
        html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '30px'}, children=[
            # Viz 1
            html.Div(style=card_style, children=[
                html.Div("1. Distribución Geográfica del Presupuesto", style={'padding': '15px 20px', 'fontWeight': '700', 'color': 'white', 'fontSize': '0.95rem', 'background': '#1e3a8a'}),
                html.Div(style={'padding': '20px'}, children=[
                    html.P("¿Cómo se distribuye geográficamente el presupuesto total contratado?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '0.9rem', 'margin': '0 0 8px'}),
                    html.P("El mapa dimensiona de manera intuitiva el tamaño del mercado de contratación pública a nivel departamental.", style={'fontSize': '0.85rem', 'color': '#64748b', 'margin': '0 0 15px', 'lineHeight': '1.5'}),
                    dcc.Graph(figure=fig1, config={'displayModeBar': False}, style={'height': '350px'}),
                ]),
            ]),
            # Viz 2
            html.Div(style=card_style, children=[
                html.Div("2. Modalidades y Nivel de Competencia", style={'padding': '15px 20px', 'fontWeight': '700', 'color': 'white', 'fontSize': '0.95rem', 'background': '#1d4ed8'}),
                html.Div(style={'padding': '20px'}, children=[
                    html.P("¿Qué modalidades de contratación presentan estructuralmente una menor cantidad de oferentes?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '0.9rem', 'margin': '0 0 8px'}),
                    html.P("Al estandarizar las barras al 100%, se compara visualmente la proporción interna de competencia (Baja vs Alta) entre modalidades.", style={'fontSize': '0.85rem', 'color': '#64748b', 'margin': '0 0 15px', 'lineHeight': '1.5'}),
                    dcc.Graph(figure=fig2, config={'displayModeBar': False}, style={'height': '350px'}),
                ]),
            ]),
            # Viz 3
            html.Div(style=card_style, children=[
                html.Div("3. Concentración de Proveedores", style={'padding': '15px 20px', 'fontWeight': '700', 'color': 'white', 'fontSize': '0.95rem', 'background': '#2563eb'}),
                html.Div(style={'padding': '20px'}, children=[
                    html.P("¿Cuáles proveedores absorben la mayor cantidad de dinero en escenarios de baja competencia?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '0.9rem', 'margin': '0 0 8px'}),
                    html.P("El tamaño de las áreas representa la magnitud del presupuesto adjudicado. Facilita la identificación inmediata de los principales contratistas en entornos sin pluralidad.", style={'fontSize': '0.85rem', 'color': '#64748b', 'margin': '0 0 15px', 'lineHeight': '1.5'}),
                    dcc.Graph(figure=fig3, config={'displayModeBar': False}, style={'height': '350px'}),
                ]),
            ]),
            # Viz 4
            html.Div(style=card_style, children=[
                html.Div("4. Entidades Estatales Prioritarias", style={'padding': '15px 20px', 'fontWeight': '700', 'color': 'white', 'fontSize': '0.95rem', 'background': '#334155'}),
                html.Div(style={'padding': '20px'}, children=[
                    html.P("¿Qué entidades concentran los mayores montos bajo alertas de baja competencia?", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '0.9rem', 'margin': '0 0 8px'}),
                    html.P("El ordenamiento descendente actúa como una lista de prioridades o \"ruta de auditoría\" directa para el control social.", style={'fontSize': '0.85rem', 'color': '#64748b', 'margin': '0 0 15px', 'lineHeight': '1.5'}),
                    dcc.Graph(figure=fig4, config={'displayModeBar': False}, style={'height': '350px'}),
                ]),
            ]),
        ]),
    ])
