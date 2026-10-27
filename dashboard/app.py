"""Dashboard de métricas de negocio - Prueba Big Data Zapping 2026.

Ejecutar desde la carpeta del proyecto (después de correr el notebook, que genera outputs/):
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import data  # noqa: E402

st.set_page_config(page_title='Métricas de negocio · Zapping', layout='wide')
# Lo que el tema de .streamlit/config.toml no cubre: títulos en Bold Italic (la itálica es la voz de la marca)
# con tracking ajustado, cifras de los KPI en Bold y texto sobre Zapink en Bold (mínimo de la marca sobre rosa).
st.html('''<style>
h1, h2, h3 { font-style: italic; letter-spacing: -0.02em; }
[data-testid="stMetricValue"] { font-weight: 700; letter-spacing: -0.02em; }
[data-baseweb="tag"], [data-testid="stBaseButton-primary"] { font-weight: 700; }
code { color: rgba(255, 255, 255, 0.7); }
</style>''')

if not (data.OUT / 'user_day.parquet').exists():
    st.error('No se encontró `outputs/user_day.parquet`. Ejecuta primero el notebook `prueba_big_data.ipynb`.')
    st.stop()

# ------------------------------------------------------------------------------------------
# Filtros globales: aplican a todas las páginas
# ------------------------------------------------------------------------------------------
d0, dn = data.bounds()
with st.sidebar:
    st.header('Filtros')
    rango = st.date_input('Período', value=(d0.date(), dn.date()), min_value=d0.date(), max_value=dn.date(),
                          format='DD/MM/YYYY', key='f_rango')
    start, end = (rango if isinstance(rango, (tuple, list)) and len(rango) == 2 else (d0.date(), dn.date()))

    dims = []
    for dim, label in data.DIMS.items():
        vals = st.multiselect(label, data.dim_values(dim), key=f'f_{dim}', placeholder='Todos')
        dims.append((dim, tuple(vals)))

    st.divider()
    excl_mas = st.toggle('Excluir eventos masivos', key='f_mas',
                         help='Bajas por fin de convenio B2B y migraciones masivas de catálogo. '
                              'En el churn, muestra el churn orgánico.')
    if st.button('Restablecer filtros', width='stretch'):
        for k in [k for k in st.session_state if k.startswith('f_')]:
            del st.session_state[k]
        st.rerun()
    st.caption('Fuente: `outputs/*.parquet` generados por el notebook. Montos en USD a tasas fijas del '
               '26-10-2026 (CLP 991,40 · BRL 5,02 · PEN 3,45).')

st.session_state['filters'] = data.Filters(
    start=pd.Timestamp(start), end=pd.Timestamp(end), dims=tuple(dims),
    excluir_masivos=excl_mas)

pages = [
    st.Page('views/resumen.py', title='Resumen', icon=':material/dashboard:', default=True),
    st.Page('views/flujo.py', title='Flujo de clientes', icon=':material/swap_vert:'),
    st.Page('views/reactivaciones.py', title='Reactivaciones', icon=':material/replay:'),
    st.Page('views/cambios.py', title='Cambios de plan', icon=':material/swap_horiz:'),
    st.Page('views/ingresos.py', title='Ingresos', icon=':material/payments:'),
    st.Page('views/engagement.py', title='Engagement', icon=':material/play_circle:'),
    st.Page('views/retencion.py', title='Retención', icon=':material/favorite:'),
]
st.navigation(pages).run()
