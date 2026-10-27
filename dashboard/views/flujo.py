import plotly.graph_objects as go
import streamlit as st

from core import charts, data, metrics

f = data.get_filters()
st.title('Flujo de clientes')
st.caption('Actividad 3.1 · ' + f.describe())

ab = data.apply_event_filters(data.altas_bajas(), f)

c1, c2 = st.columns([1, 2])
gran = c1.segmented_control('Granularidad', ['Día', 'Semana', 'Mes'], default='Semana', key='flujo_gran')
dim = c2.selectbox('Bajas orgánicas por', list(data.DIMS), format_func=data.DIMS.get, key='flujo_dim')
freq = {'Día': 'D', 'Semana': 'W', 'Mes': 'M'}[gran or 'Semana']


def bucket(s):
    return s.dt.to_period(freq).dt.start_time


ALTAS = ['Alta nueva', 'Reactivación']
BAJAS = ['Baja sin retorno', 'Baja con retorno', 'Baja masiva']
ORGANICAS = ['Baja sin retorno', 'Baja con retorno']
hidden = {'Baja masiva'} if f.excluir_masivos else set()

svc = ab[ab['clase'].isin(ALTAS + BAJAS) & ~ab['clase'].isin(hidden)]
if svc.empty:
    charts.empty_state()
    st.stop()

# ------------------------------------------------------------------------------------------
st.subheader('Altas y bajas')
st.caption('Altas hacia arriba, bajas hacia abajo. La intermitencia es parte del negocio: cada salto, aunque sea de un '
           'día, es una baja y una reactivación. Rayadas, las bajas de usuarios que volvieron dentro de la ventana '
           '(las más recientes tuvieron menos tiempo para volver). Las masivas son fines de convenio B2B; ocultarlas '
           'rompe el cuadre con los activos.')
counts = svc.assign(periodo=bucket(svc['date'])).groupby(['periodo', 'clase']).size().rename('eventos').reset_index()
colors = charts.flow_colors()
fig = go.Figure()
for clase in ALTAS + BAJAS:
    sub = counts[counts['clase'] == clase]
    if sub.empty:
        continue
    sign = -1 if clase in BAJAS else 1
    fig.add_bar(x=sub['periodo'], y=sign * sub['eventos'], name=clase, marker_color=colors[clase],
                marker_line_width=0, marker_pattern=charts.hatch(clase), customdata=sub['eventos'],
                hovertemplate=f'{clase}: %{{customdata:,.0f}}<extra></extra>')
fig.update_layout(barmode='relative')
charts.daily_axis(charts.layout(fig, height=380, y_title='Eventos'))
charts.show(fig, counts.pivot(index='periodo', columns='clase', values='eventos').fillna(0).astype(int)
            .reset_index(), key='flujo_eventos')

# ------------------------------------------------------------------------------------------
st.subheader('Usuarios activos')
dd = metrics.daily(f)
fig = go.Figure(go.Scatter(x=dd['d'], y=dd['activos'], mode='lines', line=dict(color=charts.slot(1), width=2),
                           hovertemplate='%{y:,.0f} usuarios<extra></extra>'))
charts.daily_axis(charts.layout(fig, height=260, y_title='Usuarios', legend=False))
charts.mark_events(fig, data.eventos_clave(), f.start, f.end)
charts.show(fig, dd[['d', 'activos']].rename(columns={'d': 'fecha'}), key='flujo_activos')

# ------------------------------------------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader(f'Bajas orgánicas por {data.DIMS[dim].lower()}')
    br = ab[ab['clase'].isin(ORGANICAS)]
    if br.empty:
        charts.empty_state()
    else:
        g = br.assign(mes=br['date'].dt.strftime('%Y-%m')).groupby(['mes', f'c_{dim}']).size().rename('bajas')
        g = g.reset_index().rename(columns={f'c_{dim}': 'segmento'})
        cmap = charts.color_map(data.dim_values(dim))
        fig = go.Figure()
        for segv in [v for v in data.dim_values(dim) if v in set(g['segmento'])]:
            sub = g[g['segmento'] == segv]
            fig.add_bar(x=sub['mes'].map(data.month_short), y=sub['bajas'], name=segv, marker_color=cmap[segv],
                        marker_line_width=0, hovertemplate=f'{segv}: %{{y:,.0f}}<extra></extra>')
        fig.update_layout(barmode='stack')
        charts.layout(fig, height=340, y_title='Bajas orgánicas')
        charts.show(fig, g.pivot(index='mes', columns='segmento', values='bajas').fillna(0).astype(int).reset_index(),
                    key='flujo_bajas_dim', caption='Sin fines de convenio. Incluye las bajas con y sin retorno.')
with right:
    st.subheader('Addons con el usuario activo')
    ad = ab[ab['clase'].isin(['Alta addon', 'Baja addon'])]
    if ad.empty:
        charts.empty_state()
    else:
        g = ad.assign(mes=ad['date'].dt.strftime('%Y-%m')).groupby(['mes', 'clase']).size().rename('eventos').reset_index()
        fig = go.Figure()
        for clase in ['Alta addon', 'Baja addon']:
            sub = g[g['clase'] == clase]
            sign = -1 if clase == 'Baja addon' else 1
            fig.add_bar(x=sub['mes'].map(data.month_short), y=sign * sub['eventos'], name=clase,
                        marker_color=colors[clase], marker_line_width=0, customdata=sub['eventos'],
                        hovertemplate=f'{clase}: %{{customdata:,.0f}}<extra></extra>')
        fig.update_layout(barmode='relative')
        charts.layout(fig, height=340, y_title='Eventos')
        charts.show(fig, g.pivot(index='mes', columns='clase', values='eventos').fillna(0).astype(int).reset_index(),
                    key='flujo_addons')

with st.expander('Detalle de eventos (df_altas_bajas filtrado)'):
    cols = ['date', 'id', 'event_type', 'clase', 'gap_days', 'package_name', 'category', 'country_iso',
            'original_price', 'mrr_usd', 'addons', 'partner_id']
    st.dataframe(ab[cols].sort_values('date'), hide_index=True, width='stretch')
    st.download_button('Descargar CSV', ab[cols].to_csv(index=False).encode('utf-8'), 'altas_bajas.csv', 'text/csv')
