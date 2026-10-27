import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import charts, data

f = data.get_filters()
st.title('Reactivaciones')
st.caption('Actividad 3.2 · ' + f.describe())

r = data.apply_event_filters(data.reactivaciones(), f)
if r.empty:
    charts.empty_state()
    st.stop()

dentro = r[r['origen'] == 'dentro_ventana']
where, params = f.sql()
activos = data.query(f'SELECT count(DISTINCT id) AS n FROM ud WHERE {where}', params)['n'].iloc[0]
por_usuario = dentro.groupby('id').size()

cols = st.columns(5)
cols[0].metric('Reactivaciones', charts.fmt_int(len(r)), border=True,
               help='Altas de usuarios que ya habían tenido un plan.')
cols[1].metric('Intermitentes', charts.fmt_pct(len(por_usuario) / activos) if activos else '—',
               border=True, help='Fracción de los usuarios activos en el período que se fueron y volvieron al menos una vez dentro de '
                                 'la ventana observada.')
cols[2].metric('Días fuera (mediana)', charts.fmt_int(dentro['gap_days'].median()) if len(dentro) else '—',
               border=True, help='Días sin plan antes de volver, en las reactivaciones dentro de la ventana.')
cols[3].metric('Mismo plan', charts.fmt_pct(dentro['mismo_plan'].mean()) if len(dentro) else '—',
               border=True, help='Vuelven al mismo plan, entre las reactivaciones con último plan observable.')
cols[4].metric('MRR reactivado (USD)', charts.fmt_int(r['new_mrr_usd'].sum()), border=True,
               help='MRR mensual (USD) de las reactivaciones, con el plan con el que vuelven.')

# ------------------------------------------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader('Días fuera antes de volver')
    gaps = dentro['gap_days'].dropna()
    cap = 60
    binned = np.where(gaps > cap, cap + 1, gaps).astype(int)
    hist = pd.Series(binned).value_counts().sort_index()
    labels = [str(d) if d <= cap else f'>{cap}' for d in hist.index]
    fig = go.Figure(go.Bar(
        x=hist.index, y=hist.values, marker_line_width=0, marker_color=charts.highlight(),
        customdata=labels, hovertemplate='%{customdata} días: %{y:,.0f}<extra></extra>'))
    charts.layout(fig, height=340, y_title='Reactivaciones', x_title='Días sin plan', legend=False,
                  hovermode='closest')
    fig.update_xaxes(tickvals=[1, 3, 7, 14, 30, 45, cap + 1], ticktext=['1', '3', '7', '14', '30', '45', f'>{cap}'],
                     tickangle=0)
    charts.show(fig, pd.DataFrame({'dias_fuera': labels, 'reactivaciones': hist.values}), key='react_gap',
                caption='Solo reactivaciones dentro de la ventana observada. La mayoría vuelve en pocos días: '
                        'la intermitencia es parte del comportamiento del rubro.')
with right:
    st.subheader('Reactivaciones por usuario')
    if por_usuario.empty:
        charts.empty_state()
    else:
        ciclos = por_usuario.clip(upper=5).value_counts().sort_index()
        etiquetas = [str(k) if k < 5 else '5+' for k in ciclos.index]
        fig = go.Figure(go.Bar(
            x=etiquetas, y=ciclos.values, marker_line_width=0, marker_color=charts.highlight(),
            hovertemplate='%{x} reactivaciones: %{y:,.0f} usuarios<extra></extra>'))
        charts.layout(fig, height=340, y_title='Usuarios', x_title='Veces que salió y volvió', legend=False,
                      hovermode='closest')
        fig.update_xaxes(type='category')  # si no, Plotly trata el eje como numérico y descarta '5+'
        charts.show(fig, pd.DataFrame({'reactivaciones': etiquetas, 'usuarios': ciclos.values}), key='react_ciclos',
                    caption='Usuarios intermitentes según cuántas veces volvieron dentro del período.')

# ------------------------------------------------------------------------------------------
st.subheader('Reactivaciones por mes')
ORIGEN = {'dentro_ventana': 'Último plan observado', 'previo_ventana': 'Historial previo a 2026'}
g = (r.assign(mes=r['date'].dt.strftime('%Y-%m'), origen_lbl=r['origen'].map(ORIGEN))
     .groupby(['mes', 'origen_lbl']).size().rename('reactivaciones').reset_index())
color = {'Último plan observado': charts.slot(1), 'Historial previo a 2026': charts.slot(2)}
fig = go.Figure()
for lbl in ORIGEN.values():
    sub = g[g['origen_lbl'] == lbl]
    if not sub.empty:
        fig.add_bar(x=sub['mes'].map(data.month_short), y=sub['reactivaciones'], name=lbl,
                    marker_color=color[lbl], marker_line_width=0,
                    hovertemplate=f'{lbl}: %{{y:,.0f}}<extra></extra>')
fig.update_layout(barmode='stack')
charts.layout(fig, height=320, y_title='Reactivaciones')
charts.show(fig, g.pivot(index='mes', columns='origen_lbl', values='reactivaciones').fillna(0).astype(int)
            .reset_index(), key='react_mes',
            caption='"Historial previo a 2026": su primera aparición es una vuelta, pero su último plan no es observable.')

# ------------------------------------------------------------------------------------------
st.subheader('Con qué plan se fueron y con cuál volvieron')
st.caption('Reactivaciones dentro de la ventana. Se muestran los 12 pares más frecuentes: en rosa, los que cambian '
           'de plan; en gris, los que vuelven al mismo.')
pairs = (dentro.groupby(['last_package_name', 'new_package_name']).size().rename('n').reset_index()
         .sort_values('n', ascending=False).head(12))
if pairs.empty:
    charts.empty_state()
else:
    src_nodes = list(dict.fromkeys(pairs['last_package_name']))
    dst_nodes = list(dict.fromkeys(pairs['new_package_name']))
    labels = [f'{p} (antes)' for p in src_nodes] + [f'{p} (ahora)' for p in dst_nodes]
    same = pairs['last_package_name'] == pairs['new_package_name']
    link_color = np.where(same, charts.rgba(charts.context(), 0.45), charts.rgba(charts.highlight(), 0.45))
    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=14, thickness=12, color=charts.ink('axis'), line=dict(width=0)),
        textfont=charts.sankey_font(),
        link=dict(source=[src_nodes.index(p) for p in pairs['last_package_name']],
                  target=[len(src_nodes) + dst_nodes.index(p) for p in pairs['new_package_name']],
                  value=pairs['n'], color=link_color,
                  hovertemplate='%{source.label} → %{target.label}: %{value:,.0f}<extra></extra>')))
    fig.update_layout(height=420, margin=dict(l=8, r=8, t=8, b=8), separators=',.',
                      font=dict(family=charts.FONT))
    charts.show(fig, pairs.rename(columns={'last_package_name': 'plan_anterior', 'new_package_name': 'plan_nuevo',
                                           'n': 'reactivaciones'}), key='react_sankey')

with st.expander('Detalle de reactivaciones (df_reactivaciones filtrado)'):
    cols_ = ['date', 'id', 'origen', 'gap_days', 'mismo_plan', 'last_package_name', 'last_mrr_usd',
             'new_package_name', 'new_mrr_usd', 'delta_mrr_usd', 'new_country_iso']
    st.dataframe(r[cols_].sort_values('date'), hide_index=True, width='stretch')
