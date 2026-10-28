import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import charts, data

f = data.get_filters()
st.title('Perfiles y riesgo')
f.subtitle('Actividad 6 (KDD)')

if not data.PERFILES.exists():
    st.error('No se encontró `outputs/perfiles.parquet`. Ejecuta la sección 7 del notebook.')
    st.stop()

res = data.perfiles_resumen()
riesgo = data.riesgo_antiguedad()
cox = data.cox()
juego = data.mrr_en_juego()
orden = res.index.tolist()
cmap = charts.color_map(orden)
total = riesgo[riesgo['grupo'] == 'Total'].set_index('mes')
ventana = total.index[total['ventana']].tolist()

st.markdown('**Quiénes son** los usuarios (perfiles por clustering de su comportamiento) y **cuándo se van** (riesgo '
            'mensual de baja según la antigüedad de la suscripción). ')

en_v = juego[juego['en_ventana']]
cols = st.columns(4)
cols[0].metric('Perfiles', len(orden) - 1, border=True,
               help='Grupos de K-means, más "Observación corta" (menos de 30 días observables).')
cols[1].metric('Ventana de riesgo', f'Meses {ventana[0]}–{ventana[-1]}' if ventana else '—', border=True,
               help='Meses de antigüedad con riesgo de baja mayor a 1,5 veces la mediana y al menos 30 bajas.')
cols[2].metric('MRR en ventana (USD)', charts.fmt_int(en_v['mrr'].sum()), border=True,
               help='MRR al cierre de los usuarios activos cuya suscripción está en la ventana de riesgo.')
cols[3].metric('Pérdida esperada (USD)', charts.fmt_int(en_v['mrr_esperado_perdido_mes'].sum()), border=True,
               help='Pérdida mensual: MRR en ventana por el riesgo de su mes de antigüedad, lo que se perdería el mes siguiente sin '
                    f'hacer nada ({en_v["mrr_esperado_perdido_mes"].sum() / juego["mrr_esperado_perdido_mes"].sum():.0%} '
                    'de la pérdida esperada total).')

# ------------------------------------------------------------------------------------------
st.subheader('Quiénes son')
left, right = st.columns(2)
with left:
    fig = go.Figure()
    fig.add_bar(y=orden, x=res['pct_usuarios'], name='% de usuarios', orientation='h', marker_color=charts.context(),
                marker_line_width=0, hovertemplate='%{y}: %{x:.1%} de los usuarios<extra></extra>')
    fig.add_bar(y=orden, x=res['pct_mrr_cierre'], name='% del MRR al cierre', orientation='h',
                marker_color=charts.highlight(), marker_line_width=0,
                hovertemplate='%{y}: %{x:.1%} del MRR<extra></extra>')
    fig.update_layout(barmode='group', bargap=0.3)
    charts.layout(fig, height=380, x_title='Participación', hovermode='y unified')
    fig.update_xaxes(tickformat='.0%', showgrid=True, gridcolor=charts.ink('grid'))
    fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
    charts.show(fig, res[['usuarios', 'pct_usuarios', 'mrr_cierre', 'pct_mrr_cierre']].round(3).reset_index(),
                key='perf_tamano',
                caption='Tamaño de cada perfil (gris) y su participación en el MRR al 07-09 (rosa). Un perfil con '
                        'más MRR que usuarios paga planes más caros o sigue activo en mayor proporción.')
with right:
    fig = go.Figure(go.Bar(y=orden, x=res['churn'], orientation='h', marker_line_width=0,
                           marker_color=[charts.highlight() if v == res['churn'].max() else charts.context()
                                         for v in res['churn']],
                           customdata=res['fin_convenio'],
                           hovertemplate='%{y}: se fue el %{x:.1%} · fin de convenio %{customdata:.1%}<extra></extra>'))
    charts.layout(fig, height=380, x_title='Fracción que se fue', legend=False, hovermode='closest')
    fig.update_xaxes(tickformat='.0%', showgrid=True, gridcolor=charts.ink('grid'))
    fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
    charts.show(fig, res[['churn', 'fin_convenio']].round(3).reset_index(), key='perf_churn',
                caption='Fracción de cada perfil que se fue durante la ventana y no volvió, sin contar los fines de '
                        'convenio (que no son una decisión del usuario; ver hover). En rosa, el perfil que más se va.')

