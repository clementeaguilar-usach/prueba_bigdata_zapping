import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core import charts, data

f = data.get_filters()
st.title('Cambios de plan')
st.caption('Actividad 3.3 · ' + f.describe())

c_all = data.apply_event_filters(data.cambios_plan(), f)
c = c_all[~c_all['migracion_masiva']] if f.excluir_masivos else c_all
if c.empty:
    charts.empty_state()
    st.stop()

TIPOS = ['upgrade', 'downgrade', 'lateral', 'reajuste_precio']
counts = c['tipo'].value_counts()
cols = st.columns(5)
for col, tipo in zip(cols, TIPOS):
    col.metric(charts.TIPO_LABELS[tipo], charts.fmt_int(counts.get(tipo, 0)), border=True)
cols[4].metric('Migraciones masivas', charts.fmt_pct(c_all['migracion_masiva'].mean()), border=True,
               help='Fracción de los cambios que ocurren en volúmenes atípicos (decisión de Zapping o del '
                    'partner, no del usuario). Se calcula sobre todos los cambios.')
if not f.excluir_masivos:
    st.caption('Incluye migraciones masivas de catálogo. Actívalo en "Excluir eventos masivos" para ver solo '
               'decisiones individuales.')

# ------------------------------------------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader('Cambios por mes y tipo')
    g = c.assign(mes=c['date'].dt.strftime('%Y-%m')).groupby(['mes', 'tipo']).size().rename('cambios').reset_index()
    colors = charts.tipo_colors()
    fig = go.Figure()
    for tipo in TIPOS:
        sub = g[g['tipo'] == tipo]
        if not sub.empty:
            fig.add_bar(x=sub['mes'].map(data.month_short), y=sub['cambios'], name=charts.TIPO_LABELS[tipo],
                        marker_color=colors[tipo], marker_line_width=0,
                        hovertemplate=f'{charts.TIPO_LABELS[tipo]}: %{{y:,.0f}}<extra></extra>')
    fig.update_layout(barmode='stack')
    charts.layout(fig, height=360, y_title='Cambios de plan')
    charts.show(fig, g.pivot(index='mes', columns='tipo', values='cambios').fillna(0).astype(int).reset_index(),
                key='cambios_mes')
with right:
    st.subheader('Impacto neto en MRR')
    net = c.assign(mes=c['date'].dt.strftime('%Y-%m')).groupby('mes')['delta_mrr_usd'].sum().reset_index()
    pos, neg = charts.slot(1), charts.slot(3)  # mismos colores que upgrade / downgrade
    fig = go.Figure(go.Bar(x=net['mes'].map(data.month_short), y=net['delta_mrr_usd'], marker_line_width=0,
                           marker_color=np.where(net['delta_mrr_usd'] >= 0, pos, neg),
                           hovertemplate='US$ %{y:,.0f}<extra></extra>'))
    charts.layout(fig, height=360, y_title='Δ MRR (USD)', legend=False)
    charts.show(fig, net.rename(columns={'delta_mrr_usd': 'delta_mrr_usd_neto'}), key='cambios_mrr',
                caption='Suma de la diferencia de MRR entre el plan nuevo y el anterior. Índigo: el MRR sube; fucsia: baja.')

# ------------------------------------------------------------------------------------------
st.subheader('Desde qué plan hacia cuál')
st.caption('Los 15 pares más frecuentes. El color del flujo indica el tipo de cambio.')
pairs = (c.groupby(['prev_package_name', 'new_package_name', 'tipo']).size().rename('n').reset_index()
         .sort_values('n', ascending=False).head(15))
src_nodes = list(dict.fromkeys(pairs['prev_package_name']))
dst_nodes = list(dict.fromkeys(pairs['new_package_name']))
labels = [f'{p} (antes)' for p in src_nodes] + [f'{p} (después)' for p in dst_nodes]
fig = go.Figure(go.Sankey(
    node=dict(label=labels, pad=14, thickness=12, color=charts.ink('axis'), line=dict(width=0)),
    textfont=charts.sankey_font(),
    link=dict(source=[src_nodes.index(p) for p in pairs['prev_package_name']],
              target=[len(src_nodes) + dst_nodes.index(p) for p in pairs['new_package_name']],
              value=pairs['n'], color=[charts.rgba(charts.tipo_colors()[t], 0.4) for t in pairs['tipo']],
              customdata=[charts.TIPO_LABELS[t] for t in pairs['tipo']],
              hovertemplate='%{source.label} → %{target.label}<br>%{customdata}: %{value:,.0f}<extra></extra>')))
fig.update_layout(height=460, margin=dict(l=8, r=8, t=8, b=8), separators=',.',
                  font=dict(family=charts.FONT))
charts.show(fig, pairs.rename(columns={'prev_package_name': 'plan_anterior', 'new_package_name': 'plan_nuevo',
                                       'n': 'cambios'}), key='cambios_sankey')

with st.expander('Migraciones masivas detectadas'):
    mig = (c_all[c_all['migracion_masiva']]
           .groupby(['date', 'prev_package_name', 'new_package_name', 'tipo']).size().rename('usuarios')
           .reset_index().sort_values('usuarios', ascending=False))
    st.dataframe(mig.assign(date=mig['date'].dt.strftime('%d/%m/%Y')), hide_index=True, width='stretch')

with st.expander('Detalle de cambios (df_cambios_plan filtrado)'):
    cols_ = ['date', 'id', 'country_iso', 'tipo', 'migracion_masiva', 'prev_package_name', 'prev_list_price_usd',
             'new_package_name', 'new_list_price_usd', 'delta_mrr_usd']
    st.dataframe(c[cols_].sort_values('date'), hide_index=True, width='stretch')
