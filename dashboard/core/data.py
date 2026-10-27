"""Acceso a datos del dashboard.

Lee las tablas que exporta el notebook (`outputs/*.parquet`):
- `user_day` (1,6M filas) se consulta con DuckDB directamente sobre el parquet, con los filtros
  aplicados en SQL, para no cargarlo completo en memoria.
- Las tablas de eventos y métricas son pequeñas y se leen con pandas.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs'
USER_DAY = (OUT / 'user_day.parquet').as_posix()

DIMS: Dict[str, str] = {
    'country_iso': 'País',
    'segmento': 'Segmento',
    'category': 'Categoría',
    'package_grp': 'Plan base',
    'acquisition_grp': 'Canal de adquisición',
    'coupon_label': 'Cupón',
    'tenure_bucket': 'Antigüedad',
}
TENURE_ORDER = ['<1M', '1-3M', '3-6M', '6-12M', '1-2A', '>2A']
MONTHS_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def month_short(month: str) -> str:
    """'2026-03' -> 'mar' (todos los datos son de 2026). Para ejes de gráficos."""
    return MONTHS_ES[int(month.split('-')[1]) - 1]


def month_label(month: str) -> str:
    """'2026-03' -> 'mar 2026'."""
    year, m = month.split('-')
    return f'{MONTHS_ES[int(m) - 1]} {year}'


# --------------------------------------------------------------------------------------------
# Conexión y consultas
# --------------------------------------------------------------------------------------------
@st.cache_resource
def _connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW ud AS SELECT * FROM read_parquet('{USER_DAY}')")
    return con


@st.cache_data(show_spinner=False)
def query(sql: str, params: Tuple = ()) -> pd.DataFrame:
    """Ejecuta SQL sobre la vista `ud` (user_day). Cacheado por (sql, params)."""
    return _connection().cursor().execute(sql, list(params)).df()


@st.cache_data(show_spinner=False)
def bounds() -> Tuple[pd.Timestamp, pd.Timestamp]:
    row = query('SELECT min(d) AS d0, max(d) AS dn FROM ud').iloc[0]
    return pd.Timestamp(row['d0']), pd.Timestamp(row['dn'])


@st.cache_data(show_spinner=False)
def snapshot_days() -> pd.DataFrame:
    """Último día disponible de cada mes (snapshot de las métricas de stock)."""
    snap = query('SELECT month, max(d) AS d FROM ud GROUP BY month ORDER BY month')
    _, dn = bounds()
    snap['parcial'] = (snap['d'] == dn) & (dn != dn + pd.offsets.MonthEnd(0))
    return snap


@st.cache_data(show_spinner=False)
def dim_values(dim: str) -> List[str]:
    """Valores de una dimensión en orden estable (más usuarios primero, 'Otros' al final).

    Este orden fija el color de cada segmento en todos los gráficos.
    """
    if dim == 'tenure_bucket':
        return TENURE_ORDER
    vals = query(f'SELECT {dim} AS v, count(DISTINCT id) AS n FROM ud GROUP BY 1 ORDER BY n DESC')['v'].tolist()
    vals = [v for v in vals if v is not None]
    return [v for v in vals if v != 'Otros'] + (['Otros'] if 'Otros' in vals else [])


# --------------------------------------------------------------------------------------------
# Filtros
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Filters:
    start: pd.Timestamp
    end: pd.Timestamp
    dims: Tuple[Tuple[str, Tuple[str, ...]], ...] = field(default_factory=tuple)
    excluir_masivos: bool = False

    @property
    def active_dims(self) -> Dict[str, Tuple[str, ...]]:
        return {d: v for d, v in self.dims if v}

    def sql(self, date_col: str = 'd', with_dates: bool = True) -> Tuple[str, Tuple]:
        """Cláusula WHERE para `ud` y sus parámetros."""
        clauses, params = [], []
        if with_dates:
            clauses.append(f'{date_col} BETWEEN ? AND ?')
            params += [self.start.to_pydatetime(), self.end.to_pydatetime()]
        for dim, vals in self.active_dims.items():
            clauses.append(f"{dim} IN ({', '.join('?' * len(vals))})")
            params += list(vals)
        return (' AND '.join(clauses) or 'TRUE'), tuple(params)

    def single_segment(self) -> Optional[Tuple[str, str]]:
        """(dimensión, segmento) si hay exactamente un filtro con un solo valor; None si hay 0 o varios."""
        act = self.active_dims
        if len(act) == 1:
            dim, vals = next(iter(act.items()))
            if len(vals) == 1:
                return dim, vals[0]
        return None

    def describe(self) -> str:
        """Filtros activos, para el subtítulo de cada página. El período solo se menciona si no es la ventana completa."""
        d0, dn = bounds()
        parts = [] if (self.start, self.end) == (d0, dn) else [f"{self.start:%d-%m-%Y} a {self.end:%d-%m-%Y}"]
        for dim, vals in self.active_dims.items():
            parts.append(f"{DIMS[dim]}: {', '.join(vals)}")
        if self.excluir_masivos:
            parts.append('sin eventos masivos')
        return ' · '.join(parts)

    def subtitle(self, prefix: str = '') -> None:
        """Subtítulo de la página: la actividad o métrica que cubre y los filtros activos, si los hay."""
        text = ' · '.join(p for p in (prefix, self.describe()) if p)
        if text:
            st.caption(text)


def get_filters() -> Filters:
    return st.session_state['filters']


def apply_event_filters(df: pd.DataFrame, f: Filters, date_col: str = 'date') -> pd.DataFrame:
    """Filtra una tabla de eventos ya enriquecida con atributos de cohorte (columnas `c_<dim>`)."""
    mask = df[date_col].between(f.start, f.end)
    for dim, vals in f.active_dims.items():
        mask &= df[f'c_{dim}'].isin(vals)
    return df[mask]


# --------------------------------------------------------------------------------------------
# Tablas de eventos (enriquecidas con la cohorte del usuario en el día de referencia)
# --------------------------------------------------------------------------------------------
def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega los atributos de cohorte (`c_<dim>`) que tenía el usuario en `ref_date`.

    Así los eventos se filtran y agrupan con las mismas dimensiones que las métricas.
    """
    keys = df[['id', 'ref_date']].drop_duplicates()
    cur = _connection().cursor()
    cur.register('keys_df', keys)
    cols = ', '.join(f'u.{d} AS c_{d}' for d in DIMS)
    attrs = cur.execute(
        f'SELECT k.id, k.ref_date, {cols} FROM keys_df k JOIN ud u ON u.id = k.id AND u.d = k.ref_date'
    ).df()
    return df.merge(attrs, on=['id', 'ref_date'], how='left')


