import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import charts, data

f = data.get_filters()
st.title('Reactivaciones')
f.subtitle('Actividad 3.2')

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
                caption='Distribución de los días sin plan entre una baja y la reactivación siguiente (solo '
                        'reactivaciones dentro de la ventana observada; más de 60 días se agrupan al final). La mayoría '
                        'vuelve en pocos días: la intermitencia es parte del comportamiento del rubro.')
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
                    caption='Usuarios intermitentes según cuántas veces se fueron y volvieron dentro del período. '
                            'La mayoría lo hace una sola vez, pero un grupo vuelve 5 o más veces.')

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
            caption='Reactivaciones por mes según su origen. *Último plan observado*: el usuario se fue y volvió '
                    'dentro de la ventana, así que se conoce el plan con que se fue. *Historial previo a 2026*: el '
                    'usuario ya existía antes del 01-01 (su primer plan es anterior) y su primera aparición en los '
                    'datos es una vuelta, pero el plan con que se fue no es observable.')

# ------------------------------------------------------------------------------------------
st.subheader('Con qué plan se fueron y con cuál volvieron')
obs = dentro.dropna(subset=['last_package_name', 'new_package_name']).astype({'mismo_plan': bool})
if obs.empty:
    charts.empty_state()
else:
    top = obs['last_package_name'].value_counts().head(10).index[::-1]  # el más frecuente arriba
    g = (obs.assign(vuelta=np.where(obs['mismo_plan'], 'Vuelve al mismo plan', 'Vuelve con otro plan'))
         .loc[lambda x: x['last_package_name'].isin(top)]
         .groupby(['last_package_name', 'vuelta']).size().unstack(fill_value=0)
         .reindex(index=top, columns=['Vuelve al mismo plan', 'Vuelve con otro plan'], fill_value=0))
    share = g.div(g.sum(axis=1), axis=0)
    color = {'Vuelve al mismo plan': charts.context(), 'Vuelve con otro plan': charts.highlight()}
    fig = go.Figure()
    for lbl in g.columns:
        fig.add_bar(y=g.index, x=g[lbl], name=lbl, orientation='h', marker_color=color[lbl], marker_line_width=0,
                    customdata=share[lbl], hovertemplate=f'{lbl}: %{{x:,.0f}} (%{{customdata:.0%}})<extra></extra>')
    fig.update_layout(barmode='stack')
    charts.layout(fig, height=max(280, 34 * len(top) + 90), x_title='Reactivaciones', hovermode='y unified')
    fig.update_xaxes(showgrid=True, gridcolor=charts.ink('grid'))
    fig.update_yaxes(gridcolor='rgba(0,0,0,0)')
    charts.show(fig, g.reset_index().rename(columns={'last_package_name': 'plan_con_que_se_fue'}), key='react_planes',
                caption='Reactivaciones según el plan que el usuario tenía al irse (los 10 más frecuentes). En gris, '
                        'las que vuelven con el mismo plan; en rosa, las que vuelven con otro. Sin filtros, quien se fue de Esencial o Nacional vuelve casi siempre al '
                        'mismo plan; de Plus o Premium, cerca de la mitad cambia.')

    cambio = obs[~obs['mismo_plan']]
    if not cambio.empty:
        pares = (cambio.groupby(['last_package_name', 'new_package_name']).size().rename('reactivaciones')
                 .reset_index().sort_values('reactivaciones', ascending=False).head(10))
        st.dataframe(pares.rename(columns={'last_package_name': 'Plan con que se fue',
                                           'new_package_name': 'Plan con que volvió',
                                           'reactivaciones': 'Reactivaciones'}),
                     hide_index=True, width='stretch')
        charts.figure_caption('Las 10 combinaciones más frecuentes entre quienes vuelven con un plan distinto al que '
                              'tenían (la parte rosa de la figura anterior).')

with st.expander('Detalle de reactivaciones (df_reactivaciones filtrado)'):
    cols_ = ['date', 'id', 'origen', 'gap_days', 'mismo_plan', 'last_package_name', 'last_mrr_usd',
             'new_package_name', 'new_mrr_usd', 'delta_mrr_usd', 'new_country_iso']
    st.dataframe(r[cols_].sort_values('date'), hide_index=True, width='stretch')
