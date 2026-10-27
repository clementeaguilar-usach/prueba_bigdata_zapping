"""Métricas calculadas al vuelo sobre `user_day` con los filtros del usuario.

Replican las definiciones del notebook (ver README):
- Métricas de stock (activos, MRR, ARPPU, antigüedad): último día disponible de cada mes.
- MAU: usuarios del snapshot mensual con `time_watched > 0`. `time_watched` son los segundos de consumo de los
  últimos 30 días, así que en el snapshot indica si el usuario consumió durante el mes.
"""
from typing import Optional

import pandas as pd

from core import data
from core.data import Filters


def _snap_days(f: Filters) -> pd.DataFrame:
    snap = data.snapshot_days()
    return snap[(snap['d'] >= f.start) & (snap['d'] <= f.end)]


def snapshot(f: Filters, dim: Optional[str] = None) -> pd.DataFrame:
    """Activos, MRR (USD), pagadores y ARPPU por mes (y segmento) en el snapshot mensual."""
    snap = _snap_days(f)
    if snap.empty:
        return pd.DataFrame(columns=['month', 'segment', 'activos', 'mrr', 'pagadores', 'arppu', 'parcial'])
    where, params = f.sql(with_dates=False)
    seg = f', {dim} AS segment' if dim else ''
    days = ', '.join('?' * len(snap))
    out = data.query(
        f'SELECT month{seg}, count(*) AS activos, sum(mrr_usd_total) AS mrr, sum(is_paying::INT) AS pagadores '
        f'FROM ud WHERE d IN ({days}) AND {where} GROUP BY ALL ORDER BY ALL',
        tuple(d.to_pydatetime() for d in snap['d']) + params)
    out['arppu'] = out['mrr'] / out['pagadores'].where(out['pagadores'] > 0)
    return out.merge(snap[['month', 'parcial']], on='month', how='left')


def daily(f: Filters) -> pd.DataFrame:
    where, params = f.sql()
    return data.query(
        f'SELECT d, count(*) AS activos, sum(mrr_usd_total) AS mrr FROM ud WHERE {where} GROUP BY d ORDER BY d',
        params)


def mau(f: Filters, dim: Optional[str] = None) -> pd.DataFrame:
    snap = _snap_days(f)
    if snap.empty:
        return pd.DataFrame(columns=['month', 'segment', 'suscriptores', 'mau', 'ratio'])
    where, params = f.sql(with_dates=False)
    seg = f', {dim} AS segment' if dim else ''
    days = ', '.join('?' * len(snap))
    out = data.query(
        f'SELECT month{seg}, count(*) AS suscriptores, sum(watched::INT) AS mau FROM ud '
        f'WHERE d IN ({days}) AND {where} GROUP BY ALL ORDER BY ALL',
        tuple(d.to_pydatetime() for d in snap['d']) + params)
    out['ratio'] = out['mau'] / out['suscriptores']
    return out


def engagement_daily(f: Filters) -> pd.DataFrame:
    """Por día: fracción de activos con consumo en los últimos 30 días y horas consumidas (mediana de quienes ven)."""
    where, params = f.sql()
    out = data.query(
        f'SELECT d, count(*) AS activos, sum(watched::INT) AS con_consumo, '
        f'median(time_watched) FILTER (WHERE watched) / 3600 AS horas_mediana FROM ud WHERE {where} '
        f'GROUP BY d ORDER BY d', params)
    out['ratio'] = out['con_consumo'] / out['activos']
    return out


def tenure(f: Filters) -> pd.DataFrame:
    snap = _snap_days(f)
    if snap.empty:
        return pd.DataFrame(columns=['month', 'tenure_bucket', 'usuarios'])
    where, params = f.sql(with_dates=False)
    days = ', '.join('?' * len(snap))
    return data.query(
        f'SELECT month, tenure_bucket, count(*) AS usuarios FROM ud WHERE d IN ({days}) AND {where} '
        f'GROUP BY ALL ORDER BY ALL', tuple(d.to_pydatetime() for d in snap['d']) + params)


def mrr_local(f: Filters) -> pd.DataFrame:
    snap = _snap_days(f)
    if snap.empty:
        return pd.DataFrame(columns=['month', 'country_iso', 'currency', 'mrr_local'])
    where, params = f.sql(with_dates=False)
    days = ', '.join('?' * len(snap))
    return data.query(
        f'SELECT month, country_iso, currency, sum(mrr_local_total) AS mrr_local FROM ud '
        f'WHERE d IN ({days}) AND {where} GROUP BY ALL ORDER BY ALL', tuple(d.to_pydatetime() for d in snap['d']) + params)


def churn(f: Filters, dim: Optional[str] = None) -> pd.DataFrame:
    """Churn 1M/3M/6M precalculado en el notebook (una dimensión a la vez).

    No se puede recalcular con filtros combinados: se muestra la dimensión elegida y, si hay un filtro
    sobre esa misma dimensión, solo sus segmentos.
    """
    m = data.metricas()
    metric = '4.6_churn_organico' if f.excluir_masivos else '4.6_churn'
    out = m[(m['metric'] == metric) & (m['dimension'] == (dim or 'total'))].copy()
    sel = f.active_dims.get(dim) if dim else None
    if sel:
        out = out[out['segment'].isin(sel)]
    return out.rename(columns={'sub_segment': 'horizonte', 'month': 'cohort_month'})