@st.cache_data(show_spinner=False)
def altas_bajas() -> pd.DataFrame:
    ab = pd.read_parquet(OUT / 'altas_bajas.parquet')
    is_baja = ab['event_type'].isin(['baja', 'baja_addon'])
    # La cohorte de una baja es la de su último día activo; la de un alta, la de su primer día
    ab['ref_date'] = ab['last_active_date'].where(is_baja, ab['date'])
    ab = _enrich(ab)
    ab['baja_masiva'] = ab['baja_masiva'].astype('boolean').fillna(False).astype(bool)
    ab['es_primera_alta'] = ab['es_primera_alta'].astype('boolean').fillna(False).astype(bool)
    ab['clase'] = classify_flow(ab)
    return ab


def classify_flow(ab: pd.DataFrame) -> pd.Series:
    """Clase de cada evento de servicio para el gráfico de flujo.

    Las bajas orgánicas se separan según si el usuario volvió dentro de la ventana (`gap_days` no nulo):
    así se ve la intermitencia sin aplicar un umbral de días.
    """
    clase = pd.Series(None, index=ab.index, dtype='object')
    alta, baja = ab['event_type'] == 'alta', ab['event_type'] == 'baja'
    vuelve = ab['gap_days'].notna()
    clase[alta & ab['es_primera_alta']] = 'Alta nueva'
    clase[alta & ~ab['es_primera_alta']] = 'Reactivación'
    clase[baja & ab['baja_masiva']] = 'Baja masiva'
    clase[baja & ~ab['baja_masiva'] & ~vuelve] = 'Baja sin retorno'
    clase[baja & ~ab['baja_masiva'] & vuelve] = 'Baja con retorno'
    clase[ab['event_type'] == 'alta_addon'] = 'Alta addon'
    clase[ab['event_type'] == 'baja_addon'] = 'Baja addon'
    return clase


