import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core import charts, data, metrics

f = data.get_filters()
st.title('Flujo de clientes')
f.subtitle('Actividad 3.1')

ab = data.apply_event_filters(data.altas_bajas(), f)

gran = st.segmented_control('Granularidad', ['Semana', 'Mes'], default='Mes', key='flujo_gran') or 'Mes'
freq = {'Semana': 'W', 'Mes': 'M'}[gran]
per_label = gran.lower()


def bucket(s):
    return s.dt.to_period(freq).dt.start_time


ALTAS = ['Alta nueva', 'Reactivación']
BAJAS = ['Baja sin retorno', 'Baja con retorno', 'Baja masiva']
hidden = {'Baja masiva'} if f.excluir_masivos else set()

svc = ab[ab['clase'].isin(ALTAS + BAJAS) & ~ab['clase'].isin(hidden)]
if svc.empty:
    charts.empty_state()
    st.stop()
svc = svc.assign(periodo=bucket(svc['date']), lado=np.where(svc['clase'].isin(ALTAS), 'contrataciones', 'abandonos'))


def add_totals(fig, tot):
    """Total de contrataciones sobre cada barra y de abandonos bajo ella."""
    tot = tot.reindex(columns=['contrataciones', 'abandonos'], fill_value=0)
    style = dict(mode='text', showlegend=False, hoverinfo='skip', cliponaxis=False,
                 textfont=dict(size=10, color=charts.ink('secondary')))
    fig.add_scatter(x=tot.index, y=tot['contrataciones'], text=tot['contrataciones'].map(charts.fmt_int),
                    textposition='top center', **style)
    fig.add_scatter(x=tot.index, y=-tot['abandonos'], text=tot['abandonos'].map(charts.fmt_int),
                    textposition='bottom center', **style)


# ------------------------------------------------------------------------------------------
st.subheader('Altas y bajas')
counts = svc.groupby(['periodo', 'clase']).size().rename('eventos').reset_index()
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
add_totals(fig, svc.groupby(['periodo', 'lado']).size().unstack(fill_value=0))
fig.update_layout(barmode='relative')
charts.daily_axis(charts.layout(fig, height=420, y_title='Eventos'))
charts.show(fig, counts.pivot(index='periodo', columns='clase', values='eventos').fillna(0).astype(int)
            .reset_index(), key='flujo_eventos',
            caption=f'Altas (hacia arriba) y bajas (hacia abajo) del servicio por {per_label}. Sobre cada barra, el '
                    'total de contrataciones (altas nuevas + reactivaciones); bajo ella, el total de abandonos (todas '
                    'las bajas visibles). Cada salto, aunque sea de un día, cuenta como una baja y una reactivación. '
                    '*Baja con retorno*: el usuario volvió dentro de la ventana; *sin retorno* (rayada): no volvió '
                    'antes del 07-09. Las más recientes tuvieron menos tiempo para volver, por eso las sin retorno '
                    'crecen hacia el final. *Baja masiva*: fin de convenio B2B del 12-06.')
n_masivas = int((ab['clase'] == 'Baja masiva').sum())
if n_masivas:
    st.caption(f'{"Están ocultas" if f.excluir_masivos else "Con *Excluir eventos masivos* se ocultan"} las '
               f'{charts.fmt_int(n_masivas)} bajas masivas. Sin ellas, las barras ya no explican toda la variación '
               'de la figura 2: los activos de un día son los del día anterior más las altas y menos las bajas.')

# ------------------------------------------------------------------------------------------
st.subheader('Usuarios activos')
dd = metrics.daily(f)
fig = go.Figure(go.Scatter(x=dd['d'], y=dd['activos'], mode='lines', line=dict(color=charts.highlight(), width=2),
                           hovertemplate='%{y:,.0f} usuarios<extra></extra>'))
charts.daily_axis(charts.layout(fig, height=260, y_title='Usuarios', legend=False))
charts.mark_events(fig, data.eventos_clave(), f.start, f.end, tipos=['Fin de convenio'])
charts.show(fig, dd[['d', 'activos']].rename(columns={'d': 'fecha'}), key='flujo_activos',
            caption='Usuarios con al menos un plan activo cada día: es el saldo acumulado de la figura 1. La línea '
                    'vertical marca el fin de convenio del 12-06.')

# ------------------------------------------------------------------------------------------
st.subheader('Qué planes se contratan y con cuáles se van')
dims = list(data.DIMS)
dim = st.selectbox('Desglosar por', dims, index=dims.index('package_grp'), format_func=data.DIMS.get,
                   key='flujo_dim')
