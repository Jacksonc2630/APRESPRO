# Imports and configuration
import os, re, glob
import json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from rasterstats import zonal_stats
import rasterio

# ── config ────────────────────────────────────────────────────────────────────
config_path = Path('config.json')
if config_path.exists():
    with open(config_path, 'r') as f:
        config = json.load(f)
    data_processed = Path(config['paths'].get('data_processed', 'Data/Processed'))
    figures_path   = Path(config['paths'].get('figures',        'Outputs/Figures'))
else:
    data_processed = Path('Data/Processed')
    figures_path   = Path('Outputs/Figures')

# ── neighborhoods ─────────────────────────────────────────────────────────────
neigh_fp = data_processed / 'neighborhoods_final.gpkg'
if not neigh_fp.exists():
    raise FileNotFoundError(f'Neighborhood file not found: {neigh_fp}')
neigh  = gpd.read_file(neigh_fp)
id_col = 'geoid' if 'geoid' in neigh.columns else neigh.columns[0]

# ── raster directories ────────────────────────────────────────────────────────
# Priority: monthly time-series → yearly → 30-yr normals
time_series_parent = Path('Data/Raw/Climate')
possible_dirs = [
    ('prism_tmax_us_30s_monthly',      'prism_vpdmax_us_30s_monthly'),
    ('prism_tmax_us_30s_yearly',       'prism_vpdmax_us_30s_yearly'),
    ('prism_tmax_us_30s_2020_avg_30y', 'prism_vpdmax_us_30s_2020_avg_30y'),
]

tmax_dir = vpd_dir = None
for tmax_alt, vpd_alt in possible_dirs:
    cand_t = time_series_parent / tmax_alt
    cand_v = time_series_parent / vpd_alt
    if cand_t.exists() and cand_v.exists():
        if list(cand_t.glob('*.tif')) and list(cand_v.glob('*.tif')):
            tmax_dir, vpd_dir = cand_t, cand_v
            print(f'Found raster directories: {tmax_alt}, {vpd_alt}')
            break

if tmax_dir is None:
    raise FileNotFoundError(
        'No TMAX/VPD raster directories found. Expected one of:\n' +
        '\n'.join(f'  {time_series_parent / d[0]}  &  {time_series_parent / d[1]}'
                   for d in possible_dirs))

print(f'Using TMAX: {tmax_dir.name}')
print(f'Using VPD : {vpd_dir.name}')

# ── reproject neighborhoods to raster CRS ─────────────────────────────────────
t0 = next(tmax_dir.glob('*.tif'), None)
if t0 is not None:
    with rasterio.open(t0) as src:
        rast_crs = src.crs
    if neigh.crs != rast_crs:
        print(f'Reprojecting neighborhoods from {neigh.crs} to {rast_crs}')
        neigh = neigh.to_crs(rast_crs)

# ── output paths ──────────────────────────────────────────────────────────────
out_dir = Path('Outputs/Statistics')
out_dir.mkdir(parents=True, exist_ok=True)
out_csv = out_dir / 'neighborhood_wbgt_by_month.csv'
# ── Helper functions ──────────────────────────────────────────────────────────

# ── CONFIGURABLE PARAMETER ────────────────────────────────────────────────────
# The Steadman WBGT formula (0.567*T + 0.393*ea + 3.94) is calibrated for
# *ambient* (mean) temperature conditions.  PRISM tmax is the daily maximum,
# which biases WBGT high.  We subtract TMAX_TO_MEAN_OFFSET to approximate the
# daily mean before passing to the formula.  For monthly 30-yr normals in the
# north-east US, ~5 °C is a reasonable default; set to 0 to disable.
TMAX_TO_MEAN_OFFSET = 5.0   # °C  – use ~5 to convert Tmax to approximate Tmean for WBGT


def es_kpa(Tc):
    """Saturation vapour pressure (kPa) – Tetens formula."""
    return 0.6108 * np.exp((17.27 * Tc) / (Tc + 237.3))