# ------------------------------------------------------------------------------------------
st.subheader('Qué distingue a cada perfil')
VARS = {'precio_usd': 'Precio (USD)', 'addons': 'Addons', 'frac_dias_vio': 'Días con consumo',
        'horas_30d': 'Horas en 30 días', 'reactivaciones': 'Reactivaciones', 'dias_fuera_mediana': 'Días fuera',
        'upgrades': 'Upgrades', 'downgrades': 'Downgrades', 'antig_dias': 'Antigüedad al llegar'}
perf = [p for p in orden if p != 'Observación corta']
zm = res.loc[perf, [f'z_{v}' for v in VARS]].to_numpy()
real = res.loc[perf, list(VARS)]
diverging = [[0, charts.slot(1)], [0.5, charts.ink('neutral')], [1, charts.slot(3)]]
fig = go.Figure(go.Heatmap(
    z=np.clip(zm, -3, 3), x=list(VARS.values()), y=perf, zmin=-3, zmax=3, colorscale=diverging,
    text=[[f'{v:+.1f}'.replace('.', ',') for v in row] for row in zm], texttemplate='%{text}',
    customdata=real.round(2).to_numpy().tolist(), xgap=2, ygap=2,
    hovertemplate='%{y} · %{x}<br>%{text} desv. estándar · mediana %{customdata}<extra></extra>',
    colorbar=dict(thickness=10, tickvals=[-3, 0, 3], ticktext=['−3 o menos', '0', '+3 o más'])))
charts.layout(fig, height=360, legend=False, hovermode='closest')
fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
fig.update_xaxes(side='top')
charts.show(fig, real.round(2).reset_index(), key='perf_z',
            caption='Centroide de cada perfil en desviaciones estándar respecto del promedio de los usuarios (después '
                    'de log en las variables de cola larga). Fucsia: sobre el promedio; índigo: bajo el promedio. El '
                    'nombre de cada perfil sale de su rasgo más marcado. La tabla tiene las medianas en unidades '
                    'reales.')

# ------------------------------------------------------------------------------------------
st.subheader('Cuándo se van')
grupo = st.segmented_control('Comparar por', ['Total', 'Segmento', 'Cupón', 'Perfil'], default='Total',
                             key='perf_grupo') or 'Total'
sub = riesgo[(riesgo['grupo'] == grupo) & (riesgo['bajas'] > 0)]
fig = go.Figure()
for m in ventana:
    fig.add_vrect(x0=m - 0.5, x1=m + 0.5, fillcolor=charts.ink('grid'), line_width=0, layer='below')
if grupo == 'Total':
    fig.add_scatter(x=list(total.index) + list(total.index[::-1]),
                    y=list(total['ic_sup']) + list(total['ic_inf'][::-1]), fill='toself',
                    fillcolor=charts.rgba(charts.highlight(), 0.18), line_width=0, hoverinfo='skip', showlegend=False)
    fig.add_scatter(x=total.index, y=total['riesgo'], mode='lines+markers', name='Total',
                    line=dict(color=charts.highlight(), width=2), marker=dict(size=8),
                    customdata=total[['bajas', 'en_riesgo']],
                    hovertemplate='Mes %{x}: %{y:.1%} (%{customdata[0]:,.0f} bajas de %{customdata[1]:,.0f})'
                                  '<extra></extra>')
else:
    valores = orden if grupo == 'Perfil' else sorted(sub['valor'].unique())
    gmap = cmap if grupo == 'Perfil' else charts.color_map(valores)
    for v in valores:
        s = sub[sub['valor'] == v]
        if s.empty or (grupo == 'Perfil' and v == 'Observación corta'):
            continue
        fig.add_scatter(x=s['mes'], y=s['riesgo'], mode='lines+markers', name=v,
                        line=dict(color=gmap[v], width=2), marker=dict(size=7),
                        hovertemplate=f'{v} · mes %{{x}}: %{{y:.1%}}<extra></extra>')
charts.layout(fig, height=400, y_title='Riesgo mensual de baja', y_format='.0%', x_title='Mes de antigüedad de la '
              'suscripción', hovermode='closest' if grupo != 'Total' else 'x unified')
fig.update_xaxes(dtick=3)
charts.show(fig, sub[['valor', 'mes', 'en_riesgo', 'meses_persona', 'bajas', 'riesgo', 'ic_inf', 'ic_sup']].round(4),
            key='perf_riesgo',
            caption='Probabilidad de darse de baja durante cada mes de antigüedad entre quienes llegaron a ese mes '
                    '(bajas / meses-persona, con entrada tardía y sin fines de convenio). Franja gris: ventana de '
                    f'riesgo de la curva total (meses {ventana[0]}–{ventana[-1]}). En el total, la banda es el '
                    'intervalo de confianza del 95%. El perfil Intermitente tiene riesgo alto por construcción: se '
                    'define por haber salido y vuelto varias veces.' if ventana else 'Riesgo mensual de baja.')

