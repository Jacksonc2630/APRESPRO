
# Import Libaires
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Point
from shapely import wkt
import json
import os
import time
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from pathlib import Path

# Load project configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Extract paths
data_raw = Path(config['paths']['data_raw'])
data_processed = Path(config['paths']['data_processed'])
climate_path = Path(config['paths']['climate'])
socialvulnerability_path = Path(config['paths']['socialvulnerability'])
infrastructure_path = Path(config['paths']['infrastructure'])
shapefiles_path = Path(config['paths']['shapefiles'])
redlining_path = Path(config['paths']['redlining'])
Outputs_path = Path(config['paths']['outputs'])

# Configurations
class Config:
    GEOCODE_CACHE = 'geocode_cache.json'
    OUTPUT_MAP = Outputs_path / 'Figures' / 'nyc_infrastructure_access.png'
    WEIGHTS = {'height': 0.25, 'age': 0.25, 'area': 0.25, 'elevation': 0.25}

def calculate_heat_index(gdf):
    score = pd.Series(0.0, index=gdf.index)
    if 'Height_Roof' in gdf.columns:
        height = pd.to_numeric(gdf['Height_Roof'], errors='coerce').fillna(0)
        score += (height / 100).clip(0, 1) * Config.WEIGHTS['height'] * 100
    if 'Construction_Year' in gdf.columns:
        year = pd.to_numeric(gdf['Construction_Year'], errors='coerce').fillna(2026)
        age = 2026 - year
        score += (age / 100).clip(0, 1) * Config.WEIGHTS['age'] * 100
    if 'SHAPE_AREA' in gdf.columns:
        area = pd.to_numeric(gdf['SHAPE_AREA'], errors='coerce').fillna(0)
        score += (area / 500).clip(0, 1) * Config.WEIGHTS['area'] * 100
    if 'Ground_Elevation' in gdf.columns:
        elev_data = pd.to_numeric(gdf['Ground_Elevation'], errors='coerce').fillna(100)
        elev = (1 - (elev_data / 200)).clip(0, 1)
        score += elev * Config.WEIGHTS['elevation'] * 100
    return score
# GEOCODING WITH CACHE (ADDRESS TO LAT/LON)

def get_geocoder():
    geolocator = Nominatim(
        user_agent="nyc_heat",
        timeout=10
    )

    return RateLimiter(
        geolocator.geocode,
        min_delay_seconds=2,
        max_retries=3,
        error_wait_seconds=5,
        swallow_exceptions=True
    )


def geocode_with_cache(df, address_col='Address', borough_col='Borough'):

    # Load cache
    cache = {}
    if os.path.exists(Config.GEOCODE_CACHE):
        with open(Config.GEOCODE_CACHE, 'r') as f:
            cache = json.load(f)

    geocode = get_geocoder()

    lats = []
    lons = []

    for _, row in df.iterrows():

        addr = f"{row[address_col]}, {row[borough_col]}, NY"

        if addr in cache:
            lat = cache[addr]['lat']
            lon = cache[addr]['lon']

        else:
            try:
                loc = geocode(addr)

                if loc:
                    lat = loc.latitude
                    lon = loc.longitude

                    cache[addr] = {
                        'lat': lat,
                        'lon': lon
                    }

                    # SAVE CACHE IMMEDIATELY (critical fix)
                    with open(Config.GEOCODE_CACHE, 'w') as f:
                        json.dump(cache, f)

                else:
                    lat, lon = None, None

            except Exception:
                lat, lon = None, None

        lats.append(lat)
        lons.append(lon)

    df['latitude'] = lats
    df['longitude'] = lons

    return df