def detect_and_convert_tmax(mean_val):
    """
    Convert raw PRISM tmax to °C and apply Tmax→Tmean offset.
    PRISM delivers tmax in °C; values >200 are treated as Kelvin (rare edge case).
    The TMAX_TO_MEAN_OFFSET correction brings values closer to daily-mean
    conditions, which the Steadman formula expects.
    """
    if mean_val is None:
        return None
    tc = (mean_val - 273.15) if mean_val > 200 else float(mean_val)
    return tc - TMAX_TO_MEAN_OFFSET


def detect_and_convert_vpd(mean_val):
    """
    Convert raw PRISM vpdmax to kPa.
    PRISM vpdmax is ALWAYS delivered in hPa (mb); typical range 0–40 hPa.
    We always divide by 10 to convert hPa → kPa, except for rare Pa edge case.
    NOTE: The previous logic (threshold > 10) failed for typical summer values
    (e.g. 5–20 hPa) which were incorrectly treated as already-kPa, causing ea
    to be clamped to ~0 and WBGT to be significantly underestimated.
    """
    if mean_val is None:
        return None
    v = float(mean_val)
    if v > 100:
        return v / 1000.0    # Pa → kPa (rare edge case)
    return v / 10.0          # hPa → kPa (PRISM standard units)


def compute_wbgt(Tc, vpd_kpa):
    """
    Steadman / Willett-Sherwood outdoor shaded WBGT approximation.

      WBGT = 0.567·T + 0.393·ea + 3.94

    where ea = es(T) − VPD  (actual vapour pressure, kPa).

    NOTE: Solar radiation is intentionally excluded here.  The empirical
    coefficients already embed a climatological radiation loading for shaded
    outdoor conditions.  Adding a separate solar term with an arbitrary
    coefficient (as in the previous version) inflated results by 1–3 °C.
    If you have reliable in-situ solar data and a validated coefficient,
    add it in a separate validated function.

    Returns: (wbgt_C, ea_kPa)
    """
    es = es_kpa(Tc)
    ea = max(es - vpd_kpa, 0.001)   # clamp to avoid log-domain issues
    wbgt = 0.567 * Tc + 0.393 * ea + 3.94
    return wbgt, ea


def get_raster_nodata(raster_path):
    """Read the nodata value declared in the raster's metadata."""
    with rasterio.open(raster_path) as src:
        return src.nodata


def safe_zonal_mean(geoms, raster_path):
    """
    Compute per-geometry mean from raster, respecting declared nodata.
    Returns a list of float | None (one per geometry row).
    """
    nd = get_raster_nodata(raster_path)
    stats = zonal_stats(geoms, raster_path, stats=['mean'],
                        all_touched=True, nodata=nd)
    return [s.get('mean') if s else None for s in stats]
def extract_period(fname):
    """
    Infer period string from a raster filename.
    Returns: 'YYYY-MM' | 'YYYY' | '30yr_normal' | ''
    """
    s     = str(fname)
    s_low = s.lower()

    # 1) explicit YYYY-MM or YYYYMM
    m = re.search(r'(\d{4})[-_]?([0-1][0-9])', s)
    if m:
        year, mon = m.group(1), m.group(2)
        if 1 <= int(mon) <= 12:
            return f'{year}-{mon}'

    # 2) month name tokens
    month_map = {
        'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
        'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'
    }
    for k, v in month_map.items():
        if re.search(rf'\b{k}\b', s_low):
            y = re.search(r'(\d{4})', s)
            return (f'{y.group(1)}-{v}' if y else v)

    # 3) 30-yr normal indicator
    if re.search(r'30y|avg_30y|30-yr', s_low):
        return '30yr_normal'

    # 4) bare year fallback
    y = re.search(r'(\d{4})', s)
    return y.group(1) if y else ''
# ── File discovery ────────────────────────────────────────────────────────────
tmax_files = sorted(glob.glob(str(tmax_dir / '*.tif')))
vpd_files  = sorted(glob.glob(str(vpd_dir  / '*.tif')))

print(f'TMAX files found: {len(tmax_files)}')
if tmax_files:
    print(f'  sample: {[os.path.basename(p) for p in tmax_files[:3]]}')
