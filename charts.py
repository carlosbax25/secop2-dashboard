"""
Genera las figuras de Plotly dinámicamente según filtros aplicados.
"""
import plotly.graph_objects as go
import pandas as pd
import numpy as np

AZUL_OSCURO = '#08519C'
GRIS_OSCURO = '#212121'
GRIS_MEDIO = '#616161'
GRIS_CLARO = '#BDBDBD'
BLANCO = '#FFFFFF'

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

import unicodedata
def norm_dep(t):
    if not t: return ""
    return "".join(c for c in unicodedata.normalize("NFKD", str(t)) if not unicodedata.combining(c)).upper().strip()

def fmt(v):
    if v >= 1e12: return f"${v/1e12:.1f} B"
    if v >= 1e9: return f"${v/1e9:.1f} mil M"
    if v >= 1e6: return f"${v/1e6:,.0f} M"
    return f"${v:,.0f}"


def compute_kpis(df_filtered):
    """Calcula KPIs del dataset filtrado."""
    total_contratos = len(df_filtered)
    presupuesto_total = df_filtered['valor_total_adjudicacion'].sum()
    pct_sin_comp = df_filtered['baja_competencia'].mean() * 100 if total_contratos > 0 else 0
    return {
        'total_contratos': total_contratos,
        'presupuesto_total': presupuesto_total,
        'pct_sin_comp': round(pct_sin_comp, 1),
    }


def build_fig1(df_filtered, geojson_data):
    """Viz 1: Mapa de burbujas Top 5 departamentos."""
    dept = df_filtered.groupby('departamento_entidad').agg(
        ppto=('valor_total_adjudicacion', 'sum'),
        n=('valor_total_adjudicacion', 'count'),
    ).reset_index().sort_values('ppto', ascending=False)
    total_ppto = df_filtered['valor_total_adjudicacion'].sum()
    dept['pct'] = (dept['ppto'] / total_ppto * 100).round(1) if total_ppto > 0 else 0

    top5 = dept.head(5).copy()
    pct_top5 = top5['pct'].sum()

    top5['dep_key'] = top5['departamento_entidad'].apply(norm_dep)
    top5['lat'] = top5['dep_key'].apply(lambda x: next((v[0] for k, v in COORDS_DEPTOS.items() if k in x or x in k), None))
    top5['lon'] = top5['dep_key'].apply(lambda x: next((v[1] for k, v in COORDS_DEPTOS.items() if k in x or x in k), None))
    top5 = top5.dropna(subset=['lat', 'lon'])
    top5['ppto_fmt'] = top5['ppto'].apply(fmt)
    top5['size'] = (top5['ppto'] / top5['ppto'].max() * 45) + 12 if not top5.empty else 20

    fig = go.Figure()
    if not top5.empty:
        fig.add_trace(go.Scattermapbox(
            lat=top5['lat'], lon=top5['lon'],
            mode='markers+text',
            marker=dict(
                size=top5['size'],
                color=top5['ppto'],
                colorscale=[[0,'#BDD7E7'],[0.3,'#6BAED6'],[0.6,'#3182BD'],[1,'#08519C']],
                showscale=False, opacity=0.8, sizemode='diameter',
            ),
            text=top5['departamento_entidad'].str.title(),
            textposition='top center',
            textfont=dict(size=9, color=GRIS_OSCURO),
            customdata=np.column_stack([top5['ppto_fmt'], top5['pct'], top5['n']]),
            hovertemplate='<b>%{text}</b><br>Presupuesto: %{customdata[0]}<br>%{customdata[1]}% del total<br>%{customdata[2]:,} contratos<extra></extra>',
        ))
    fig.update_layout(
        title=dict(text=f'<b>Top 5 concentran el {pct_top5:.0f}% del presupuesto</b>', font=dict(size=11, color=GRIS_OSCURO), x=0, y=0.97),
        mapbox=dict(style='carto-positron', center=dict(lat=5.5, lon=-74.0), zoom=4.3,
                    layers=[dict(source=geojson_data, type='line', color='#BDBDBD', line=dict(width=0.5), below='traces')]),
        paper_bgcolor=BLANCO, margin=dict(l=0, r=0, t=30, b=0), height=400, showlegend=False,
    )
    return fig


