import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import charts, data, metrics

f = data.get_filters()
st.title('Resumen')
f.subtitle()

snap = metrics.snapshot(f)
if snap.empty:
    charts.empty_state()
    st.stop()

months = snap['month'].tolist()
partial = dict(zip(snap['month'], snap['parcial'].fillna(False)))
complete = [m for m in months if not partial[m]]
ref = st.selectbox('Mes de referencia', months, index=months.index(complete[-1] if complete else months[-1]),
                   format_func=lambda m: data.month_label(m) + (' (parcial)' if partial[m] else ''))
i = months.index(ref)
cur, prev = snap.iloc[i], (snap.iloc[i - 1] if i > 0 else None)


def delta(cur_v, prev_v, kind='pct'):
    if prev_v is None or prev_v != prev_v or prev_v == 0:
        return None
    if kind == 'pp':
        return f'{(cur_v - prev_v) * 100:+.1f} pp'.replace('.', ',')
    return f'{(cur_v / prev_v - 1) * 100:+.1f}%'.replace('.', ',')


mau = metrics.mau(f).set_index('month')
mau_cur = mau['ratio'].get(ref)
mau_prev = mau['ratio'].get(months[i - 1]) if i > 0 else None

# Churn 1M: precalculado por una dimensión; disponible sin filtros o con un único segmento filtrado
seg = ('total', 'Total') if not f.active_dims else f.single_segment()
churn_label = 'Churn 1M (orgánico)' if f.excluir_masivos else 'Churn 1M (total)'
churn_cur = churn_prev = None
if seg:
    ch = metrics.churn(f, None if seg[0] == 'total' else seg[0])
    ch = ch[(ch['horizonte'] == '1M') & (ch['segment'] == seg[1])].set_index('cohort_month')['value']
    churn_cur = ch.get(ref)
    churn_prev = ch.get(months[i - 1]) if i > 0 else None

cols = st.columns(5)
cols[0].metric('Usuarios activos', charts.fmt_int(cur['activos']),
               delta(cur['activos'], prev['activos'] if prev is not None else None), border=True,
               help='Usuarios con al menos un plan activo el último día del mes.')
cols[1].metric('MRR (USD)', charts.fmt_int(cur['mrr']), delta(cur['mrr'], prev['mrr'] if prev is not None else None),
               border=True, help='Ingreso mensual recurrente en USD (planes con is_mrr_contributor = 1).')
cols[2].metric('ARPPU (USD)', f"{cur['arppu']:.2f}".replace('.', ','),
               delta(cur['arppu'], prev['arppu'] if prev is not None else None), border=True,
               help='MRR / usuarios pagadores (MRR > 0).')
cols[3].metric('MAU / suscriptores', charts.fmt_pct(mau_cur) if mau_cur is not None else '—',
               delta(mau_cur, mau_prev, 'pp') if mau_cur is not None else None, border=True,
               help='Fracción de los activos al cierre del mes que vio contenido en los 30 días previos '
                    '(time_watched > 0).')
cols[4].metric(churn_label, charts.fmt_pct(churn_cur) if churn_cur is not None else '—',
               delta(churn_cur, churn_prev, 'pp') if churn_cur is not None else None,
               delta_color='inverse', border=True,
               help='Usuarios activos al inicio del mes que se fueron antes de un mes. '
                    + ('' if seg else 'No disponible con filtros combinados (ver página Retención).'))
if partial[ref]:
    st.warning(f'{data.month_label(ref)} es un mes parcial: el snapshot corresponde al último día disponible.')

# ------------------------------------------------------------------------------------------
st.subheader('Evolución diaria')
dd = metrics.daily(f)
events = data.eventos_clave()
left, right = st.columns(2)
with left:
    st.markdown('**MRR diario**')
    fig = go.Figure(go.Scatter(x=dd['d'], y=dd['mrr'], mode='lines', name='MRR',
                               line=dict(color=charts.highlight(), width=2),
                               hovertemplate='US$ %{y:,.0f}<extra></extra>'))
    charts.daily_axis(charts.layout(fig, height=320, y_title='MRR (USD)', legend=False))
    charts.mark_events(fig, events, f.start, f.end)
    charts.show(fig, dd[['d', 'mrr']].rename(columns={'d': 'fecha', 'mrr': 'mrr_usd'}), key='res_mrr',
                caption='MRR en USD de todos los planes activos cada día. Línea continua: fin de convenio; '
                        'punteada: migración de catálogo. Ambos eventos mueven el MRR: las migraciones cambian el '
                        'precio del plan de cientos de usuarios a la vez.')
with right:
    st.markdown('**Usuarios activos**')
    fig = go.Figure(go.Scatter(x=dd['d'], y=dd['activos'], mode='lines', name='Usuarios activos',
                               line=dict(color=charts.highlight(), width=2),
                               hovertemplate='%{y:,.0f} usuarios<extra></extra>'))
    charts.daily_axis(charts.layout(fig, height=320, y_title='Usuarios', legend=False))
    charts.mark_events(fig, events, f.start, f.end, tipos=['Fin de convenio'])
    charts.show(fig, dd[['d', 'activos']].rename(columns={'d': 'fecha'}), key='res_activos',
                caption='Usuarios con al menos un plan activo cada día. Solo se marca el fin de convenio (12-06), el '
                        'único evento masivo que cambia el número de usuarios: las migraciones solo les cambian el plan.')

# ------------------------------------------------------------------------------------------
ev = events[(events['date'] >= f.start) & (events['date'] <= f.end)]
if not ev.empty:
    st.subheader('Eventos masivos')
    st.markdown(
        'Son días en que muchos usuarios cambian a la vez por una decisión de Zapping o de un partner, no por '
        'decisión propia. Se detectan en los datos como volúmenes atípicos:\n'
        '- **Fin de convenio** (línea continua): un partner B2B termina su convenio y todos sus usuarios pierden el '
        'plan el mismo día. Baja el número de usuarios y el MRR.\n'
        '- **Migración de catálogo** (línea punteada): cientos de usuarios pasan el mismo día del mismo plan A al '
        'mismo plan B. Cambia el plan y el MRR, pero no el número de usuarios. Se marcan las de 200 o más ' 
        'usuarios en el día.')
    signed = lambda x: ('+' if x > 0 else '') + charts.fmt_int(x)  # noqa: E731
    tbl = pd.DataFrame({
        'Fecha': ev['date'].dt.strftime('%d/%m/%Y'), 'Tipo': ev['tipo'], 'Qué pasó': ev['detalle'],
        'Usuarios': ev['usuarios'].map(charts.fmt_int), 'Efecto en activos': ev['efecto_activos'].map(signed),
        'Efecto en MRR (USD)': ev['efecto_mrr'].map(signed)})
    st.table(tbl.set_index('Fecha'))
    charts.figure_caption('Eventos masivos del período. *Qué pasó*: partners (fin de convenio) o pares plan '
                          'anterior → plan nuevo (migración) con más usuarios ese día. *Efecto en MRR*: MRR de los '
                          'planes perdidos o diferencia de precio de los migrados; el resto de los movimientos del '
                          'día no se incluye.')

with st.expander('Ver tabla mensual'):
    tbl = snap.assign(mes=snap['month'].map(data.month_label)).merge(
        mau[['mau', 'suscriptores', 'ratio']].reset_index(), on='month', how='left')
    st.dataframe(tbl[['mes', 'activos', 'mrr', 'pagadores', 'arppu', 'mau', 'suscriptores', 'ratio']],
                 hide_index=True, width='stretch')
