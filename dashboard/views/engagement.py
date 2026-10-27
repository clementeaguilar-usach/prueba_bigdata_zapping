import plotly.graph_objects as go
import streamlit as st

from core import charts, data, metrics

f = data.get_filters()
st.title('Engagement')
st.caption('Métrica 4.4 (MAU) · ' + f.describe())
st.caption('`time_watched` son los segundos de consumo de los últimos 30 días. El MAU cuenta a los activos al '
           'cierre de cada mes con consumo en esos 30 días; septiembre es parcial (cierre el 07-09).')

tot = metrics.mau(f)
if tot.empty:
    charts.empty_state()
    st.stop()
tot['mes'] = tot['month'].map(data.month_short)

left, right = st.columns(2)
with left:
    st.subheader('MAU y suscriptores')
    fig = go.Figure()
    fig.add_scatter(x=tot['mes'], y=tot['suscriptores'], name='Suscriptores al cierre', mode='lines+markers',
                    line=dict(color=charts.context(), width=2), marker=dict(size=8),
                    hovertemplate='Suscriptores: %{y:,.0f}<extra></extra>')
    fig.add_scatter(x=tot['mes'], y=tot['mau'], name='MAU (vieron en 30 días)', mode='lines+markers',
                    line=dict(color=charts.highlight(), width=2), marker=dict(size=8),
                    hovertemplate='MAU: %{y:,.0f}<extra></extra>')
    charts.layout(fig, height=340, y_title='Usuarios')
    charts.show(fig, tot[['month', 'suscriptores', 'mau']], key='eng_mau')
with right:
    st.subheader('MAU / suscriptores')
    fig = go.Figure(go.Scatter(x=tot['mes'], y=tot['ratio'], mode='lines+markers',
                               line=dict(color=charts.highlight(), width=2), marker=dict(size=8),
                               hovertemplate='%{y:.1%}<extra></extra>'))
    charts.layout(fig, height=340, y_title='Fracción que vio contenido', y_format='.0%', legend=False)
    fig.update_yaxes(range=[0, 1])
    charts.show(fig, tot[['month', 'ratio']].round(3), key='eng_ratio')

# ------------------------------------------------------------------------------------------
st.subheader('Consumo diario')
dd = metrics.engagement_daily(f)
left, right = st.columns(2)
with left:
    st.markdown('**Activos con consumo en los últimos 30 días**')
    fig = go.Figure(go.Scatter(x=dd['d'], y=dd['ratio'], mode='lines', line=dict(color=charts.highlight(), width=2),
                               customdata=dd['activos'],
                               hovertemplate='%{y:.1%} de %{customdata:,.0f} activos<extra></extra>'))
    charts.daily_axis(charts.layout(fig, height=280, y_title='Fracción de activos', y_format='.0%', legend=False))
    fig.update_yaxes(range=[0, 1])
    charts.mark_events(fig, data.eventos_clave(), f.start, f.end)
    charts.show(fig, dd[['d', 'activos', 'con_consumo', 'ratio']].round(3).rename(columns={'d': 'fecha'}),
                key='eng_diario')
with right:
    st.markdown('**Horas de consumo en 30 días (mediana de quienes ven)**')
    fig = go.Figure(go.Scatter(x=dd['d'], y=dd['horas_mediana'], mode='lines',
                               line=dict(color=charts.highlight(), width=2),
                               hovertemplate='%{y:,.1f} horas<extra></extra>'))
    charts.daily_axis(charts.layout(fig, height=280, y_title='Horas', legend=False))
    charts.mark_events(fig, data.eventos_clave(), f.start, f.end)
    charts.show(fig, dd[['d', 'horas_mediana']].round(1).rename(columns={'d': 'fecha'}), key='eng_horas',
                caption='Mediana y no promedio: algunas cuentas superan las 720 horas en 30 días (pantallas simultáneas).')

# ------------------------------------------------------------------------------------------
dim = st.selectbox('Agrupar por', list(data.DIMS), format_func=data.DIMS.get, index=2, key='eng_dim')
st.subheader(f'MAU / suscriptores por {data.DIMS[dim].lower()}')
by = metrics.mau(f, dim)
order = [v for v in data.dim_values(dim) if v in set(by['segment'])]
mat = by.pivot(index='segment', columns='month', values='ratio').reindex(order)
subs = by.pivot(index='segment', columns='month', values='suscriptores').reindex(order)
fig = go.Figure(go.Heatmap(
    z=mat.values, x=[data.month_short(m) for m in mat.columns], y=mat.index, zmin=0, zmax=1,
    colorscale=charts.sequential_scale(),
    text=[[charts.fmt_pct(v, 0) if v == v else '' for v in row] for row in mat.values], texttemplate='%{text}',
    customdata=subs.values, xgap=2, ygap=2,
    hovertemplate='%{y} · %{x}<br>%{z:.1%} de %{customdata:,.0f} suscriptores<extra></extra>',
    colorbar=dict(tickformat='.0%', thickness=10)))
charts.layout(fig, height=max(260, 46 * len(order) + 80), legend=False, hovermode='closest')
fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
charts.show(fig, by[['month', 'segment', 'suscriptores', 'mau', 'ratio']].round(3), key='eng_heat',
            caption='Segmentos con pocos suscriptores (ver tabla) dan tasas inestables. '
                    'B2B suele tener menos engagement: el servicio viene incluido en un paquete del partner.')
