"""Estilo y utilidades de gráficos.

Paleta categórica de referencia validada (8 colores en orden fijo, con su versión para modo oscuro).
Reglas que se aplican en todo el dashboard:
- Un solo eje Y por gráfico (nunca doble eje).
- El color sigue a la entidad: cada segmento conserva su color aunque cambien los filtros.
- Más de 8 segmentos -> el resto se agrupa en 'Otros' (gris).
- Cada gráfico tiene su tabla equivalente ("Ver tabla").
"""
from typing import Dict, Iterable, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CATEGORICAL = {
    'light': ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'],
    'dark': ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
}
SEQUENTIAL_BLUE = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
ORDINAL_BLUE = ['#86b6ef', '#6da7ec', '#3987e5', '#2a78d6', '#1c5cab', '#184f95']  # 250..600
INK = {
    'light': {'primary': '#0b0b0b', 'secondary': '#52514e', 'muted': '#898781',
              'grid': '#e1e0d9', 'axis': '#c3c2b7', 'surface': '#fcfcfb', 'neutral': '#c3c2b7'},
    'dark': {'primary': '#f0efec', 'secondary': '#c3c2b7', 'muted': '#898781',
             'grid': '#2c2c2a', 'axis': '#383835', 'surface': '#1a1a19', 'neutral': '#5c5b57'},
}


def mode() -> str:
    try:
        return 'dark' if st.context.theme.type == 'dark' else 'light'
    except Exception:
        return 'light'


def palette() -> List[str]:
    return CATEGORICAL[mode()]


def ink(role: str) -> str:
    return INK[mode()][role]


def slot(i: int) -> str:
    """Color categorical por número de slot (1..8)."""
    return palette()[i - 1]


def color_map(values: Iterable[str]) -> Dict[str, str]:
    """Asigna colores en orden fijo; desde el 9º valor (y 'Otros') usa gris neutro."""
    colors = palette()
    out, i = {}, 0
    for v in values:
        if v == 'Otros' or i >= len(colors):
            out[v] = ink('neutral')
        else:
            out[v] = colors[i]
            i += 1
    return out


# Colores semánticos fijos (cada uno es siempre la misma entidad)
def flow_colors() -> Dict[str, str]:
    return {'Alta nueva': slot(1), 'Reactivación': slot(3),
            'Baja sin retorno': slot(2), 'Baja con retorno': slot(2), 'Baja masiva': slot(7),
            'Alta addon': slot(1), 'Baja addon': slot(2)}


# Clases que comparten color con otra y se distinguen por textura (rayado diagonal)
HATCHED = {'Baja con retorno'}


def hatch(clase: str) -> dict:
    """Patrón de relleno para marcar una variante de la misma entidad sin gastar otro color."""
    if clase not in HATCHED:
        return {}
    return dict(shape='/', fillmode='overlay', fgcolor=ink('surface'), size=6, solidity=0.35)


def tipo_colors() -> Dict[str, str]:
    return {'upgrade': slot(1), 'downgrade': slot(2), 'lateral': slot(3), 'reajuste_precio': slot(4)}


TIPO_LABELS = {'upgrade': 'Upgrade', 'downgrade': 'Downgrade', 'lateral': 'Lateral (mismo precio)',
               'reajuste_precio': 'Reajuste de precio'}


def layout(fig: go.Figure, height: int = 360, y_title: Optional[str] = None, y_format: Optional[str] = None,
           x_title: Optional[str] = None, legend: bool = True, hovermode: str = 'x unified') -> go.Figure:
    """Diseño base: grilla tenue, leyenda arriba, separadores decimales en español."""
    fig.update_layout(
        height=height, separators=',.', hovermode=hovermode,
        margin=dict(l=8, r=8, t=36 if legend else 12, b=8),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, title_text='', traceorder='normal'),
        showlegend=legend, bargap=0.25,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif'),
    )
    fig.update_xaxes(title_text=x_title, showgrid=False, linecolor=ink('axis'), ticks='outside',
                     tickcolor=ink('axis'))
    fig.update_yaxes(title_text=y_title, gridcolor=ink('grid'), zeroline=True, zerolinecolor=ink('axis'),
                     zerolinewidth=1, tickformat=y_format)
    # Separación de 2px (color de la superficie) entre segmentos apilados y barras contiguas
    fig.update_traces(selector=dict(type='bar'), marker_line_color=ink('surface'), marker_line_width=2)
    return fig


def sankey_font() -> dict:
    return dict(color=ink('primary'), size=12, shadow='none',
                family='system-ui, -apple-system, "Segoe UI", sans-serif')


def daily_axis(fig: go.Figure) -> go.Figure:
    """Fechas como dd/mm, para no depender de nombres de mes en inglés."""
    fig.update_xaxes(tickformat='%d/%m', hoverformat='%d/%m/%Y')
    return fig


def mark_events(fig: go.Figure, events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> go.Figure:
    """Líneas verticales finas en los días con eventos masivos."""
    for _, ev in events.iterrows():
        if start <= ev['date'] <= end:
            fig.add_vline(x=ev['date'], line_width=1, line_color=ink('axis'), layer='below')
    return fig


def show(fig: go.Figure, table: Optional[pd.DataFrame] = None, key: Optional[str] = None,
         caption: Optional[str] = None) -> None:
    """Muestra el gráfico y, debajo, su tabla equivalente con descarga CSV."""
    st.plotly_chart(fig, use_container_width=True, theme='streamlit', key=key,
                    config={'displaylogo': False, 'displayModeBar': False})
    if caption:
        st.caption(caption)
    if table is not None:
        with st.expander('Ver tabla'):
            st.dataframe(table, width='stretch', hide_index=True)
            st.download_button('Descargar CSV', table.to_csv(index=False).encode('utf-8'),
                               file_name=f'{key or "tabla"}.csv', mime='text/csv', key=f'dl_{key}')


def fmt_int(x: float) -> str:
    return f'{x:,.0f}'.replace(',', '.')


def fmt_usd(x: float, decimals: int = 0) -> str:
    s = f'{x:,.{decimals}f}'.replace(',', '§').replace('.', ',').replace('§', '.')
    return f'US$ {s}'


def fmt_pct(x: float, decimals: int = 1) -> str:
    return f'{x * 100:.{decimals}f}%'.replace('.', ',')


def empty_state(msg: str = 'No hay datos para los filtros seleccionados.') -> None:
    st.info(msg)