print(f'VPD  files found: {len(vpd_files)}')
if vpd_files:
    print(f'  sample: {[os.path.basename(p) for p in vpd_files[:3]]}')

# ── Raster diagnostics ────────────────────────────────────────────────────────
if tmax_files:
    with rasterio.open(tmax_files[0]) as src:
        print('\nTMAX raster info:')
        print(f'  path   : {tmax_files[0]}')
        print(f'  dtype  : {src.dtypes}')
        print(f'  size   : {src.width} x {src.height}')
        print(f'  CRS    : {src.crs}')
        print(f'  nodata : {src.nodata}')
        print(f'  bounds : {src.bounds}')

        # sample a few pixel values to verify units
        arr = src.read(1, masked=True)
        valid = arr.compressed()
        if valid.size:
            print(f'  pixel stats — min={valid.min():.2f}  mean={valid.mean():.2f}  max={valid.max():.2f}')
            if valid.mean() > 200:
                print('OK Mean > 200 - treating as Kelvin, will subtract 273.15')
            elif valid.mean() < 0:
                print('OK Values below 0 degC detected (winter month?)')
            else:
                print('OK Values look like degC  (TMAX_TO_MEAN_OFFSET={TMAX_TO_MEAN_OFFSET} degC will be applied)')

if vpd_files:
    with rasterio.open(vpd_files[0]) as src:
        arr = src.read(1, masked=True)
        valid = arr.compressed()
        if valid.size:
            print(f'\nVPD pixel stats — min={valid.min():.3f}  mean={valid.mean():.3f}  max={valid.max():.3f}')
            if valid.mean() > 100:
                print('OK Treating VPD as Pa -> converting to kPa')
            elif valid.mean() > 10:
                print('OK Treating VPD as hPa -> converting to kPa')
            else:
                print('OK VPD looks like kPa')

print('\nNeighborhoods:')
print(f'  count  : {len(neigh)}')
print(f'  CRS    : {neigh.crs}')
print(f'  bounds : {neigh.total_bounds}')
# ── Pair tmax ↔ vpd files ────────────────────────────────────────────────────

def find_vpd_for_tmax(tpath):
    tname = os.path.basename(tpath)
    # 1) direct stem replacement tmax → vpdmax
    for old, new in [('prism_tmax', 'prism_vpdmax'), ('tmax', 'vpdmax')]:
        cand = vpd_dir / tname.replace(old, new)
        if cand.exists():
            return str(cand)
    # 2) match by trailing date tokens
    t_tail = os.path.splitext(tname)[0].split('_')[-2:]
    for vf in vpd_files:
        if os.path.splitext(os.path.basename(vf))[0].split('_')[-2:] == t_tail:
            return vf
    # 3) fallback: only one vpd file
    if len(vpd_files) == 1:
        return vpd_files[0]
    return None


# ── Build pairs ───────────────────────────────────────────────────────────────
if len(tmax_files) == 1 and len(vpd_files) == 1:
    pairs = [(tmax_files[0], vpd_files[0])]
else:
    pairs = []
    for tpath in tmax_files:
        vmatch = find_vpd_for_tmax(tpath)
        if vmatch is None:
            print(f'  Warning No VPD match for {os.path.basename(tpath)}, skipping')
        else:
            pairs.append((tpath, vmatch))

print(f'Processing {len(pairs)} tmax/vpd pair(s) ...')

# ── Zonal statistics & WBGT ───────────────────────────────────────────────────
rows = []

