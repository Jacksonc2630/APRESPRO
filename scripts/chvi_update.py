import math
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def find_col(df, candidates):
    for c in candidates:
        for col in df.columns:
            if c.lower() in col.lower():
                return col
    return None

def safe_minmax(series):
    if series.isna().all():
        return series
    mn = series.min()
    mx = series.max()
    if pd.isna(mn) or pd.isna(mx) or mn == mx:
        return pd.Series(0.5, index=series.index)
    return (series - mn) / (mx - mn)

def clean_numeric(s):
    if pd.isna(s):
        return None
    if isinstance(s, str):
        s = s.replace(',', '').strip()
        if s == '':
            return None
    try:
        return float(s)
    except Exception:
        return None

def main():
    base = r"..\Data\Processed"
    neighborhoods_gpkg = r"..\Data\Processed\neighborhoods_final.gpkg"
    neigh_attrs_csv = r"..\Data\Processed\neighborhoods_attributes.csv"
    wbgt_csv = r"..\Outputs\Statistics\neighborhood_wbgt_by_month.csv"
    svi_csv = r"..\Data\Processed\socialvulnerability.csv"
    inside_cc = r"..\Data\Processed\inside_cooling_centers_final.csv"
    outside_cc = r"..\Data\Processed\outside_cooling_centers_final.csv"
    green_csv = r"..\Data\Processed\green_spaces_final.csv"
    urban_csv = r"..\Data\Processed\urban_design_final.csv"

    # Load neighborhoods geometry and attributes
    try:
        gdf_neigh = gpd.read_file(neighborhoods_gpkg)
    except Exception:
        # fallback to attributes CSV for geometry-less operations
        gdf_neigh = None
    attrs = pd.read_csv(neigh_attrs_csv, dtype=str)
    attrs['area_sqmi'] = pd.to_numeric(attrs.get('area_sqmi'), errors='coerce')

    # in_nyc flag from BoroName
    attrs['in_nyc'] = attrs['BoroName'].isin(['Manhattan','Brooklyn','Bronx','Queens','Staten Island'])

    # load cooling centers and count per neighborhood (use spatial join when possible)
    cc_df = pd.concat([pd.read_csv(inside_cc), pd.read_csv(outside_cc)], ignore_index=True, sort=False)
    cc_df = cc_df.rename(columns={c: c.strip() for c in cc_df.columns})
    if 'latitude' in cc_df.columns and 'longitude' in cc_df.columns:
        cc_df['latitude'] = pd.to_numeric(cc_df['latitude'], errors='coerce')
        cc_df['longitude'] = pd.to_numeric(cc_df['longitude'], errors='coerce')
        cc_pts = cc_df.dropna(subset=['latitude','longitude']).copy()
        cc_g = gpd.GeoDataFrame(cc_pts, geometry=[Point(xy) for xy in zip(cc_pts['longitude'], cc_pts['latitude'])], crs='EPSG:4326')
        if gdf_neigh is not None:
            cc_g = cc_g.to_crs(gdf_neigh.crs)
            joined = gpd.sjoin(cc_g, gdf_neigh, how='left', predicate='within')
            cc_counts = joined.groupby('GEOID').size().rename('cooling_count')
        else:
            cc_counts = pd.Series(0, index=attrs['GEOID']).rename('cooling_count')
    else:
        cc_counts = pd.Series(0, index=attrs['GEOID']).rename('cooling_count')

    # green infrastructure: sum Asset_Area per neighborhood (use coords)
    green = pd.read_csv(green_csv)
    # parse numeric asset area
    if 'Asset_Area' in green.columns:
        green['Asset_Area_num'] = green['Asset_Area'].apply(clean_numeric)
    else:
        green['Asset_Area_num'] = None
    green = green.dropna(subset=['Asset_Area_num'])
    if 'Asset_X_Co' in green.columns and 'Asset_Y_Co' in green.columns and gdf_neigh is not None:
        pts = gpd.GeoDataFrame(green, geometry=[Point(xy) for xy in zip(pd.to_numeric(green['Asset_X_Co'], errors='coerce'), pd.to_numeric(green['Asset_Y_Co'], errors='coerce'))], crs=gdf_neigh.crs)
        pts = pts.dropna(subset=['geometry'])
        joined_g = gpd.sjoin(pts, gdf_neigh, how='left', predicate='within')
        green_sum = joined_g.groupby('GEOID')['Asset_Area_num'].sum().rename('green_area')
    else:
        green_sum = pd.Series(0, index=attrs['GEOID']).rename('green_area')

    # urban design: try to load and aggregate if possible (fallback to 0)
    try:
        ude = pd.read_csv(urban_csv)
        # try to find GEOID or BBL or other join key
        geoid_col = find_col(ude, ['GEOID','geoid','nta','nta2020','GEOID10'])
        if geoid_col is not None:
            ude_agg = ude.groupby(geoid_col).size().rename('urban_design_count')
        else:
            ude_agg = pd.Series(0, index=attrs['GEOID']).rename('urban_design_count')
    except Exception:
        ude_agg = pd.Series(0, index=attrs['GEOID']).rename('urban_design_count')

    # merge aggregates into attrs
    attrs = attrs.set_index('GEOID')
    attrs['cooling_count'] = 0
    attrs.loc[cc_counts.index.intersection(attrs.index), 'cooling_count'] = cc_counts.reindex(attrs.index).fillna(0)
    attrs['green_area'] = 0
    attrs.loc[green_sum.index.intersection(attrs.index), 'green_area'] = green_sum.reindex(attrs.index).fillna(0)
    attrs['urban_design_count'] = 0
    attrs.loc[ude_agg.index.intersection(attrs.index), 'urban_design_count'] = ude_agg.reindex(attrs.index).fillna(0)

    # normalize per-area densities
    attrs['cool_density'] = attrs['cooling_count'] / attrs['area_sqmi']
    attrs['green_density'] = attrs['green_area'] / attrs['area_sqmi']

    # normalize components 0-1
    attrs['cool_s'] = safe_minmax(pd.to_numeric(attrs['cool_density'], errors='coerce').fillna(0))
    attrs['green_s'] = safe_minmax(pd.to_numeric(attrs['green_density'], errors='coerce').fillna(0))
    attrs['urban_s'] = safe_minmax(pd.to_numeric(attrs['urban_design_count'], errors='coerce').fillna(0))

    # adaptive capacity score (higher is more capacity), equal weights
    attrs['adaptive_capacity'] = (attrs['cool_s'].fillna(0) + attrs['green_s'].fillna(0) + attrs['urban_s'].fillna(0)) / 3.0
    attrs['adaptive_vuln_s'] = 1.0 - attrs['adaptive_capacity']

    # SVI: try to find overall SVI column
    svi = pd.read_csv(svi_csv, dtype=str)
    svi_col = find_col(svi, ['svi','rpl_themes','rpl_themes..','E_TOTPOP','SVI'])
    if svi_col is None:
        # try common CDC name
        for c in svi.columns:
            if 'RPL_THEMES' in c.upper() or 'SVI' in c.upper():
                svi_col = c
                break
    if svi_col is not None:
        svi[svi_col] = pd.to_numeric(svi[svi_col], errors='coerce')
        # SVI is tract-level; attempt to aggregate to neighborhoods by mean if join possible
        # if SVI has 'FIPS' we cannot spatially join here without tract geometry; fallback: global min-max
        svi_vals = svi[svi_col].median()
        attrs['svi'] = svi_vals
        attrs['svi_s'] = safe_minmax(pd.to_numeric(attrs['svi'], errors='coerce').fillna(svi_vals))
    else:
        attrs['svi'] = pd.NA
        attrs['svi_s'] = 0.5

    # WBGT: try to load neighborhood wbgt
    try:
        wb = pd.read_csv(wbgt_csv)
        # find geoid and wbgt column
        geoid_c = find_col(wb, ['GEOID','geoid','geoid_neighborhood','GEOID'])
        wbgt_c = find_col(wb, ['wbgt','WBGT','wbgt_c','wbgt_mean','wbgt_C'])
        if geoid_c and wbgt_c:
            wb_idx = wb.set_index(wb[geoid_c].astype(str))
            attrs['wbgt'] = wb_idx.reindex(attrs.index)[wbgt_c].astype(float).reindex(attrs.index)
        else:
            attrs['wbgt'] = wb.select_dtypes(include='number').iloc[:,0]
    except Exception:
        attrs['wbgt'] = pd.Series(pd.NA, index=attrs.index)

    attrs['wbgt_s'] = safe_minmax(pd.to_numeric(attrs['wbgt'], errors='coerce').fillna(attrs['wbgt'].median(skipna=True)))

    # final CHVI: mean of wbgt_s, svi_s, adaptive_vuln_s
    attrs['chvi'] = (attrs['wbgt_s'].fillna(0.5) + attrs['svi_s'].fillna(0.5) + attrs['adaptive_vuln_s'].fillna(0.5)) / 3.0

    # write outputs
    out_csv = r"..\Data\Processed\neighborhoods_chvi.csv"
    sample_csv = r"..\Data\Processed\neighborhoods_chvi_sample.csv"
    attrs.reset_index().to_csv(out_csv, index=False)
    attrs.reset_index().sample(20, random_state=1).to_csv(sample_csv, index=False)
    print('Wrote', out_csv, 'and', sample_csv)

if __name__ == '__main__':
    main()
