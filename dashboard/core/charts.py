"""Estilo y utilidades de gráficos.

Sigue la guía de marca de Zapping (brand.zapping.com), con los tokens de su CSS:
- Fondo negro de marca (#040405); Zapink Pulse (#e90068) marca el argumento principal.
- Sin gris arbitrario: texto, ejes y grilla usan opacidad de blanco (o de negro en modo claro).
- Categorías con los acentos indigo, violet y fucsia, en ese orden; los pasos de cada escala se eligieron para
  separarse también con daltonismo (validado con OKLab y simulación Machado 2009).
- Un gráfico con una sola serie va en Zapink; si una serie importa más que otra, Zapink y el resto en opacidad.

Reglas de visualización que se aplican en todo el dashboard:
- Un solo eje Y por gráfico (nunca doble eje).
- El color sigue a la entidad: cada segmento conserva su color aunque cambien los filtros.
- Más de 8 segmentos -> el resto queda en el neutro de 'Otros'.
- Cada gráfico tiene su tabla equivalente ("Ver tabla").
"""
from typing import Dict, Iterable, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

FONT = '"Poppins", sans-serif'  # respaldo declarado por la marca para ZappingFont
ZAPINK = '#e90068'

# Slots 1-3: acentos de marca (indigo, violet, fucsia). Slot 4: tinta (blanco / negro de marca).
# Slots 5-8: otros pasos de las mismas escalas, solo para dimensiones con más de 4 valores.
CATEGORICAL = {
    'dark': ['#8156ff', '#dba6ff', '#c70091', '#e6e6e6', '#f842ba', '#9f2cd7', '#bab1ff', '#828282'],
    'light': ['#8156ff', '#671a8d', '#e000a3', '#363637', '#a50077', '#b333f2', '#482e94', '#828282'],
}
# Magnitud (heatmaps): Zapink con opacidad creciente sobre la superficie
SEQUENTIAL = {
    'dark': ['#1f0411', '#490323', '#720235', '#9b0146', '#c40158', '#e90068'],
    'light': ['#fce0ed', '#f8b2d2', '#f485b7', '#f0579b', '#ed2980', '#e90068'],
}
# Orden (tramos de antigüedad): escala de opacidad de blanco (o negro), de 30% a 90%
ORDINAL = {
    'dark': ['#4f4f50', '#6d6d6e', '#8c8c8c', '#aaaaaa', '#c8c8c8', '#e6e6e6'],
    'light': ['#b4b4b4', '#969696', '#777778', '#59595a', '#3b3b3c', '#1d1d1e'],
}
INK = {
    'dark': {'primary': '#ffffff', 'secondary': 'rgba(255,255,255,0.7)', 'muted': 'rgba(255,255,255,0.5)',
             'grid': 'rgba(255,255,255,0.1)', 'axis': 'rgba(255,255,255,0.2)', 'surface': '#040405',
             'neutral': '#4f4f50', 'context': '#686869'},
    'light': {'primary': '#040405', 'secondary': 'rgba(4,4,5,0.7)', 'muted': 'rgba(4,4,5,0.5)',
              'grid': 'rgba(4,4,5,0.1)', 'axis': 'rgba(4,4,5,0.2)', 'surface': '#ffffff',
              'neutral': '#b4b4b4', 'context': '#9b9b9b'},
}


def mode() -> str:
    """Modo del tema. Manda `theme.base` del config (negro de marca); st.context.theme.type informa la preferencia
    del navegador aunque haya un tema propio, así que solo se usa si el config no fija la base."""
    base = st.get_option('theme.base')
    if base in ('dark', 'light'):
        return base
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


def highlight() -> str:
    """Zapink: la serie principal (o la única) del gráfico."""
    return ZAPINK


def context() -> str:
    """Serie de contexto junto a una en Zapink (blanco o negro al 40%)."""
    return ink('context')


def ordinal() -> List[str]:
    return ORDINAL[mode()]


def sequential_scale() -> list:
    """Escala continua para heatmaps."""
    steps = SEQUENTIAL[mode()]
    return [[i / (len(steps) - 1), c] for i, c in enumerate(steps)]


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip('#')
    return f'rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})'


def color_map(values: Iterable[str]) -> Dict[str, str]:
    """Asigna colores en orden fijo; desde el 9º valor (y 'Otros') usa el neutro."""
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
    return {'Alta nueva': slot(1), 'Reactivación': slot(2),
            'Baja sin retorno': slot(3), 'Baja con retorno': slot(3), 'Baja masiva': context(),
            'Alta addon': slot(1), 'Baja addon': slot(3)}


# Clases que comparten color con otra y se distinguen por textura (rayado diagonal)
HATCHED = {'Baja con retorno'}


def hatch(clase: str) -> dict:
    """Patrón de relleno para marcar una variante de la misma entidad sin gastar otro color."""
    if clase not in HATCHED:
        return {}
    return dict(shape='/', fillmode='overlay', fgcolor=ink('surface'), size=6, solidity=0.35)


def tipo_colors() -> Dict[str, str]:
    return {'upgrade': slot(1), 'downgrade': slot(3), 'lateral': slot(2), 'reajuste_precio': slot(4)}


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
        font=dict(family=FONT),
    )
    fig.update_xaxes(title_text=x_title, showgrid=False, linecolor=ink('axis'), ticks='outside',
                     tickcolor=ink('axis'))
    fig.update_yaxes(title_text=y_title, gridcolor=ink('grid'), zeroline=True, zerolinecolor=ink('axis'),
                     zerolinewidth=1, tickformat=y_format)
    # Separación de 2px (color de la superficie) entre segmentos apilados y barras contiguas
    fig.update_traces(selector=dict(type='bar'), marker_line_color=ink('surface'), marker_line_width=2)
    return fig


def sankey_font() -> dict:
    return dict(color=ink('primary'), size=12, shadow='none', family=FONT)


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