for tpath, vpath in pairs:
    tname = os.path.basename(tpath)
    vname = os.path.basename(vpath)

    t_means = safe_zonal_mean(neigh, tpath)
    v_means = safe_zonal_mean(neigh, vpath)

    for idx, (geom_row, t_raw, v_raw) in enumerate(
            zip(neigh.itertuples(), t_means, v_means)):

        geoid = getattr(geom_row, id_col)

        if t_raw is None or v_raw is None or np.isnan(t_raw) or np.isnan(v_raw):
            wbgt = ea = np.nan
            t_c = v_kpa = None
        else:
            t_c  = detect_and_convert_tmax(t_raw)
            v_kpa = detect_and_convert_vpd(v_raw)

            if t_c is None or v_kpa is None:
                wbgt = ea = np.nan
            else:
                wbgt, ea = compute_wbgt(t_c, v_kpa)

        rows.append({
            id_col:          geoid,
            'raster_file':   tname,
            'vpd_file':      vname,
            'tmax_mean_raw': t_raw,
            'tmax_mean_C':   t_c,
            'vpd_mean_raw':  v_raw,
            'vpd_mean_kPa':  v_kpa,
            'ea_kPa':        ea,
            'wbgt_C':        wbgt,
        })

# ── Build DataFrame ───────────────────────────────────────────────────────────
if not rows:
    print('No neighbourhood statistics produced — check raster/vector overlap.')
    df = pd.DataFrame()
else:
    df = pd.DataFrame(rows)
    df['period'] = df['raster_file'].fillna('').apply(extract_period)
    df['year']   = df['period'].str.extract(r'(\d{4})', expand=False)
    df['month']  = df['period'].str.extract(r'-(\d{2})', expand=False)

    df.to_csv(out_csv, index=False)
    print(f'Saved WBGT CSV -> {out_csv}')
    print(f'Rows written  : {len(df)}')
    print(f'Unique periods: {sorted(df["period"].unique())}')
    print('\nSample output:')
    print(df[['period', id_col, 'tmax_mean_C', 'vpd_mean_kPa', 'ea_kPa', 'wbgt_C']]
          .head(10).to_string(index=False))

    # ── Sanity check ────────────────────────────────────────────────────────
    summer = df[df['month'].isin(['06','07','08'])]['wbgt_C'].dropna()
    if not summer.empty:
        print(f'\nSummer (Jun–Aug) WBGT sanity check:')
        print(f'  min={summer.min():.2f}  median={summer.median():.2f}  max={summer.max():.2f} °C')
        if summer.max() > 35:
            print('Warning Max WBGT > 35 degC - check unit conversions or TMAX_TO_MEAN_OFFSET')
        elif summer.median() > 30:
            print('Warning Median WBGT > 30 degC - values seem high for shaded outdoor conditions')
        else:
            print('OK Values within plausible outdoor shaded WBGT range')
# ── Export neighbourhood centroids as PRISM locations CSV ────────────────────
locs_fp = Path('Data/Processed/prism_locations_neighborhoods.csv')

neigh_latlon = neigh.to_crs(epsg=4326).copy()
centroids    = neigh_latlon.geometry.centroid

# prefer a short human-readable name column, fall back to id_col
short_name = None
for candidate in ['name', 'Name', 'neighborhood', 'nbhd', id_col]:
    if candidate in neigh_latlon.columns:
        short_name = neigh_latlon[candidate].astype(str).str.slice(0, 12)
        break

df_locs = pd.DataFrame({
    'latitude':  centroids.y,
    'longitude': centroids.x,
    'name':      short_name if short_name is not None
                 else neigh_latlon[id_col].astype(str).str.slice(0, 12),
})

df_locs.to_csv(locs_fp, index=False)
print(f'Wrote PRISM locations file: {locs_fp}  ({len(df_locs)} rows)')
print(df_locs.head(6).to_string(index=False))
print('\nUpload to: https://prism.oregonstate.edu/explorer/bulk.php')
print('Format: latitude,longitude,name (name <=12 chars, optional)')
# ── WBGT Choropleth Visualisation ────────────────────────────────────────────
import matplotlib.pyplot as plt
import matplotlib as mpl

wbgt_path = out_csv if 'out_csv' in locals() else Path('Outputs/Statistics/neighborhood_wbgt_by_month.csv')
wbgt_df   = pd.read_csv(wbgt_path)

# normalise id column name for merging
if 'GEOID' not in wbgt_df.columns:
    wbgt_df = wbgt_df.rename(columns={id_col: 'GEOID'})

