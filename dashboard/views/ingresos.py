import plotly.graph_objects as go
import streamlit as st

from core import charts, data, metrics

f = data.get_filters()
st.title('Ingresos')
f.subtitle('Métricas 4.2 (MRR) y 4.3 (ARPPU)')

dim = st.selectbox('Agrupar por', list(data.DIMS), format_func=data.DIMS.get, key='ing_dim')
snap = metrics.snapshot(f, dim)
if snap.empty:
    charts.empty_state()
    st.stop()

order = [v for v in data.dim_values(dim) if v in set(snap['segment'])]
cmap = charts.color_map(data.dim_values(dim))
snap['mes'] = snap['month'].map(data.month_short) + snap['parcial'].map({True: '*', False: ''}).fillna('')

# ------------------------------------------------------------------------------------------
st.subheader(f'MRR mensual por {data.DIMS[dim].lower()}')
fig = go.Figure()
for seg in order:
    sub = snap[snap['segment'] == seg]
    fig.add_bar(x=sub['mes'], y=sub['mrr'], name=seg, marker_color=cmap[seg], marker_line_width=0,
                hovertemplate=f'{seg}: US$ %{{y:,.0f}}<extra></extra>')
fig.update_layout(barmode='stack')
charts.layout(fig, height=380, y_title='MRR (USD)')
charts.show(fig, snap.pivot(index='month', columns='segment', values='mrr').round(0).reset_index(), key='ing_mrr',
            caption=f'MRR en USD por mes, apilado por {data.DIMS[dim].lower()}. Cada barra es el snapshot del '
                    'último día del mes (* = mes parcial).')

# ------------------------------------------------------------------------------------------
st.subheader(f'ARPPU por {data.DIMS[dim].lower()}')
fig = go.Figure()
for seg in order:
    sub = snap[snap['segment'] == seg]
    fig.add_scatter(x=sub['mes'], y=sub['arppu'], name=seg, mode='lines+markers',
                    line=dict(color=cmap[seg], width=2), marker=dict(size=8),
                    hovertemplate=f'{seg}: US$ %{{y:,.2f}}<extra></extra>')
charts.layout(fig, height=360, y_title='ARPPU (USD)')
charts.show(fig, snap.pivot(index='month', columns='segment', values='arppu').round(2).reset_index(),
            key='ing_arppu', caption=f'Ingreso promedio por usuario pagador (MRR / usuarios con MRR > 0) por '
                                     f'{data.DIMS[dim].lower()}, en el snapshot de cada mes.')

# ------------------------------------------------------------------------------------------
st.subheader('MRR en moneda local')
loc = metrics.mrr_local(f)
loc = loc[loc['mrr_local'] > 0]
if loc.empty:
    charts.empty_state()
else:
    groups = list(loc.groupby(['country_iso', 'currency']).groups)
    cols = st.columns(min(len(groups), 4))
    for i, (country, cur) in enumerate(groups):
        sub = loc[(loc['country_iso'] == country) & (loc['currency'] == cur)]
        fig = go.Figure(go.Scatter(x=sub['month'].map(data.month_short), y=sub['mrr_local'], mode='lines+markers',
                                   line=dict(color=charts.highlight(), width=2), marker=dict(size=8),
                                   hovertemplate=f'{cur} %{{y:,.0f}}<extra></extra>'))
        charts.layout(fig, height=260, y_title=cur, legend=False)
        ticks = sub['month'].map(data.month_short).tolist()
        fig.update_xaxes(tickangle=0, tickmode='array', tickvals=ticks[::2])  # uno por medio: el gráfico es angosto
        with cols[i % len(cols)]:
            st.markdown(f'**{country} · {cur}**')
            charts.show(fig, sub[['month', 'mrr_local']], key=f'ing_local_{country}_{cur}')
    charts.figure_caption('MRR mensual en la moneda en que se cobra, sin convertir: aísla el efecto del tipo de '
                          'cambio. Un gráfico por país y moneda, cada uno con su propia escala.')

# ------------------------------------------------------------------------------------------
st.subheader('MRR diario')
dd = metrics.daily(f)
fig = go.Figure(go.Scatter(x=dd['d'], y=dd['mrr'], mode='lines', line=dict(color=charts.highlight(), width=2),
                           hovertemplate='US$ %{y:,.0f}<extra></extra>'))
charts.daily_axis(charts.layout(fig, height=280, y_title='MRR (USD)', legend=False))
charts.mark_events(fig, data.eventos_clave(), f.start, f.end)
charts.show(fig, dd[['d', 'mrr']].rename(columns={'d': 'fecha', 'mrr': 'mrr_usd'}), key='ing_diario',
            caption='MRR en USD de todos los planes activos cada día. Línea continua: fin de convenio; punteada: '
                    'migración de catálogo (ver Resumen).')