left, right = st.columns(2)
with left:
    st.markdown('**Riesgo alrededor del fin del cupón**')
    rc = data.riesgo_cupon()
    fig = go.Figure(go.Bar(x=rc['mes_relativo'], y=rc['riesgo'], marker_line_width=0,
                           marker_color=[charts.highlight() if m == 0 else charts.context() for m in rc['mes_relativo']],
                           customdata=rc['bajas'],
                           hovertemplate='Mes %{x}: %{y:.1%} (%{customdata:,.0f} bajas)<extra></extra>'))
    charts.layout(fig, height=320, y_title='Riesgo mensual de baja', y_format='.0%', legend=False,
                  x_title='Meses desde el fin del descuento', hovermode='closest')
    fig.update_xaxes(dtick=1)
    charts.show(fig, rc.round(4), key='perf_cupon',
                caption='Altas de 2026 con cupón, alineadas por el fin del descuento: el mes 0 (rosa) es el primero a '
                        'precio completo. El riesgo sube justo ahí y baja después: el cupón posterga la decisión.')
with right:
    st.markdown('**Qué multiplica el riesgo (modelo de Cox)**')
    cx = cox.sort_values('hr')
    sig = (cx['ic_inf'] > 1) | (cx['ic_sup'] < 1)
    color = np.where(~sig, charts.context(), np.where(cx['hr'] > 1, charts.highlight(), charts.slot(1)))
    etiquetas = cx['variable'].str.replace(' (vs Activo establecido)', '', regex=False)
    fig = go.Figure(go.Scatter(
        x=cx['hr'], y=etiquetas, mode='markers', marker=dict(size=10, color=color),
        error_x=dict(type='data', symmetric=False, array=cx['ic_sup'] - cx['hr'], arrayminus=cx['hr'] - cx['ic_inf'],
                     color=charts.ink('muted'), thickness=1.5, width=0),
        customdata=cx[['ic_inf', 'ic_sup']],
        hovertemplate='%{y}: HR %{x:.2f} (IC 95% %{customdata[0]:.2f}–%{customdata[1]:.2f})<extra></extra>'))
    fig.add_vline(x=1, line_width=1, line_color=charts.ink('secondary'))
    charts.layout(fig, height=320 + 12 * len(cx), legend=False, x_title='Hazard ratio (escala log)',
                  hovermode='closest')
    fig.update_xaxes(type='log', showgrid=True, gridcolor=charts.ink('grid'), tickvals=[0.5, 1, 2, 4, 8],
                     ticktext=['0,5', '1', '2', '4', '8'])
    fig.update_yaxes(gridcolor='rgba(0,0,0,0)')
    charts.show(fig, cox.round(3), key='perf_cox',
                caption='Cuánto multiplica cada atributo el riesgo de baja a igual antigüedad (1 = sin efecto). Rosa: '
                        'lo aumenta; índigo: lo reduce; gris: no significativo. Referencias: B2C, Ecuador y el perfil '
                        'Activo establecido. La tabla incluye el HR en los primeros 90 días y después.')

# ------------------------------------------------------------------------------------------
st.subheader('Dónde está el MRR en juego')
tabla = (juego[juego['en_ventana']].sort_values('mrr_esperado_perdido_mes', ascending=False)
         .assign(mrr=lambda x: x['mrr'].map(charts.fmt_int),
                 bajas_esperadas_mes=lambda x: x['bajas_esperadas_mes'].round(0).map(charts.fmt_int),
                 mrr_esperado_perdido_mes=lambda x: x['mrr_esperado_perdido_mes'].map(charts.fmt_int)))
st.dataframe(tabla[['perfil', 'usuarios', 'mrr', 'bajas_esperadas_mes', 'mrr_esperado_perdido_mes']].rename(columns={
    'perfil': 'Perfil', 'usuarios': 'Usuarios en ventana', 'mrr': 'MRR (USD)',
    'bajas_esperadas_mes': 'Bajas esperadas el próximo mes', 'mrr_esperado_perdido_mes': 'MRR esperado perdido (USD)'}),
    hide_index=True, width='stretch')
charts.figure_caption('Usuarios activos al 07-09 cuya suscripción está en la ventana de riesgo, por perfil. La '
                      'pérdida esperada multiplica su MRR por el riesgo de su mes de antigüedad (curva total), '
                      'lo que es el objetivo natural de una promoción de retención.')
