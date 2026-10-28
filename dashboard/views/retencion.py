import plotly.graph_objects as go
import streamlit as st

from core import charts, data, metrics

f = data.get_filters()
st.title('Retención')
f.subtitle('Métricas 4.1, 4.5 y 4.6')

# ------------------------------------------------------------------------------------------
st.subheader('Usuarios por antigüedad (4.1)')
ten = metrics.tenure(f)
if ten.empty:
    charts.empty_state()
else:
    as_pct = st.toggle('Ver como % de la base', value=True, key='ret_pct')
    tot = ten.groupby('month')['usuarios'].transform('sum')
    ten['valor'] = ten['usuarios'] / tot if as_pct else ten['usuarios']
    fig = go.Figure()
    for bucket, color in zip(data.TENURE_ORDER, charts.ordinal()):
        sub = ten[ten['tenure_bucket'] == bucket]
        if not sub.empty:
            fig.add_bar(x=sub['month'].map(data.month_short), y=sub['valor'], name=bucket, marker_color=color,
                        marker_line_width=0, customdata=sub['usuarios'],
                        hovertemplate=f'{bucket}: %{{y:{".1%" if as_pct else ",.0f"}}} (%{{customdata:,.0f}})<extra></extra>')
    fig.update_layout(barmode='stack')
    charts.layout(fig, height=340, y_title='% de usuarios' if as_pct else 'Usuarios',
                  y_format='.0%' if as_pct else None)
    charts.show(fig, ten.pivot(index='month', columns='tenure_bucket', values='usuarios')
                .reindex(columns=data.TENURE_ORDER).reset_index(), key='ret_tenure',
                caption='Composición de los usuarios activos al cierre de cada mes por antigüedad, medida desde '
                        'la creación de su primer plan observado (proxy de created_user). Más oscuro, más reciente.')

# ------------------------------------------------------------------------------------------
st.subheader('Tasa de churn (4.6)')
c1, c2 = st.columns([1, 2])
horizonte = c1.segmented_control('Horizonte', ['1M', '3M', '6M'], default='1M', key='ret_hor') or '1M'
# El churn está precalculado en el notebook por dimensión; el perfil (actividad 6) no está entre ellas
churn_dims = [d for d in data.DIMS if d in set(data.metricas()['dimension'])]
dim = c2.selectbox('Agrupar por', ['total'] + churn_dims,
                   format_func=lambda d: 'Total' if d == 'total' else data.DIMS[d], key='ret_dim')
st.caption(('**Churn orgánico** (sin bajas masivas por fin de convenio). ' if f.excluir_masivos else
            '**Churn total** (incluye bajas masivas; actívalo en "Excluir eventos masivos" para el orgánico). ')
           + 'Precalculado en el notebook por una dimensión a la vez: los filtros de otras dimensiones no se aplican.')
ch = metrics.churn(f, None if dim == 'total' else dim)
ch = ch[ch['horizonte'] == horizonte]
if ch.empty:
    charts.empty_state('No hay ventanas completas para este horizonte.')
else:
    segs = ['Total'] if dim == 'total' else [v for v in data.dim_values(dim) if v in set(ch['segment'])]
    cmap = {'Total': charts.highlight()} if dim == 'total' else charts.color_map(data.dim_values(dim))
    fig = go.Figure()
    for seg in segs:
        sub = ch[ch['segment'] == seg].sort_values('cohort_month')
        fig.add_scatter(x=sub['cohort_month'].map(data.month_short), y=sub['value'], name=seg, mode='lines+markers',
                        line=dict(color=cmap[seg], width=2), marker=dict(size=8),
                        hovertemplate=f'{seg}: %{{y:.1%}}<extra></extra>')
    charts.layout(fig, height=360, y_title=f'Churn {horizonte}', y_format='.0%', legend=dim != 'total',
                  x_title='Mes de inicio de la cohorte')
    charts.show(fig, ch.pivot(index='cohort_month', columns='segment', values='value').round(4).reset_index(),
                key='ret_churn',
                caption=f'De los usuarios activos el primer día de cada mes, la fracción que se dio de baja dentro '
                        f'de los {horizonte[0]} meses siguientes. Solo se muestran los meses con la ventana completa '
                        'observada.')

# ------------------------------------------------------------------------------------------
st.subheader('Vida media por plan (4.5)')
c1, c2 = st.columns([1, 2])
agr = c1.segmented_control('Agrupar por', ['Plan', 'Categoría'], default='Plan', key='ret_agr') or 'Plan'
col = 'plan_label' if agr == 'Plan' else 'package_category'
vida = data.vida(col).sort_values('spells', ascending=False)
groups = vida[col].tolist()
sel = c2.multiselect('Grupos (máx. 8)', groups, default=groups[:5], max_selections=8, key=f'ret_km_{col}')
curves = data.km_curvas()
curves = curves[curves['agrupacion'] == col]
cmap = charts.color_map(groups)  # color fijo por grupo según su tamaño, no por la selección
fig = go.Figure()
for g in sel:
    sub = curves[curves['grupo'] == g]
    fig.add_scatter(x=sub['dias'], y=sub['supervivencia'], name=g, mode='lines', line=dict(color=cmap[g], width=2,
                    shape='hv'), hovertemplate=f'{g}: %{{y:.1%}} a los %{{x:.0f}} días<extra></extra>')
fig.add_hline(y=0.5, line_width=1, line_color=charts.ink('muted'))
charts.layout(fig, height=400, y_title='Fracción que sigue en el plan', y_format='.0%', x_title='Días en el plan',
              hovermode='closest')
fig.update_yaxes(range=[0, 1.02])
fig.update_xaxes(range=[0, 730])
cols_v = [col, 'spells', 'usuarios', 'pct_censurado', 'mediana_km_dias', 'rmst_365_dias', 'media_cerrados_dias',
          'metodo']
charts.show(fig, vida[cols_v], key='ret_km',
            caption='Fracción de los usuarios que sigue en cada plan según los días transcurridos desde que lo '
                    'contrató. Curvas de Kaplan–Meier con entrada tardía. Se censuran los planes que siguen activos y los que '
                    'terminan por migración masiva o fin de convenio. La mediana es donde la curva cruza la línea del 50%.')

# ------------------------------------------------------------------------------------------
st.subheader('Retención de usuarios nuevos')
ret = data.retencion_nuevos()
ks = [c for c in ret.columns if c != 'usuarios_nuevos']
z = ret[ks].values
fig = go.Figure(go.Heatmap(
    z=z, x=[f'Mes {k}' for k in ks], y=[f'{data.month_label(i)} ({n:,})'.replace(',', '.') for i, n in
                                         zip(ret.index, ret['usuarios_nuevos'])],
    zmin=0, zmax=1, colorscale=charts.sequential_scale(),
    text=[[charts.fmt_pct(v, 0) if v == v else '' for v in row] for row in z], texttemplate='%{text}',
    xgap=2, ygap=2, hovertemplate='%{y} · %{x}: %{z:.1%}<extra></extra>',
    colorbar=dict(tickformat='.0%', thickness=10)))
charts.layout(fig, height=400, legend=False, hovermode='closest', x_title='Meses desde la primera alta')
fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
charts.show(fig, ret.reset_index(), key='ret_cohortes',
            caption='Fracción de cada cohorte (mes de primera alta, entre paréntesis su tamaño) con algún día activo '
                    'k meses después. No depende de los filtros laterales.')
