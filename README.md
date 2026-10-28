# Prueba Big Data Zapping 2026: Métricas de negocio

Autor: Clemente Aguilar Osorio

La solución está en [`prueba_big_data.ipynb`](prueba_big_data.ipynb) y parte de [`snapshot_subscriber.parquet`](snapshot_subscriber.parquet): snapshots diarios de los planes activos por usuario entre el 2026-01-01 y el 2026-09-07, con 10.001 usuarios de 4 países.

Este documento reúne **todos los criterios usados para interpretar los datos**, con la evidencia que respalda cada uno. Se actualiza cada vez que se agrega o cambia un criterio; el historial está en [Registro de cambios](#registro-de-cambios).

## Ejecución

```bash
python --version                 # 3.9.6
pip install -r requirements_entrega.txt
jupyter nbconvert --to notebook --execute prueba_big_data.ipynb
```

- **[`requirements_entrega.txt`](requirements_entrega.txt):** es el que se entrega. Tiene solo las bibliotecas que usa el notebook; pip resuelve sus dependencias. Se verificó instalándolo en un entorno limpio con Python 3.9.6 y ejecutando el notebook completo.
- **[`requirements.txt`](requirements.txt):** congela el entorno de desarrollo completo, incluidos Jupyter y el dashboard.
- **[`dashboard/requirements.txt`](dashboard/requirements.txt):** dependencias del dashboard publicado.

El notebook se ejecuta de forma secuencial (~1,5–2 min, pico de memoria ~7,4 GB) y termina con una sección de validaciones (`assert`). Las tablas resultantes se exportan a `outputs/*.parquet` para el dashboard.

| Actividad | Resultado (`pandas.DataFrame`) |
|---|---|
| 1. Altas y bajas diarias | `df_altas_bajas`, más los resúmenes `daily_events` y `monthly_events` |
| 2. Reactivaciones | `df_reactivaciones` |
| 3. Upgrade / downgrade | `df_cambios_plan` |
| 4. Métricas por cohorte | `df_metricas` (formato largo), `df_vida_plan`, `df_vida_categoria`, `df_retencion_nuevos` |
| 5. Dashboard | [`dashboard/`](dashboard/), ver [Dashboard](#dashboard-actividad-5). El enlace publicado va en la celda *Dashboard*, al inicio del notebook |
| 6. KDD (opcional) | `usuarios` (perfil de cada usuario), `df_perfiles_resumen`, `df_riesgo`, `df_riesgo_cupon`, `df_cox`, `df_mrr_en_juego`. Ver criterios 16 y 17 |

### Respuestas del equipo de Zapping
Consultas hechas al equipo de Big Data sobre el enunciado:
1. **Proxy de `created_user`:** se valida el uso de la fecha mínima de `created` de cada usuario (criterio 5).
2. **`time_watched`:** son los segundos totales de consumo de los **últimos 30 días**. Cambia la definición del MAU (criterio 9).
3. **Dashboard:** puede publicarse y compartirse con el equipo con un enlace en el notebook (ver [Publicación](#publicación)).
4. **Intermitencia:** salir y volver (alta → baja → alta) es natural en el rubro y debe mostrarse. Se elimina `GRACE_DAYS` (criterio 2).

### Parámetros

Están en la celda de parámetros del notebook. Todos los umbrales que dependen de los datos se calculan en tiempo de ejecución.

| Parámetro | Valor | Uso |
|---|---|---|
| `FX_TO_USD` | CLP 991,40 · BRL 5,02 · PEN 3,45 por USD | Conversión a USD (tasas fijas al 26-10-2026) |
| `MASS_TUKEY_K` | 3 | Factor de la cerca de Tukey para volúmenes atípicos |
| `MASS_CHURN_MIN_SHARE` | 0,5 | Fracción mínima de la base de un grupo para calificar una baja como masiva |
| `TOP_N` | 8 | Categorías visibles en cohortes de alta cardinalidad (el resto va a "Otros") |
| `KDD_MIN_DIAS_OBS` | 30 | Días observables mínimos para asignar un perfil (si no, "Observación corta") |
| `KDD_K` · `KDD_ARI_MIN` | 3–8 · 0,9 | Número de perfiles evaluados y estabilidad mínima para aceptar uno |
| `RIESGO_MESES` | 24 | Meses de antigüedad en la curva de riesgo |
| `VENTANA_FACTOR` · `VENTANA_MIN_BAJAS` | 1,5 · 30 | Ventana de riesgo: riesgo > 1,5 × la mediana de la curva y ≥ 30 bajas |
| `COX_CORTE_DIAS` | 90 | Corte de tramos para revisar riesgos proporcionales en el modelo de Cox |

## Dashboard (actividad 5)

```bash
streamlit run dashboard/app.py   # requiere haber ejecutado antes el notebook (lee outputs/*.parquet)
```

Está hecho en Streamlit + Plotly. Las métricas que dependen de los filtros se calculan al vuelo con DuckDB sobre `outputs/user_day.parquet`, sin cargarlo completo en memoria.

| Página | Contenido |
|---|---|
| Resumen | Indicadores del mes de referencia con variación contra el mes anterior (activos, MRR, ARPPU, MAU/suscriptores, churn 1M). MRR y activos diarios con los eventos masivos marcados, y tabla de eventos masivos (qué pasó, usuarios, efecto en activos y en MRR) |
| Flujo de clientes (3.1) | Altas (nuevas y reactivaciones) contra bajas (sin retorno, con retorno y masivas) por semana o mes, con el total de contrataciones y de abandonos de cada barra. Activos diarios. Planes contratados y planes con que se van (o cualquier otra dimensión), con totales y neto por segmento. Addons contratados y cancelados |
| Reactivaciones (3.2) | Indicadores de intermitencia (% de usuarios que salen y vuelven, mediana de días fuera, % que vuelve al mismo plan), distribución de los días fuera, reactivaciones por usuario y por mes, y, por plan con que se fue, cuántos vuelven al mismo plan o a otro (con las combinaciones más frecuentes) |
| Cambios de plan (3.3) | Cambios por mes y tipo, impacto neto en MRR, Sankey plan anterior → nuevo y detalle de las migraciones masivas |
| Ingresos (4.2–4.3) | MRR mensual y ARPPU por dimensión, MRR en moneda local por país y MRR diario |
| Engagement (4.4) | MAU contra suscriptores al cierre de mes, ratio MAU/suscriptores, consumo diario (fracción de activos con consumo en 30 días y horas medianas) y mapa de calor por dimensión |
| Retención (4.1, 4.5, 4.6) | Composición por antigüedad, churn 1M/3M/6M por dimensión, curvas de Kaplan–Meier por plan o categoría y retención de usuarios nuevos por cohorte |
| Perfiles y riesgo (6) | Tamaño, MRR y churn de cada perfil; mapa de calor de lo que distingue a cada uno; riesgo mensual de baja por antigüedad (total, segmento, cupón o perfil) con la ventana de riesgo; riesgo alrededor del fin del cupón; hazard ratios del modelo de Cox, y MRR en juego por perfil |

**Filtros globales** (barra lateral, aplican a todas las páginas): período; país, segmento, categoría, plan base, canal de adquisición, cupón, antigüedad y perfil (combinables); *Excluir eventos masivos* (en el churn, muestra el churn orgánico).

**Criterios de diseño y lectura:**
- **Misma definición que el notebook.** El dashboard reproduce las métricas sin redefinirlas: snapshot del último día del mes para métricas de stock, la misma regla de MAU, etc. Se verificó que MRR, ARPPU, MAU, ratio y activos diarios coinciden exactamente con `outputs/metricas.parquet` y `outputs/eventos_diarios.parquet`.
- **Cohorte de un evento.** Cada evento se cruza con los atributos que tenía el usuario el día de referencia: el día del alta, el último día activo en una baja, el día del cambio. Así los eventos se filtran con las mismas dimensiones que las métricas.
- **Qué no responde a los filtros combinados.** El churn, las curvas de vida media y la matriz de retención están precalculados en el notebook por una dimensión a la vez, porque requieren los spells completos de cada usuario. El churn se muestra para la dimensión elegida en "Agrupar por" y respeta el filtro de esa misma dimensión. La página lo indica.
- **Visualización:**
  - Un solo eje por gráfico.
  - Paleta categórica fija de 8 colores, donde cada segmento conserva su color aunque cambien los filtros; desde el noveno segmento y "Otros" se usa el neutro.
  - Las bajas sin retorno usan el color de las bajas con un rayado diagonal (misma entidad, otra variante); las masivas van en el color de contexto.
  - Cada figura tiene un pie numerado (*Figura n.*) que explica qué se está mirando.
  - Eventos masivos en las series diarias: línea continua para el fin de convenio y punteada para la migración de catálogo. Los gráficos de usuarios marcan solo el fin de convenio, porque las migraciones cambian el plan y el MRR pero no el número de usuarios.
- **Identidad visual de Zapping** ([brand.zapping.com](https://brand.zapping.com/)), sin logos. Los valores salen de los tokens CSS del Brand Hub. El tema está en [`.streamlit/config.toml`](.streamlit/config.toml), y los colores de los gráficos en [`dashboard/core/charts.py`](dashboard/core/charts.py).
  - **Color binario:** fondo negro de marca `#040405`, Zapink Pulse `#e90068` como color primario y texto blanco. No hay degradados ni amarillo, y el glow no se usa.
  - **Jerarquía sin gris:** texto secundario, ejes, grilla y bordes usan opacidad de blanco (`white-α`), no grises arbitrarios.
  - **Tipografía:** Poppins, el respaldo que la propia marca declara para ZappingFont. Esta no se pudo enlazar porque el Brand Hub no permite cargarla desde otro dominio (no envía CORS). El cuerpo va en Medium 500, porque la marca no tiene Regular, y los títulos en Bold Italic 700. Sobre rosa, el peso mínimo es Bold.
  - **Gráficos:** Zapink marca el argumento. Un gráfico con una sola serie va en Zapink; si una serie importa más que otra, esa va en Zapink y el resto en opacidad (por ejemplo, MAU contra suscriptores). Las categorías usan los acentos indigo → violet → fucsia, en el orden que fija la marca. Las magnitudes de los heatmaps van en Zapink con opacidad creciente, y los tramos ordenados (antigüedad) en escala de opacidad de blanco.
  - **Daltonismo:** en el paso 500, los tres acentos de marca tienen la misma luminosidad y se confunden con deuteranopía (ΔE OKLab 2,6 entre indigo y violet). Por eso se usan indigo‑500, violet‑300 y fucsia‑600, más el blanco de marca como cuarto color: los 4 pares superan ΔE 15 con visión normal y con daltonismo simulado (Machado 2009). Así quedan cubiertas país, segmento y cupón.
  - **Desviación de la regla de marca:** la marca permite como máximo 3 acentos por pieza. Las dimensiones con más de 4 valores (plan, canal, categoría) usan además otros pasos de las mismas escalas. Esos 8 colores se distinguen cuando están contiguos, por ejemplo en barras apiladas, pero en un gráfico de líneas con muchas series conviene apoyarse en la leyenda, el hover o la tabla.
  - Cada gráfico tiene su tabla equivalente ("Ver tabla") con descarga en CSV.
  - Septiembre se marca como mes parcial.

### Publicación
El equipo de Zapping autorizó publicar el dashboard. Está preparado para **Streamlit Community Cloud** (Vercel no sirve: ejecuta funciones *serverless* de vida corta y Streamlit necesita un servidor Python permanente con websockets).

1. Ejecutar el notebook, para que `outputs/` esté al día.
2. Subir el proyecto a un repositorio de GitHub, **idealmente privado**. `outputs/user_day.parquet` tiene datos por usuario y día. El `.gitignore` ya excluye el parquet crudo, que el dashboard no necesita.
3. En [share.streamlit.io](https://share.streamlit.io): *Create app* → repositorio, rama y archivo principal `dashboard/app.py`. En *Advanced settings*, elegir Python 3.12 o anterior (el dashboard no requiere 3.9.6, solo el notebook).
4. Instala [`dashboard/requirements.txt`](dashboard/requirements.txt), que está junto a `app.py` y tiene solo las 6 dependencias del dashboard.
5. Restringir el acceso a los correos del equipo (*Settings → Sharing*) y pegar el enlace en la celda *Dashboard*, al inicio del notebook.

---

## Criterios de interpretación

### 1. Granularidad y ventana
- Cada snapshot (`date`, siempre a las 03:30) representa el estado de **un día** y se normaliza a fecha (`d`).
- No falta ningún día entre `DAY0 = 2026-01-01` y `DAYN = 2026-09-07` (250 días).

### 2. Regla de actividad e intermitencia
- **Criterio literal del enunciado:** si un usuario-plan no aparece un día, ese día no lo tiene activo. Un salto de 1 día genera, por tanto, una baja seguida de una alta (reactivación).
- **Criterio:** se aplica sin tolerancia en todo el notebook, incluidas la vida media (4.5) y el churn (4.6). El equipo de Zapping confirmó que la intermitencia (alta → baja → alta) es un comportamiento natural del rubro, así que es información de negocio y no ruido.
- **Cómo se describe la intermitencia:**
  - `gap_days`: en una alta, los días que el usuario estuvo fuera; en una baja, los días que tardará en volver (NaN si no vuelve dentro de la ventana).
  - En el notebook, la sección *Intermitencia* (actividad 2) y en el dashboard las páginas *Flujo de clientes* y *Reactivaciones*.

  | Días sin registro | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
  |---|---|---|---|---|---|---|---|
  | Reactivaciones | 1.204 | 388 | 186 | 140 | 136 | 81 | 71 |
  | % acumulado | 39,7% | 52,6% | 58,7% | | 67,8% | | 72,8% |

  - El 16,5% de los usuarios sale y vuelve al menos una vez dentro de la ventana, y 345 lo hacen 3 veces o más.
  - La mediana de días fuera es 2.
  - El 58,7% de las 5.110 bajas orgánicas vuelve dentro de la ventana. Es una cota inferior: las bajas recientes tuvieron menos tiempo para volver.
- **Versión anterior:** usaba `GRACE_DAYS = 3`, el codo de la tabla anterior. Marcaba como técnicos los eventos con `gap_days <= 3`: 1.778 de 7.731 bajas. También toleraba esos saltos en la vida media y el churn. Se eliminó por la confirmación de Zapping (ver [Registro de cambios](#registro-de-cambios)).
- **Spell:** período continuo de presencia de un usuario (o de un usuario en un plan). Lo construye `build_spells(frame, keys, tol)`: se abre un spell nuevo cuando faltan más de `tol` días entre dos registros.

### 3. Censura de la ventana
- Los usuarios presentes en `DAY0` ya estaban activos antes, así que **no** se cuentan como alta ese día (censura por la izquierda).
- Los presentes en `DAYN` siguen activos y **no** se cuentan como baja (censura por la derecha).
- La fecha de una baja es el **primer día sin plan**, y `last_active_date` es el último día con plan. Así se cumple que `activos(d) = activos(d-1) + altas(d) − bajas(d)`, lo que se valida en el notebook.

### 4. Plan principal del día
- Hay 4.799 usuario-días con **2 planes base** a la vez, que corresponden al cruce durante un cambio de plan. Se considera vigente el de `created` más reciente, es decir el plan nuevo.
  - **Verificación:** esta regla podría generar cambios espurios que se revierten al día siguiente (A → B → A). Solo ocurre en 34 de 6.182 cambios, casi todos ZAPPING PRO V2 → Pro, así que el efecto es despreciable.
- Hay 376 usuario-días que solo tienen addons. En esos casos el plan principal del día es el addon.
- `plan_label` = nombre normalizado (NFKC, sin espacios extremos) + país. Hace falta porque el mismo nombre existe en varios países y monedas ("Plus" en CL, EC y PE) y con variantes de espacios.

### 5. Antigüedad del usuario
- El campo `created_user` que indica el enunciado **no existe** en el parquet. Se usa como proxy la fecha mínima de `created` (creación de plan) de cada usuario (`user_created`). El equipo de Zapping validó este proxy.
- Es una cota inferior de la antigüedad real: si el usuario tuvo planes anteriores cuyo registro ya no aparece, su creación fue antes.
- Tramos de antigüedad: `<1M`, `1-3M`, `3-6M`, `6-12M`, `1-2A`, `>2A`.

### 6. Origen de una reactivación
- `dentro_ventana`: el usuario tuvo un spell anterior en los datos. Su último plan es el del último día de ese spell.
- `previo_ventana`: el usuario aparece por primera vez después de `DAY0`, pero su `user_created` es **más de 2 días anterior** a esa aparición. Su último plan no es observable.
  - **Evidencia del umbral de 2 días.** En los usuarios que aparecen por primera vez, la diferencia entre la primera aparición y `created` es -1 día en 645 casos, 0 en 2.465, 1 en 15 y 2 en 7. Después aparece una cola dispersa (52, 98, 127… días). Los valores -1 y 0 reflejan el desfase entre la hora del snapshot y la de creación (UTC), así que más de 2 días indica historial previo.
- Resultado: 3.029 reactivaciones `dentro_ventana` y 154 `previo_ventana`.

### 7. Ingresos (MRR)
- Solo suman las filas con `is_mrr_contributor = 1`.
- **Precio mensual:** es `price_paid`, salvo en planes multi-período (`periods_in_months > 1`) donde `price_paid > original_price`. Ahí `price_paid` registra el cobro del período completo (p.ej. 199.000 CLP en un plan anual de 19.900/mes) y se divide por `periods_in_months`. `original_price` es un precio de lista mensual.
- **MRR** = suma del precio mensual normalizado de todos los planes (base + addons) activos en el snapshot.
- **Moneda:** se consolida en USD con **tasas fijas al 26-10-2026** y también se reporta en moneda local por país. EC trae algunas filas en BRL y PE algunas en USD; se convierten según su propia moneda.
  - Con tasas fijas, las variaciones del MRR en USD reflejan solo cambios en la base y en los precios, no el tipo de cambio. Se evaluó usar tasas promedio mensuales y se descartó por decisión del autor (ver [Registro de cambios](#registro-de-cambios)).

### 8. ARPPU
- `ARPPU = MRR / usuarios pagadores`. Un usuario es pagador si su MRR del día es mayor que 0, lo que excluye demos, planes gratuitos y no contribuyentes.

### 9. MAU
- `time_watched` son los segundos de consumo de los **últimos 30 días** (ventana móvil, confirmado por Zapping). Por eso sube y baja de un día a otro.
- **Criterio:** un usuario es MAU en el mes si tiene `time_watched > 0` en el **snapshot de fin de mes**, es decir, si consumió en los 30 días previos. Es la definición estándar de MAU a 30 días y usa la misma base que el MRR y el ARPPU.
- **Por qué no "algún día del mes":** con una ventana móvil, esa regla cuenta como activo en enero a quien vio algo el 20 de diciembre. Sobreestima el ratio en casi todos los meses, hasta 8 pp. Junio es la excepción: ahí esa regla incluye en la base a los usuarios B2B que se fueron el día 12, de bajo consumo.

  | Mes | Regla anterior (algún día) | Snapshot de fin de mes |
  |---|---|---|
  | 2026-01 | 72,6% | 64,8% |
  | 2026-05 | 71,4% | 63,6% |
  | 2026-06 | 67,9% | 79,5% |
| 2026-08 | 80,6% | 75,7% |

- Se reporta también el ratio `MAU / suscriptores` (activos en el snapshot). Septiembre es parcial: su snapshot (07-09) cubre del 09-08 al 07-09.
- **Valores atípicos:** 344 usuarios superan los 30 días de consumo en 30 días (máximo ~104 días en B2C y ~2.874 en una cuenta COUPON), lo que indica pantallas simultáneas o cuentas compartidas. No afectan al MAU, que solo mira si el valor es mayor que 0. En el dashboard, las horas se resumen con la mediana.
- `time_watched` es igual en todas las filas de un usuario-día (se valida), así que por usuario-día se toma un único valor.

### 10. Cambios de plan (upgrade / downgrade)
- Hay un cambio cuando el `package_id` del plan base del día `d` es distinto al del día `d-1`, con el usuario activo **ambos días**. Un cambio tras un salto queda registrado como baja + reactivación con `mismo_plan = False`.
- **Clasificación** según el precio de lista mensual en USD (`original_price` convertido):
  - `upgrade` si sube más de 1% y `downgrade` si baja más de 1%.
  - `lateral` si queda dentro de ±1%: migración o cambio de versión, p.ej. Pro → ZAPPING PRO V2.
  - `reajuste_precio` si el plan conserva el nombre y solo cambia de `package_id` (p.ej. Zapping Full de 18.900 a 19.900 CLP). Es un cambio de catálogo y no una decisión del usuario.
- Solo se consideran **planes base**. Contratar o cancelar un addon no es upgrade ni downgrade; queda en 3.1 como `alta_addon` o `baja_addon`.
- Resultado: 1.893 upgrades, 3.479 downgrades, 633 laterales y 177 reajustes de precio.

### 11. Eventos masivos (bajas y migraciones)
Algunos días concentran volúmenes que no corresponden a decisiones individuales y distorsionan las métricas. Se detectan con umbrales **derivados de los datos**. La primera versión usaba un umbral fijo de 50 usuarios, que no tenía justificación y clasificaba mal parte de los casos (ver [Registro de cambios](#registro-de-cambios)).

**Volumen atípico (común a ambos tipos).** Los conteos de eventos por (día, grupo) tienen una cola muy pesada: mediana 1, Q3 2 y máximo 2.359. Por eso se usa la **cerca de Tukey para outliers extremos sobre el log10 de los conteos**: `umbral = 10^(Q3 + k·IQR)` con `k = MASS_TUKEY_K = 3` (función `tukey_fence_log`). Con los datos actuales el umbral queda en **16 usuarios** tanto para bajas como para cambios de plan. Como referencia, la mediana diaria es de 14,5 bajas y 4 cambios de plan **en total**.

#### 11.1 Baja masiva (`baja_masiva`)
- **Grupo:** el partner B2B (`partner_id`) o, si no tiene partner, el plan (`plan_label`).
- **Criterio:** el volumen del (día, grupo) es atípico **y** el grupo pierde al menos `MASS_CHURN_MIN_SHARE` = 50% de los usuarios activos que tenía el día anterior.
- **Por qué hace falta la proporción:** los (día, grupo) con volumen atípico son de dos tipos muy distintos.

  | Fecha | Grupo | Bajas | Base del grupo | % de la base | ¿Masiva? |
  |---|---|---|---|---|---|
  | 2026-06-12 | partner 1351 (EC, BUNDLE) | 2.359 | 2.535 | **93,1%** | Sí |
  | 2026-06-12 | partner 2181 (EC, RESELLER) | 262 | 262 | **100%** | Sí |
  | 2026-01-12 | partner 1271 (EC, HARDBUNDLE) | 135 | 1.181 | 11,4% | No |
  | 2026-02-11 | partner 1271 | 127 | 1.232 | 10,3% | No |
  | 2026-08-11 | plan Fan (EC, cupón/prepago) | 22 | ~122 | 18,0% | No |
  | … 11 días más | partner 1271 | 51–120 | ~1.300 | 4–9% | No |

  - Los partners 1351 y 2181 pierden casi toda su base en un día, lo que es compatible con el **término de un convenio**.
  - El partner 1271 pierde entre el 4% y el 11% de su base **todos los meses, entre el día 10 y el 12**: es su ciclo de facturación. Es **churn recurrente** y debe contar como orgánico. El caso de Fan del 2026-08-11 parece un vencimiento conjunto de cupones o prepagos, tampoco es un fin de convenio.
  - Con volumen atípico no hay ningún caso entre el 18% y el 93%, así que cualquier corte en ese rango da el mismo resultado; el 50% no es un valor sensible.
- **Resultado:** 2.621 bajas masivas, todas del 2026-06-12. Las columnas `bajas_grupo_dia` y `pct_base_grupo` quedan en `df_altas_bajas` como evidencia.

#### 11.2 Migración masiva (`migracion_masiva`)
- **Grupo:** el par (plan anterior → plan nuevo, por `package_id`) en el mismo día.
- **Criterio:** solo volumen atípico (más de 16 usuarios con los datos actuales).
- **Por qué no se exige una proporción de la base:** las migraciones de catálogo se ejecutan en **tandas de varios días** con proporciones bajas cada día. Por ejemplo, Básico → Demo EC movió el 11%, 9%, 16% y 30% de la base de Básico el 17, 18, 21 y 28 de abril. Una proporción mínima las dejaría fuera.
- **Señal descartada:** también se probó si los planes nuevos de una migración se crean en lote (`created` concentrado en pocos minutos), pero no separa los casos de forma consistente.
- **Resultado:** 4.656 de 6.182 cambios (34 pares-día) son migraciones masivas. Por ejemplo, Básico → Esencial (2026-02-12, 829), Básico → Demo EC (abril, ~1.450), Esencial ↔ Esencial Paramount (junio y agosto) y los cambios a planes "V2" (2026-06-01).

**Uso de las marcas:**
- El **churn orgánico** (4.6) excluye las bajas masivas.
- En la **vida media** (4.5), un plan que termina por una migración masiva o por una baja masiva se trata como censura y no como fin de vida.

### 12. Vida media por plan (4.5)
- **Unidad:** spell de un usuario en un mismo `plan_label`, sin tolerancia a saltos (criterio 2). El spell termina por cancelación, por un salto o por cambio de plan.
- **Truncamiento por la izquierda:** si el spell ya estaba activo en `DAY0`, su vida se mide desde el `created` del plan, y en Kaplan–Meier entra al riesgo recién en `DAY0` (*delayed entry*). Sin esto, la muestra quedaría sesgada hacia planes antiguos.
- **Censura por la derecha:** los spells activos en `DAYN` no tienen fin observado.
- **Censura por eventos masivos:** también se censuran los spells que terminan por una **migración masiva** (4.614) o por una **baja masiva por fin de convenio** (2.621). En ambos casos el usuario no dejó el plan por decisión propia: lo movió Zapping o terminó el contrato del partner. Por eso no informan sobre la vida del plan.
  - **Efecto de censurar los fines de convenio:** cambia sobre todo la categoría `bundle`, donde estaba el partner 1351. Su mediana pasó de 55 a 580 días y su RMST a 365 días de 139 a 287 (con la tolerancia anterior). Con la regla estricta, la mediana queda en 568 días. Demo EC (EC) queda 100% censurado, porque todos sus spells terminaron en el fin de convenio del 2026-06-12, así que su vida no es estimable con estos datos.
- **Efecto de la regla estricta:** las categorías con más intermitencia acortan su vida. La mediana de `hardbundle` baja de 219 a 112 días, la de `b2c` de 91 a 79 y la de Básico (EC) de 229 a 67. En `bundle` casi no cambia (580 → 568).
- **Métricas:** mediana de Kaplan–Meier (NaN si la supervivencia nunca baja del 50% en lo observado), vida media restringida a 365 días (RMST) y, como referencia ingenua, el promedio de los spells cerrados.
- Solo se reportan los planes con al menos 30 spells.
- Si el riesgo inicial es demasiado chico para el truncamiento, `lifelines` falla; en ese caso se ajusta sin entrada tardía y se indica en la columna `metodo`. Pasa en Zapping Full (CL), Zapping Lite+ (CL), Zapping Lite (CL) y Zapping Lite ISPs (BR), y sus medianas largas deben leerse con cautela.

### 13. Churn a 1M, 3M y 6M (4.6)
- **Definición:** de los usuarios activos el primer día del mes *M*, el porcentaje que tuvo una baja antes de *M + k* meses, sin tolerancia a saltos (criterio 2).
- Solo se calcula si la ventana completa cabe en los datos (`M + k <= DAYN`). Por eso el churn a 6M solo existe para enero, febrero y marzo.
- Un usuario que se va y vuelve dentro del horizonte **cuenta** como churn.
- Las cohortes se asignan con los atributos del usuario en *M*.
- **Churn orgánico:** igual al anterior, pero sin contar las bajas masivas (sección 11.1).

| Mes | 1M total | 1M orgánico | 3M total | 3M orgánico | 6M total | 6M orgánico |
|---|---|---|---|---|---|---|
| 2026-01 | 7,9% | 7,9% | 16,2% | 16,2% | 61,6% | 22,7% |
| 2026-03 | 8,9% | 8,9% | 15,9% | 15,9% | 60,6% | 24,3% |
| 2026-06 | 42,3% | 8,2% | 51,7% | 17,6% | — | — |

Con la tolerancia anterior de 3 días, el churn orgánico era ~3 pp menor a 1M (p.ej. enero 5,1%) y ~6 pp menor a 6M (16,5%). La diferencia es la intermitencia de corto plazo.

### 14. Retención de usuarios nuevos
- Usuario nuevo: tiene una alta con `es_primera_alta = True`, es decir, no es reactivación.
- Cohorte = mes de esa primera alta. La retención en *k* es la fracción de la cohorte que tiene algún día activo en el mes *M + k*.

### 15. Cohortes y snapshots
- **Dimensiones:**
  - país;
  - categoría del plan (`category`);
  - segmento B2B/B2C (`is_b2b`);
  - plan base (top 8 `plan_label`);
  - canal de adquisición (top 8 `acquisition`);
  - uso de cupón (`coupon_type` no nulo);
  - tramo de antigüedad.
- **Métricas de stock** (usuarios, MRR, ARPPU): se miden el **último día disponible de cada mes**. Septiembre es parcial (hasta el 07).
- El MAU también se mide en el snapshot (criterio 9), porque `time_watched` ya resume los 30 días previos.

### 16. Perfiles de usuario (KDD)
- **Unidad:** una fila por usuario, con su comportamiento en la ventana. Los 309 usuarios con menos de 30 días observables (`KDD_MIN_DIAS_OBS`) quedan como *Observación corta* y no entran al clustering.
- **Variables del clustering** (solo comportamiento): precio de lista mensual en USD (mediana), addons (media), fracción de días con consumo, horas de consumo en 30 días (mediana en los días con consumo), reactivaciones, días fuera (mediana), upgrades y downgrades individuales (sin migraciones masivas) y antigüedad **al inicio** de la ventana. Las de cola larga entran como `log(1 + x)`, y todas se estandarizan.
- **Qué no entra y por qué:** país, segmento, categoría, canal y cupón solo describen los perfiles. Los resultados (si se fue, el MRR al cierre) tampoco entran. En una primera versión, la cobertura (días activos / observables) y la antigüedad al final de la ventana produjeron un grupo con 99% de bajas que solo repetía quién se fue; por eso se reemplazaron.
- **Método y elección de k:** K-means con `n_init = 20`. Se elige el k con mayor silhouette entre los que tienen ARI medio ≥ 0,9 en 20 remuestreos bootstrap:

  | k | 3 | 4 | 5 | 6 | **7** | 8 |
  |---|---|---|---|---|---|---|
  | Silhouette | 0,274 | 0,297 | 0,319 | 0,352 | **0,366** | 0,340 |
  | ARI medio | 0,979 | 0,951 | 0,869 | 0,802 | **0,958** | 0,816 |
- **Nombres:** salen de reglas sobre el centroide (en desviaciones estándar), no del número de grupo, así que no dependen del orden que asigna K-means. Si dos grupos quedan con el mismo nombre, el notebook se detiene. Con la misma semilla, el resultado es idéntico en el entorno de desarrollo y en uno limpio.
- **Resultado:**

  | Perfil | Usuarios | % MRR al cierre | Se fue | Rasgo |
  |---|---|---|---|---|
  | Activo establecido | 2.834 | 26% | 17% | Ve todos los días; ~10 meses de antigüedad al empezar 2026 |
  | Pasivo | 2.806 | 6% | 13% | Casi no ve; 95% B2B; 58% perdió el servicio por fin de convenio |
  | Recién llegado | 1.831 | 20% | **45%** | Llegó en 2026; 43% con cupón |
  | Intermitente | 1.047 | 12% | 27% | 2 reactivaciones, 6 días fuera (medianas) |
  | Subió de plan | 740 | 19% | 13% | Upgrade por decisión propia |
  | Intensivo con addons | 218 | 7% | 17% | 206 h de consumo, plan de US$ 19 |
  | Bajó de plan | 216 | 4% | 12% | Downgrade por decisión propia |
- Los dos perfiles más chicos (2%) se mantienen: son comportamientos distintos y estables, no ruido.

### 17. Riesgo de baja por antigüedad (KDD)
- **Unidad:** cada periodo continuo de suscripción (como en el churn). La antigüedad se mide desde el inicio del periodo; si empieza en `DAY0`, desde la creación del primer plan, con entrada tardía (supuesto 10 del notebook).
- **Evento y censura:** el evento es la baja. Se censuran los periodos activos en `DAYN` y los que terminan por fin de convenio. Quedan 5.110 bajas en 13.030 periodos.
- **Riesgo mensual:** bajas del mes de antigüedad *m* / meses-persona de exposición en ese mes, con IC 95% de Poisson. **Ventana de riesgo:** riesgo > 1,5 × la mediana de la curva y ≥ 30 bajas. El mínimo de bajas descarta el mes 23, que supera el umbral con solo 20 bajas.
- **Fin del cupón:** en las altas de 2026 con cupón, el mes relativo 0 es el primero a precio completo (`coupon_duration_months` meses después del alta).
- **Modelo de Cox** (`lifelines`, entrada tardía, penalización L2 de 0,01). Covariables al inicio del periodo: segmento, país, cupón, precio de lista (log), pago de varios meses y perfil. `lifelines` no calcula los residuos de Schoenfeld con entrada tardía, así que los riesgos proporcionales se revisan ajustando el modelo en los primeros 90 días y después. El cupón y Perú cambian mucho entre tramos: su efecto depende de la antigüedad. Las variables con menos de 30 bajas no se estiman en un tramo. C-index: 0,785.
- **MRR en juego:** para los activos al cierre, MRR × riesgo de su mes de antigüedad (curva total; después del mes 23, el promedio del segundo año).

---

## Validaciones automáticas
El notebook verifica con `assert`:
1. La identidad de flujo diario: `activos(d) = activos(d-1) + altas(d) − bajas(d)`.
2. Que no haya altas en `DAY0` ni bajas posteriores a `DAYN`.
3. Que todo cambio de plan tenga al usuario con plan base en `d-1` y en `d`.
4. Que el MRR del snapshot coincida con la suma directa sobre el parquet.
5. Que toda reactivación `dentro_ventana` tenga último plan conocido y `gap_days >= 1`.
6. Que primeras altas + reactivaciones = total de altas.
7. Que el MAU no supere la base del snapshot y que `time_watched` sea único por usuario-día.
8. KDD: que cada usuario tenga exactamente un perfil, que las bajas no superen a los usuarios en riesgo en ningún mes y que los hazard ratios sean finitos.

## Hallazgos relevantes para interpretar las métricas
- **2026-06-12:** fin de los convenios de los partners 1351 y 2181 en EC (2.621 usuarios). Explica la caída de usuarios de julio (de 8.077 a 5.574) y el churn total de ~40–55%.
- **Partner 1271 (EC, HARDBUNDLE):** churn mensual recurrente de 4–11% de su base entre los días 10 y 12.
- **Esencial ↔ Esencial Paramount** (partner 1271, junio → agosto): la ida y vuelta de 4 a 30 USD explica el salto de MRR y ARPPU en EC entre junio y agosto.
- **Intermitencia:** 1 de cada 6 usuarios sale y vuelve dentro de la ventana, y la mayoría vuelve en 1 a 3 días. Más de la mitad de las bajas orgánicas (59%) vuelve dentro de la ventana.
- **Engagement:** las horas medianas de consumo suben de ~40 a ~90 tras el 2026-06-12. Es consistente con un efecto de composición: salen los partners que terminaron convenio, y las categorías B2B tienen menos consumo (BUNDLE, HARDBUNDLE y RESELLER ~40–65% de MAU, contra ~96% en B2C).
- **Ventanas de riesgo (KDD):** el riesgo mensual de baja es de 26% en los meses 0 y 1 de una suscripción, 14% en el mes 2 y menos de 4% después del primer año. Solo el 46% llega al mes 4. Al cierre, 2.362 usuarios activos (41% del MRR) están en los meses 0 a 5, y concentran el 75% de la pérdida esperada del mes siguiente (US$ 5.104 de ~US$ 6.800).
- **El cupón posterga la baja (KDD):** el riesgo es menor durante el descuento (16% contra 28% sin cupón en el mes 0), pero sube a 36,5% en el primer mes a precio completo. En el modelo de Cox, el HR del cupón es 1,42 en los primeros 90 días y 1,09 después.
- **Recién llegados (KDD):** el 45% se fue, y a igual antigüedad tienen 1,85 veces el riesgo de los activos establecidos. Pagar varios meses por adelantado reduce el riesgo (HR 0,62).
- **PE:** la base es muy pequeña y desaparece en julio. Sus tasas por cohorte (p.ej. churn de 66–95%) se basan en muy pocos usuarios.

## Limitaciones conocidas
- **Memoria:** el notebook llega a ~8 GB de RAM en su pico, por las copias intermedias de una tabla de 1,7M filas. En una máquina con menos memoria convendría leer solo las columnas necesarias y usar tipos `category`.

- **KDD observacional:** los hazard ratios y la curva del cupón son asociaciones, no efectos causales; quien recibe un cupón puede ser distinto desde el principio. Una promoción de retención debería probarse con un grupo de control. El HR del perfil *Intermitente* (6,45) es en parte mecánico, porque el perfil se define por haber tenido varias bajas.
- **Antigüedad previa a 2026:** se asume suscripción continua desde la creación del primer plan (supuesto 10). Si hubo saltos antes de 2026, la antigüedad de los usuarios antiguos está sobrestimada, y eso puede inflar el riesgo relativo de los recién llegados.

## Registro de cambios
| Fecha | Cambio |
|---|---|
| 2026-10-26 | Versión inicial de las actividades 1–4. |
| 2026-10-26 | Tasas FX actualizadas al 26-10-2026 (CLP 991,40 · BRL 5,02 · PEN 3,45). |
| 2026-10-26 | **Eventos masivos:** se reemplaza el umbral fijo de 50 usuarios por la cerca de Tukey extrema (log10) más ≥50% de la base del grupo en las bajas. Con el umbral fijo, el ciclo mensual del partner 1271 quedaba como masivo y se excluía del churn orgánico, subestimándolo (6M: de 14–15% pasa a 16–18%). Las migraciones pasan de agruparse por nombre de plan a agruparse por `package_id`. |
| 2026-10-26 | **Revisión de 3.1–3.3 con el autor.** Se confirma que 3.1 es el flujo completo: altas nuevas y reactivaciones, bajas y addons. `es_tecnica` se extiende a `df_altas_bajas` y se agregan `alta_real` y `baja_real` a los resúmenes. Se confirman los criterios de 3.3: precio de lista en USD, `lateral` para cambios dentro de ±1%, plan base más nuevo y solo planes base. |
| 2026-10-26 | **Tasas de cambio mensuales:** se reemplazan las tasas fijas del 26-10 por promedios mensuales de tasas diarias (fawazahmed0/currency-api, validado contra el BCE para el BRL). En los cambios de plan, ambos precios se comparan con la tasa del mes del cambio. El MRR en USD sube entre 1,8% y 6,0%. |
| 2026-10-26 | **Vida media:** se censuran también los spells que terminan en una baja masiva por fin de convenio (2.621). La mediana de `bundle` pasa de 55 a 580 días. |
| 2026-10-27 | **Se revierten las tasas mensuales** por decisión del autor: se vuelve a las tasas fijas al 26-10-2026. Se mantiene la censura de los fines de convenio en la vida media. Se exportan las curvas de Kaplan–Meier (`outputs/km_curvas.parquet`) para el dashboard. |
| 2026-10-27 | **Dashboard (actividad 5)** en Streamlit + Plotly + DuckDB: 7 páginas con filtros globales. Sus métricas se verificaron contra las tablas del notebook. |
| 2026-10-27 | **Respuestas de Zapping.** (1) Se valida el proxy de `created_user`. (2) `time_watched` es consumo de los últimos 30 días: el MAU pasa a medirse en el snapshot de fin de mes (enero: de 72,6% a 64,8%). (3) Se autoriza publicar el dashboard: se agregan `dashboard/requirements.txt`, la guía de publicación y la sección 9 del notebook para el enlace. (4) **Se elimina `GRACE_DAYS`**: todo salto es baja + reactivación, también en la vida media y el churn. Se quitan `es_tecnica`, `alta_real` y `baja_real`, y se agregan la sección *Intermitencia* y, en el dashboard, las bajas con y sin retorno. El churn orgánico 1M sube ~3 pp y la vida media de `hardbundle` baja de 219 a 112 días. |
| 2026-10-27 | **Identidad visual de Zapping en el dashboard** (tema negro + Zapink, Poppins, jerarquía por opacidad, acentos de marca validados para daltonismo). Sin cambios en las métricas. |
| 2026-10-27 | **Revisión del dashboard** (comentarios del autor). Pie numerado en todas las figuras y sin el subtítulo de fechas. Resumen: se explican los eventos masivos y su efecto. Flujo: sin granularidad diaria; totales de contrataciones y abandonos; nuevo desglose de planes contratados y cancelados, que reemplaza a *bajas orgánicas por dimensión*; rayado en las bajas sin retorno; addons por nombre. Reactivaciones: el Sankey se reemplaza por barras mismo plan / otro plan. Cambios: definición de cada tipo y leyenda del Sankey. Engagement: *suscriptores* en vez de *activos* y corrección del hover del mapa de calor. Sin cambios en las métricas. |
| 2026-10-27 | **Actividad 6 (KDD).** Sección 7 del notebook: perfiles de usuario (K-means, k = 7 elegido por silhouette y estabilidad bootstrap), riesgo mensual de baja por antigüedad con ventanas de riesgo, efecto del fin del cupón, modelo de Cox y MRR en juego. Supuesto 10 y validación 8 nuevos. Se agrega `scikit-learn==1.6.1` a `requirements_entrega.txt` (verificado en un entorno limpio). Dashboard: página *Perfiles y riesgo* y *Perfil* como filtro y dimensión. Validaciones, exportación pasan a ser las secciones 8 y 9. |