def build_fig2(df_filtered):
    """Viz 2: Barras apiladas 100% modalidades (3 categorias azul)."""
    df_filtered = df_filtered.copy()
    df_filtered['rango_competencia'] = pd.cut(
        df_filtered['respuestas_al_procedimiento'].fillna(0).astype(float),
        bins=[-1, 1, 3, 9999],
        labels=['1. Nula (<=1 oferente)', '2. Baja (2-3 oferentes)', '3. Alta (4+ oferentes)']
    )
    modalidades_top = df_filtered['modalidad_de_contratacion'].value_counts().head(10).index.tolist()
    df_m = df_filtered[df_filtered['modalidad_de_contratacion'].isin(modalidades_top)]
    cross = pd.crosstab(df_m['modalidad_de_contratacion'], df_m['rango_competencia'], normalize='index') * 100
    cross = cross.reset_index()

    nula_col = '1. Nula (<=1 oferente)'
    if nula_col in cross.columns:
        cross = cross.sort_values(nula_col, ascending=True)

    cats = ['1. Nula (<=1 oferente)', '2. Baja (2-3 oferentes)', '3. Alta (4+ oferentes)']
    colores = ['#BDD7E7', '#3182BD', '#08519C']

    fig = go.Figure()
    for i, cat in enumerate(cats):
        if cat in cross.columns:
            fig.add_trace(go.Bar(
                name=cat, y=cross['modalidad_de_contratacion'], x=cross[cat],
                orientation='h', marker=dict(color=colores[i], line=dict(width=0)),
                hovertemplate=f'<b>%{{y}}</b><br>{cat}: %{{x:.1f}}%<extra></extra>',
            ))
    fig.update_layout(
        barmode='stack',
        xaxis=dict(title='Procesos adjudicados', showgrid=False, zeroline=False, range=[0, 100], tickfont=dict(size=9, color=GRIS_MEDIO)),
        yaxis=dict(title='modalidad contratacion', showgrid=False, tickfont=dict(size=9, color=GRIS_OSCURO), automargin=True),
        plot_bgcolor=BLANCO, paper_bgcolor=BLANCO,
        margin=dict(l=0, r=15, t=10, b=35), height=400, bargap=0.25,
        legend=dict(orientation='h', yanchor='top', y=-0.12, xanchor='center', x=0.5, font=dict(size=9, color=GRIS_MEDIO), bgcolor='rgba(0,0,0,0)'),
    )
    return fig


def build_fig3(df_filtered):
    """Viz 3: Treemap proveedores baja competencia (azul)."""
    df_baja = df_filtered[df_filtered['baja_competencia'] == 1].copy()
    df_baja = df_baja[df_baja['nombre_del_proveedor'].notna()]
    df_baja = df_baja[df_baja['nombre_del_proveedor'] != 'No Definido']
    top_prov = df_baja.groupby('nombre_del_proveedor').agg(
        ppto=('valor_total_adjudicacion', 'sum'),
        n=('valor_total_adjudicacion', 'count')
    ).reset_index().sort_values('ppto', ascending=False).head(20)

    def fmt_milm(v):
        if v >= 1e9: return f"{v/1e9:,.0f} mil M"
        if v >= 1e6: return f"{v/1e6:,.0f} M"
        return f"${v:,.0f}"

    top_prov['ppto_fmt'] = top_prov['ppto'].apply(fmt_milm)

    labels = ['Proveedores'] + top_prov['nombre_del_proveedor'].tolist()
    parents = [''] + ['Proveedores'] * len(top_prov)
    values = [0] + top_prov['ppto'].tolist()
    custom_fmt = [''] + top_prov['ppto_fmt'].tolist()

    SCALE = [[0,'#EFF3FF'],[0.25,'#BDD7E7'],[0.5,'#6BAED6'],[0.75,'#3182BD'],[1,'#08519C']]

    fig = go.Figure(go.Treemap(
        labels=labels, values=values, parents=parents,
        marker=dict(colors=[0] + top_prov['ppto'].tolist(), colorscale=SCALE, line=dict(width=1, color=BLANCO)),
        texttemplate='<b>%{label}</b><br>%{customdata}',
        customdata=custom_fmt,
        hovertemplate='<b>%{label}</b><br>%{customdata}<extra></extra>',
        textfont=dict(size=10), insidetextfont=dict(color='#0f172a'),
        pathbar=dict(visible=True),
    ))
    fig.update_layout(paper_bgcolor=BLANCO, margin=dict(l=0, r=0, t=10, b=0), height=400)
    return fig, df_baja


def build_fig4(df_filtered):
    """Viz 4: Barras horizontales Top 15 entidades baja competencia."""
    df_baja_ent = df_filtered[df_filtered['baja_competencia'] == 1].copy()
    top_ent = df_baja_ent.groupby('entidad').agg(
        ppto=('valor_total_adjudicacion', 'sum'),
        n=('valor_total_adjudicacion', 'count')
    ).reset_index().sort_values('ppto', ascending=False).head(15)
    top_ent['ppto_fmt'] = top_ent['ppto'].apply(lambda v: f"${v/1e9:,.0f} mil M" if v >= 1e9 else f"${v/1e6:,.0f} M")
    top_ent = top_ent.sort_values('ppto', ascending=True)

    top_bar = top_ent.tail(1)
    rest_bars = top_ent.head(len(top_ent) - 1)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=rest_bars['entidad'], x=rest_bars['ppto'], orientation='h',
        marker=dict(color='#6BAED6', line=dict(width=0)),
        text=rest_bars['ppto_fmt'], textposition='outside',
        textfont=dict(size=9, color=GRIS_MEDIO),
        hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>', showlegend=False,
    ))
    fig.add_trace(go.Bar(
        y=top_bar['entidad'], x=top_bar['ppto'], orientation='h',
        marker=dict(color='#6BAED6', line=dict(width=0)),
        text=top_bar['ppto_fmt'], textposition='inside', insidetextanchor='end',
        textfont=dict(size=9, color='white', family='Arial Black'),
        hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>', showlegend=False,
    ))
    fig.update_layout(
        barmode='stack',
        xaxis=dict(visible=False, showgrid=False),
        yaxis=dict(title='Entidad', showgrid=False, tickfont=dict(size=9, color=GRIS_OSCURO), automargin=True),
        plot_bgcolor=BLANCO, paper_bgcolor=BLANCO,
        margin=dict(l=0, r=80, t=10, b=10), height=420, showlegend=False,
    )
    return fig