periods = sorted([p for p in wbgt_df['period'].unique() if p != '30yr_normal'])
if not periods:
    raise RuntimeError('No monthly periods found in WBGT CSV')

# ── Colormap ──────────────────────────────────────────────────────────────────
# Use purple-yellow-red gradient for WBGT (0-30°C range)
purple_yellow_red_cmap = mpl.colors.LinearSegmentedColormap.from_list(
    'purple_yellow_red', ['#440154', '#482878', '#3e4a89', '#26828e', '#1f9e89', '#6dcd59', '#b4de2c', '#fde725', '#f0f921', '#fdb42f', '#ed7953', '#cc4778', '#9c179e', '#5c01a6'])
# Alternative simpler gradient: purple to yellow to red
wbgt_cmap = mpl.colors.LinearSegmentedColormap.from_list(
    'wbgt_gradient', ['#762a83', '#9970ab', '#c2a5cf', '#e7d4e8', '#f7f7f7', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'])


def _make_wbgt_map(geo_df, vals_col, title, out_path):
    """Shared choropleth helper. Saves and shows the figure."""
    vals = geo_df[vals_col].dropna()
    if vals.empty:
        print(f'No data for: {title}')
        return

    # Fixed range 0-30°C for WBGT
    vmin, vmax = 0.0, 30.0
    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

    fig, ax = plt.subplots(figsize=(10, 10))
    geo_df.plot(column=vals_col, cmap=wbgt_cmap, norm=norm,
                linewidth=0.3, edgecolor='white', ax=ax,
                missing_kwds={'color': 'lightgrey', 'hatch': '///', 'label': 'no data'})
    ax.axis('off')
    ax.set_title(title, fontsize=14)

    sm = mpl.cm.ScalarMappable(cmap=wbgt_cmap, norm=norm)
    sm.set_array([])
    # Fixed ticks at 0, 10, 20, 30 for consistent legend
    ticks = [0, 5, 10, 15, 20, 25, 30]
    cbar  = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02, ticks=ticks)
    cbar.set_label('WBGT (°C)')
    cbar.ax.set_yticklabels([f'{t:.0f}' for t in ticks])

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.show()
    print(f'Saved -> {out_path}')


def plot_wbgt_for_period(period, out_name_suffix):
    """Plot WBGT choropleth for a single period string."""
    dfp = wbgt_df[wbgt_df['period'] == period][['GEOID', 'wbgt_C']].copy()
    g   = neigh.merge(dfp, left_on=id_col, right_on='GEOID', how='left')
    _make_wbgt_map(g, 'wbgt_C', f'WBGT (°C) — {period}',
                   f'Outputs/Figures/wbgt_choropleth_{out_name_suffix}.png')
    return g


# ── Jun–Aug mean map ──────────────────────────────────────────────────────────
summer_periods = [p for p in periods
                  if len(p) >= 7 and p.split('-')[1] in {'06', '07', '08'}]

if summer_periods:
    summer_df = (wbgt_df[wbgt_df['period'].isin(summer_periods)]
                 .groupby('GEOID', as_index=False)['wbgt_C'].mean())
    g_summer  = neigh.merge(summer_df, left_on=id_col, right_on='GEOID', how='left')
    _make_wbgt_map(g_summer, 'wbgt_C', 'WBGT (°C) — Jun–Aug mean',
                   'Outputs/Figures/wbgt_choropleth_summer_mean.png')
else:
    print('No June–August periods found; skipping summer mean map.')

# ── Hottest / most-variable period map ───────────────────────────────────────
period_stats = (wbgt_df[wbgt_df['period'] != '30yr_normal']
                .groupby('period')['wbgt_C']
                .agg(['count', 'mean', 'std', 'min', 'max']))

warm_periods = period_stats[period_stats['mean'] >= 20.0]
chosen = (warm_periods['std'].idxmax() if not warm_periods.empty
          else period_stats['mean'].idxmax())

g_chosen = plot_wbgt_for_period(chosen, f"{chosen.replace('-', '')}_peak")
print(f'Peak period plotted: {chosen}')
print(period_stats.loc[chosen].to_string())