col = f'c_{dim}'
pl = svc.groupby(['periodo', 'lado', col]).size().rename('eventos').reset_index().rename(columns={col: 'segmento'})
order = [v for v in data.dim_values(dim) if v in set(pl['segmento'])]
cmap = charts.color_map(data.dim_values(dim))
fig = go.Figure()
for lado, sign in (('contrataciones', 1), ('abandonos', -1)):
    for segv in order:
        sub = pl[(pl['lado'] == lado) & (pl['segmento'] == segv)]
        if sub.empty:
            continue
        fig.add_bar(x=sub['periodo'], y=sign * sub['eventos'], name=segv, legendgroup=segv,
                    showlegend=lado == 'contrataciones', marker_color=cmap[segv], marker_line_width=0,
                    customdata=sub['eventos'], hovertemplate=f'{segv} · {lado}: %{{customdata:,.0f}}<extra></extra>')
add_totals(fig, svc.groupby(['periodo', 'lado']).size().unstack(fill_value=0))
fig.update_layout(barmode='relative')
charts.daily_axis(charts.layout(fig, height=440, y_title='Eventos'))
tabla = (pl.pivot_table(index=['periodo', 'segmento'], columns='lado', values='eventos', fill_value=0)
         .reindex(columns=['contrataciones', 'abandonos'], fill_value=0).astype(int).reset_index())
charts.show(fig, tabla, key='flujo_planes',
            caption=f'Las mismas altas y bajas de la figura 1, según {data.DIMS[dim].lower()}. Arriba, las '
                    'contrataciones con el plan contratado ese día; abajo, los abandonos con el plan que el usuario '
                    'tenía su último día activo. Cada segmento conserva su color arriba y abajo.')

resumen = (pl.pivot_table(index='segmento', columns='lado', values='eventos', aggfunc='sum', fill_value=0)
           .reindex(columns=['contrataciones', 'abandonos'], fill_value=0).reindex(order))
resumen['neto'] = resumen['contrataciones'] - resumen['abandonos']
st.dataframe(resumen.reset_index().rename(columns={'segmento': data.DIMS[dim], 'contrataciones': 'Contrataciones',
                                                    'abandonos': 'Abandonos', 'neto': 'Neto'}),
             hide_index=True, width='stretch')
charts.figure_caption(f'Totales del período por {data.DIMS[dim].lower()}. El neto positivo indica que el segmento '
                      'ganó usuarios por altas y bajas. No incluye los cambios de plan sin salir del servicio (ver '
                      'Cambios de plan).')

# ------------------------------------------------------------------------------------------
st.subheader('Addons contratados y cancelados')
ad = ab[ab['clase'].isin(['Alta addon', 'Baja addon'])]
if ad.empty:
    charts.empty_state()
else:
    g = (ad.assign(mes=ad['date'].dt.strftime('%Y-%m'))
         .groupby(['mes', 'clase', 'package_name']).size().rename('eventos').reset_index())
    addons = g.groupby('package_name')['eventos'].sum().sort_values(ascending=False).index.tolist()
    amap = charts.color_map(addons)
    fig = go.Figure()
    for clase, sign in (('Alta addon', 1), ('Baja addon', -1)):
        for name in addons:
            sub = g[(g['clase'] == clase) & (g['package_name'] == name)]
            if sub.empty:
                continue
            fig.add_bar(x=sub['mes'].map(data.month_short), y=sign * sub['eventos'], name=name, legendgroup=name,
                        showlegend=clase == 'Alta addon', marker_color=amap[name], marker_line_width=0,
                        customdata=sub['eventos'],
                        hovertemplate=f'{name} · {"contratado" if sign > 0 else "cancelado"}: '
                                      '%{customdata:,.0f}<extra></extra>')
    fig.update_layout(barmode='relative')
    charts.layout(fig, height=360, y_title='Eventos')
    fig.update_xaxes(categoryorder='array', categoryarray=[data.month_short(m) for m in sorted(g['mes'].unique())])
    charts.show(fig, g.pivot_table(index=['mes', 'package_name'], columns='clase', values='eventos', fill_value=0)
                .reset_index(), key='flujo_addons',
                caption='Los addons son paquetes que se contratan sobre el plan base (canales deportivos, premium o '
                        'para adultos). Arriba, addons contratados; abajo, cancelados, por mes. Solo cuentan los '
                        'usuarios que ya tenían el servicio el día anterior (contratación) o lo conservan el día '
                        'siguiente (cancelación): los addons que entran o salen junto con el servicio ya están en la '
                        'figura 1.')

with st.expander('Detalle de eventos (df_altas_bajas filtrado)'):
    cols = ['date', 'id', 'event_type', 'clase', 'gap_days', 'package_name', 'category', 'country_iso',
            'original_price', 'mrr_usd', 'addons', 'partner_id']
    st.dataframe(ab[cols].sort_values('date'), hide_index=True, width='stretch')
    st.download_button('Descargar CSV', ab[cols].to_csv(index=False).encode('utf-8'), 'altas_bajas.csv', 'text/csv')