@st.cache_data(show_spinner=False)
def reactivaciones() -> pd.DataFrame:
    r = pd.read_parquet(OUT / 'reactivaciones.parquet')
    r['ref_date'] = r['date']
    return _enrich(r)


@st.cache_data(show_spinner=False)
def cambios_plan() -> pd.DataFrame:
    c = pd.read_parquet(OUT / 'cambios_plan.parquet')
    c['ref_date'] = c['date']
    return _enrich(c)


# --------------------------------------------------------------------------------------------
# Métricas precalculadas
# --------------------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def metricas() -> pd.DataFrame:
    return pd.read_parquet(OUT / 'metricas.parquet')


@st.cache_data(show_spinner=False)
def vida(agrupacion: str) -> pd.DataFrame:
    name = 'vida_plan' if agrupacion == 'plan_label' else 'vida_categoria'
    v = pd.read_parquet(OUT / f'{name}.parquet')
    return v.reset_index() if agrupacion not in v.columns else v


@st.cache_data(show_spinner=False)
def km_curvas() -> pd.DataFrame:
    return pd.read_parquet(OUT / 'km_curvas.parquet')


@st.cache_data(show_spinner=False)
def retencion_nuevos() -> pd.DataFrame:
    r = pd.read_parquet(OUT / 'retencion_nuevos.parquet')
    r.index = r.index.astype(str)
    return r


def _top_pairs(df: pd.DataFrame, cols: List[str], n: int = 2) -> str:
    """'Básico → Esencial (829), Plus → Esencial (52)': los n grupos más grandes del día."""
    g = df.groupby(cols).size().sort_values(ascending=False).head(n)
    return ', '.join(f"{' → '.join(map(str, k)) if isinstance(k, tuple) else k} ({v:,})".replace(',', '.')
                     for k, v in g.items())


@st.cache_data(show_spinner=False)
def eventos_clave() -> pd.DataFrame:
    """Días con eventos masivos, para anotar las series de tiempo y explicarlos en el Resumen.

    - Fin de convenio: bajas masivas (un partner B2B termina su convenio y sus usuarios pierden el plan el mismo
      día). Baja el número de usuarios y el MRR.
    - Migración de catálogo: cientos de usuarios pasan el mismo día del mismo plan A al mismo plan B (decisión de
      Zapping o del partner). Cambia el plan y el MRR, pero no el número de usuarios.
    Solo se marcan las migraciones de 200 o más usuarios en el día.
    """
    ab = pd.read_parquet(OUT / 'altas_bajas.parquet')
    mb = ab[ab['baja_masiva'] == True].assign(
        partner=lambda x: x['category'].str.title() + ' (partner ' + x['partner_id'].astype('Int64').astype(str) + ')')
    mass = mb.groupby('date').agg(usuarios=('id', 'size'), efecto_mrr=('mrr_usd', 'sum')).reset_index()
    mass['efecto_mrr'] *= -1
    mass['efecto_activos'] = -mass['usuarios']
    mass['detalle'] = [_top_pairs(mb[mb['date'] == d], ['partner']) for d in mass['date']]
    mass['tipo'] = 'Fin de convenio'
    cp = pd.read_parquet(OUT / 'cambios_plan.parquet')
    mc = cp[cp['migracion_masiva']]
    mig = mc.groupby('date').agg(usuarios=('id', 'size'), efecto_mrr=('delta_mrr_usd', 'sum')).reset_index()
    mig = mig[mig['usuarios'] >= 200]
    mig['efecto_activos'] = 0
    mig['detalle'] = [_top_pairs(mc[mc['date'] == d], ['prev_package_name', 'new_package_name']) for d in mig['date']]
    mig['tipo'] = 'Migración de catálogo'
    cols = ['date', 'tipo', 'detalle', 'usuarios', 'efecto_activos', 'efecto_mrr']
    return pd.concat([mass, mig], ignore_index=True)[cols].sort_values('date').reset_index(drop=True)