def main():
    try:
        # 1. Load Indoor Centers and create point geometries (do NOT attempt geocoding here)
        df_in = pd.read_csv(data_processed / 'inside_cooling_centers_final.csv')

        # Identify latitude/longitude-like columns in the indoor dataset
        lat_cols_in = [c for c in df_in.columns if c.lower() in ['latitude', 'lat', 'y']]
        lon_cols_in = [c for c in df_in.columns if c.lower() in ['longitude', 'lon', 'x']]

        if lat_cols_in and lon_cols_in:
            lat_col = lat_cols_in[0]
            lon_col = lon_cols_in[0]
            df_in[lat_col] = pd.to_numeric(df_in[lat_col], errors='coerce')
            df_in[lon_col] = pd.to_numeric(df_in[lon_col], errors='coerce')
            df_in_valid = df_in[df_in[lat_col].notna() & df_in[lon_col].notna() & np.isfinite(df_in[lat_col]) & np.isfinite(df_in[lon_col])].copy()
            if not df_in_valid.empty:
                gdf_in = gpd.GeoDataFrame(df_in_valid, geometry=gpd.points_from_xy(df_in_valid[lon_col], df_in_valid[lat_col]), crs="EPSG:4326")
                gdf_in['type'] = 'Indoor'
            else:
                gdf_in = gpd.GeoDataFrame(columns=list(df_in.columns) + ['geometry','type'], crs="EPSG:4326")
        else:
            # No coordinate columns found — create empty GeoDataFrame
            gdf_in = gpd.GeoDataFrame(columns=list(df_in.columns) + ['geometry','type'], crs="EPSG:4326")

        # 2. Load Outdoor Features
        print("Loading outdoor cooling centers...")
        df_out = pd.read_csv(data_processed / 'outside_cooling_centers_final.csv')
        # Detect coordinate-like columns for outdoor dataset
        x_cols_out = [c for c in df_out.columns if c.lower() in ['x','lon','longitude']]
        y_cols_out = [c for c in df_out.columns if c.lower() in ['y','lat','latitude']]
        if x_cols_out and y_cols_out:
            xcol = x_cols_out[0]
            ycol = y_cols_out[0]
            df_out[xcol] = pd.to_numeric(df_out[xcol].astype(str).str.replace(',', ''), errors='coerce')
            df_out[ycol] = pd.to_numeric(df_out[ycol].astype(str).str.replace(',', ''), errors='coerce')
            valid_out = df_out[df_out[xcol].notna() & df_out[ycol].notna() & np.isfinite(df_out[xcol]) & np.isfinite(df_out[ycol])].copy()
            if not valid_out.empty:
                gdf_out = gpd.GeoDataFrame(valid_out, geometry=gpd.points_from_xy(valid_out[xcol], valid_out[ycol]), crs="EPSG:4326")
                gdf_out['type'] = 'Outdoor'
            else:
                gdf_out = gpd.GeoDataFrame(columns=list(df_out.columns) + ['geometry','type'], crs="EPSG:4326")
        else:
            gdf_out = gpd.GeoDataFrame(columns=list(df_out.columns) + ['geometry','type'], crs="EPSG:4326")

        # Check for coordinate outliers in outdoor centers (keep diagnostic if needed)
        invalid_out = pd.DataFrame()
        if 'xcol' in locals() and 'ycol' in locals():
            invalid_out = df_out[~((df_out[xcol].notna()) & (df_out[ycol].notna()) & np.isfinite(df_out[xcol]) & np.isfinite(df_out[ycol]))]

        # 3. Load Green Infrastructure
        print("Loading green infrastructure...")
        df_green = pd.read_csv(data_processed / 'green_spaces_final.csv')
        df_green['geometry'] = df_green['the_geom'].apply(wkt.loads)
        gdf_green = gpd.GeoDataFrame(df_green, geometry='geometry', crs="EPSG:4326")

        # 4. Load Urban Design (Buildings)
        print("Loading urban design data...")
        df_urban = pd.read_csv(data_processed / 'urban_design_final.csv', low_memory=False)
        df_urban['geometry'] = df_urban['the_geom'].apply(wkt.loads)
        gdf_urban = gpd.GeoDataFrame(df_urban, geometry='geometry', crs="EPSG:4326")
        gdf_urban['heat_index'] = calculate_heat_index(gdf_urban)

        # 5. Load Neighborhoods for context and aggregation
        print("Loading neighborhood boundaries...")
        neighborhoods = gpd.read_file(data_processed / 'neighborhoods_final.gpkg').to_crs("EPSG:4326")

        # 6. Aggregate heat index by neighborhood (prefer NTA/name fields, not borough)
        print("Aggregating heat index to neighborhood level...")
        urban_with_neigh = gpd.sjoin(gdf_urban, neighborhoods, how="left", predicate="within")

        def detect_neighborhood_key(df):
            # Common NTA/name column candidates
            preferred = ['nta_name', 'ntaname', 'nta', 'ntacode', 'ntaname20', 'ntaname_2020', 'name', 'label']
            cols = [c for c in df.columns if isinstance(c, str)]
            # try preferred list first
            for p in preferred:
                for c in cols:
                    if p in c.lower():
                        return c
            # fallback: any column that contains 'nta' or 'name' but not 'borough'
            candidates = [c for c in cols if ('nta' in c.lower() or 'name' in c.lower()) and 'borough' not in c.lower()]
            if candidates:
                return candidates[0]
            # last resort: first non-geometry string column
            for c in cols:
                if c != df.geometry.name:
                    return c
            return df.index.name or 'index'

        neigh_col = detect_neighborhood_key(neighborhoods)
        neigh_heat = urban_with_neigh.groupby(neigh_col)['heat_index'].agg(['mean', 'count']).reset_index()
        neighborhoods_heat = neighborhoods.merge(neigh_heat, on=neigh_col, how='left')
        neighborhoods_heat['mean'] = neighborhoods_heat['mean'].fillna(0)
        neighborhoods_heat['count'] = neighborhoods_heat['count'].fillna(0)

        # Combine indoor and outdoor into a single cooling GeoDataFrame and keep only points inside neighborhoods
        gdf_cooling = pd.concat([gdf_in, gdf_out], ignore_index=True, sort=False)
        # Ensure valid geometries
        if not gdf_cooling.empty:
            gdf_cooling = gdf_cooling[gdf_cooling.geometry.notna() & gdf_cooling.geometry.is_valid].copy()
            # spatial join to neighborhoods: keep only points within neighborhood polygons
            gdf_cooling = gpd.sjoin(gdf_cooling, neighborhoods.reset_index(), how='left', predicate='within')
            # drop points that did not join to any neighborhood
            if 'index' in gdf_cooling.columns:
                gdf_cooling = gdf_cooling[gdf_cooling['index'].notna()]
            gdf_cooling = gdf_cooling.set_geometry('geometry')

        gdf_green_valid = gdf_green[gdf_green.geometry.is_valid] if not gdf_green.empty else gdf_green

        # PANEL 1: Cooling Infrastructure Access (Full NYC) — plot Indoor and Outdoor in different colors
        fig1, ax1 = plt.subplots(1, 1, figsize=(14, 14))
        neighborhoods.plot(ax=ax1, color='whitesmoke', edgecolor='black', linewidth=0.5)
        if not gdf_cooling.empty:
            indoor_pts = gdf_cooling[gdf_cooling['type'] == 'Indoor'] if 'type' in gdf_cooling.columns else gdf_cooling.iloc[0:0]
            outdoor_pts = gdf_cooling[gdf_cooling['type'] == 'Outdoor'] if 'type' in gdf_cooling.columns else gdf_cooling.iloc[0:0]
            if not indoor_pts.empty:
                indoor_pts.plot(ax=ax1, color='blue', markersize=10, label='Indoor', alpha=0.85)
            if not outdoor_pts.empty:
                outdoor_pts.plot(ax=ax1, color='cyan', markersize=6, label='Outdoor', alpha=0.8)

        ax1.set_title("Cooling Infrastructure Access - All of NYC", fontsize=16, pad=10, weight='bold')
        ax1.legend(loc='upper right', fontsize=12)
        ax1.axis('off')
        plt.tight_layout()
        panel1_path = Outputs_path / 'Figures' / 'panel1_cooling_infrastructure.png'
        panel1_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(panel1_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Panel 1 saved")

        # PANEL 2: Green Infrastructure (Reduced visibility)
        fig2, ax2 = plt.subplots(1, 1, figsize=(14, 14))
        neighborhoods.plot(ax=ax2, color='whitesmoke', edgecolor='black', linewidth=0.5)
        if not gdf_green_valid.empty:
            gdf_green_valid.plot(ax=ax2, color='green', markersize=3, alpha=0.4)
        ax2.set_title("Nature-Based Solutions (NbS)", fontsize=16, pad=10, weight='bold')
        ax2.axis('off')
        plt.tight_layout()
        panel2_path = Outputs_path / 'Figures' / 'panel2_green_infrastructure.png'
        plt.savefig(panel2_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Panel 2 saved")

        # PANEL 3: Heat Vulnerability (Neighborhoods colored by heat index) - quantile bins per neighborhood
        fig3, ax3 = plt.subplots(1, 1, figsize=(14, 14))

        vals = neighborhoods_heat['mean'].astype(float)
        if vals.nunique() > 1:
            # create 5 quantile bins to increase sensitivity to local variation
            q = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
            bins = list(vals.quantile(q).values)
            # Ensure bins are strictly increasing
            bins = sorted(list(dict.fromkeys(bins)))
            if len(bins) < 2:
                bins = [vals.min(), vals.max()]
            neighborhoods_heat['heat_bin'] = pd.cut(vals, bins=bins, include_lowest=True, labels=False)
            n_bins = int(neighborhoods_heat['heat_bin'].max()) + 1
            cmap = plt.cm.get_cmap('YlOrRd', max(2, n_bins))
            neighborhoods_heat.plot(column='heat_bin', ax=ax3, cmap=cmap, categorical=True, edgecolor='black', linewidth=0.3, legend=False)

            # create legend patches showing bin ranges
            import matplotlib.patches as mpatches
            patches = []
            bin_edges = bins
            denom = max(1, len(bin_edges)-2)
            for i in range(len(bin_edges)-1):
                low = bin_edges[i]
                high = bin_edges[i+1]
                color = cmap(i/denom)
                label = f"{low:.1f} – {high:.1f}"
                patches.append(mpatches.Patch(color=color, label=label))
            ax3.legend(handles=patches, title='Mean Heat Index', loc='lower right', fontsize=10)
        else:
            neighborhoods_heat.plot(column='mean', ax=ax3, cmap='YlOrRd', edgecolor='black', linewidth=0.3, legend=True)

        ax3.set_title("Urban Design Heat Vulnerability by Neighborhood", fontsize=16, pad=10, weight='bold')
        ax3.text(0.02, 0.02, 'Color Scale: Yellow (Low Heat Risk) → Red (High Heat Risk)', 
                transform=ax3.transAxes, fontsize=11, verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        ax3.axis('off')
        plt.tight_layout()
        panel3_path = Outputs_path / 'Figures' / 'panel3_urban_design.png'
        plt.savefig(panel3_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Panel 3 saved")

        print(f"\n✓ Analysis complete. All maps saved to {Outputs_path / 'Figures'}")

    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
