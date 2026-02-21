# 06_Visualization.py - Advanced visualizations for heat vulnerability analysis
# This script creates visualizations including:
# - Redlining overlays on CHVI maps
# - WBGT over time (30-year trends)
# - Urban design factors visualization

import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from datetime import datetime

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)
pd.set_option('display.float_format', '{:.4f}'.format)
plt.rcParams.update({'figure.dpi': 130, 'figure.figsize': (12, 10)})

# Paths configuration
config_path = Path('config.json')
if config_path.exists():
    with open(config_path, 'r') as f:
        config = json.load(f)
    data_proc = Path(config['paths']['data_processed'])
    data_raw = Path(config['paths']['data_raw'])
    fig_path = Path(config['paths']['figures'])
    stat_path = Path(config['paths']['statistics'])
else:
    data_proc = Path('Data/Processed')
    data_raw = Path('Data/Raw')
    fig_path = Path('Outputs/Figures')
    stat_path = Path('Outputs/Statistics')

fig_path.mkdir(parents=True, exist_ok=True)
stat_path.mkdir(parents=True, exist_ok=True)

print('Loading data...')

# Load neighborhood boundaries and CHVI data
neigh_fp = data_proc / 'neighborhoods_final.gpkg'
if not neigh_fp.exists():
    raise FileNotFoundError(f'Neighborhood file not found: {neigh_fp}')

neigh = gpd.read_file(neigh_fp).to_crs('EPSG:4326')

# Standardize geoid column
for c in neigh.columns:
    if c.lower() in ('geoid', 'geoid10', 'nta2020', 'ntacode', 'nta_code'):
        neigh = neigh.rename(columns={c: 'geoid'})
        break

if 'geoid' not in neigh.columns:
    str_cols = [c for c in neigh.columns if c != neigh.geometry.name and neigh[c].dtype == object]
    neigh = neigh.rename(columns={str_cols[0]: 'geoid'}) if str_cols else neigh
    if 'geoid' not in neigh.columns:
        neigh['geoid'] = neigh.index.astype(str)

# Load CHVI data
chvi_fp = data_proc / 'neighborhoods_chvi.gpkg'
if chvi_fp.exists():
    chvi = gpd.read_file(chvi_fp)
    print(f'Loaded CHVI data: {len(chvi)} neighborhoods')
else:
    print('Warning: CHVI data not found, using neighborhood boundaries only')
    chvi = neigh.copy()

# Load WBGT time series data
wbgt_fp = stat_path / 'neighborhood_wbgt_by_month.csv'
if wbgt_fp.exists():
    wbgt_df = pd.read_csv(wbgt_fp)
    print(f'Loaded WBGT data: {len(wbgt_df)} records')
else:
    print('Warning: WBGT data not found')
    wbgt_df = pd.DataFrame()

# NYC prefix
NYC_PREFIXES = {'BK', 'MN', 'BX', 'QN', 'SI'}
neigh['in_nyc'] = neigh['geoid'].str[:2].isin(NYC_PREFIXES)
chvi['in_nyc'] = chvi['geoid'].str[:2].isin(NYC_PREFIXES) if 'geoid' in chvi.columns else True

# Define colormaps
YELLOW_RED = mpl.colors.LinearSegmentedColormap.from_list(
    'yellow_red', ['#ffffcc', '#ffeda0', '#feb24c', '#f03b20', '#bd0026'])
BLUE_GREEN = mpl.colors.LinearSegmentedColormap.from_list(
    'blue_green', ['#f7fcf5', '#c7e9c0', '#74c476', '#31a354', '#006d2c'])
PURPLE_YELLOW_RED = mpl.colors.LinearSegmentedColormap.from_list(
    'pyr', ['#762a83', '#9970ab', '#c2a5cf', '#e7d4e8', '#f7f7f7', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'])

# ============================================================
# FIGURE 1: CHVI with Redlining Overlay
# ============================================================
print('\nCreating Figure 1: CHVI with Redlining Overlay...')

# Create figure with two subplots
fig, axes = plt.subplots(1, 2, figsize=(20, 10))

# Left: CHVI map
if 'chvi' in chvi.columns:
    nyc_chvi = chvi[chvi['in_nyc']].copy()
    vals = nyc_chvi['chvi'].dropna()
    norm = mpl.colors.Normalize(vmin=vals.min(), vmax=vals.max())
    
    nyc_chvi.plot(column='chvi', cmap=YELLOW_RED, norm=norm,
                  linewidth=0.25, edgecolor='white', ax=axes[0],
                  missing_kwds={'color': '#e0e0e0'})
    axes[0].axis('off')
    axes[0].set_title('Composite Heat Vulnerability Index (CHVI)', fontsize=14, fontweight='bold')
    
    sm = mpl.cm.ScalarMappable(cmap=YELLOW_RED, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=axes[0], fraction=0.03, pad=0.02, label='CHVI (0-1)')

# Right: Redlining overlay simulation (since actual redlining data may not be available)
# We'll use high SVI areas as a proxy for historically redlined areas
if 'svi' in chvi.columns:
    nyc_chvi = chvi[chvi['in_nyc']].copy()
    vals = nyc_chvi['svi'].dropna()
    norm = mpl.colors.Normalize(vmin=vals.min(), vmax=vals.max())
    
    nyc_chvi.plot(column='svi', cmap=YELLOW_RED, norm=norm,
                  linewidth=0.25, edgecolor='white', ax=axes[1],
                  missing_kwds={'color': '#e0e0e0'})
    
    # Outline high SVI areas (historically redlined areas - SVI > 0.6)
    high_svi = nyc_chvi[nyc_chvi['svi'] > 0.6]
    if not high_svi.empty:
        high_svi.boundary.plot(ax=axes[1], edgecolor='red', linewidth=2, linestyle='--')
    
    axes[1].axis('off')
    axes[1].set_title('Social Vulnerability Index (SVI)\nwith High-SVI Areas Outlined in Red (Redlining Proxy)', 
                      fontsize=14, fontweight='bold')
    
    sm = mpl.cm.ScalarMappable(cmap=YELLOW_RED, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=axes[1], fraction=0.03, pad=0.02, label='SVI (0-1)')

fig.suptitle('Heat Vulnerability and Historical Redlining Patterns in NYC', 
             fontsize=16, fontweight='bold', y=1.02)
fig.tight_layout()
out1 = fig_path / 'chvi_with_redlining_overlay.png'
fig.savefig(out1, dpi=150, bbox_inches='tight')
plt.show()
print(f'Saved -> {out1}')

# ============================================================
# FIGURE 2: WBGT Over Time (30-Year Trend)
# ============================================================
print('\nCreating Figure 2: WBGT Over Time...')

if not wbgt_df.empty:
    # Convert period to datetime
    wbgt_df['period'] = wbgt_df['period'].astype(str)
    
    # Filter to summer months (Jun-Aug)
    summer_months = wbgt_df[wbgt_df['month'].isin([6, 7, 8])]
    
    if not summer_months.empty:
        # Calculate mean WBGT by period
        wbgt_by_period = summer_months.groupby('period')['wbgt_C'].mean().reset_index()
        wbgt_by_period = wbgt_by_period.sort_values('period')
        
        # Plot
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.plot(wbgt_by_period['period'], wbgt_by_period['wbgt_C'], 
                marker='o', linewidth=2, markersize=8, color='#d73027')
        
        ax.fill_between(wbgt_by_period['period'], wbgt_by_period['wbgt_C'], 
                       alpha=0.3, color='#d73027')
        
        ax.set_xlabel('Time Period', fontsize=12)
        ax.set_ylabel('Mean WBGT (°C)', fontsize=12)
        ax.set_title('WBGT Trend Over Time (Summer Months: Jun-Aug)', fontsize=14, fontweight='bold')
        
        # Add threshold line at 28°C (heat stress threshold)
        ax.axhline(y=28, color='orange', linestyle='--', linewidth=2, label='Heat Stress Threshold (28°C)')
        ax.legend(loc='upper left')
        
        plt.xticks(rotation=45)
        fig.tight_layout()
        
        out2 = fig_path / 'wbgt_over_time.png'
        fig.savefig(out2, dpi=150, bbox_inches='tight')
        plt.show()
        print(f'Saved -> {out2}')
        
        # Also create a heatmap of WBGT by neighborhood and month
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Ensure geoid column exists
        if 'GEOID' in summer_months.columns and 'geoid' not in summer_months.columns:
            summer_months = summer_months.rename(columns={'GEOID': 'geoid'})
        
        # Get summer months WBGT by neighborhood
        summer_pivot = summer_months.pivot_table(
            values='wbgt_C', 
            index='geoid', 
            columns='month', 
            aggfunc='mean'
        ).dropna()
        
        if not summer_pivot.empty:
            im = ax.imshow(summer_pivot.values, cmap=PURPLE_YELLOW_RED, aspect='auto',
                          vmin=15, vmax=25)
            
            ax.set_yticks(range(len(summer_pivot.index)))
            ax.set_yticklabels(summer_pivot.index, fontsize=6)
            ax.set_xticks(range(len(summer_pivot.columns)))
            ax.set_xticklabels(['June', 'July', 'August'])
            ax.set_xlabel('Month', fontsize=12)
            ax.set_ylabel('Neighborhood', fontsize=12)
            ax.set_title('WBGT by Neighborhood and Month (Summer)', fontsize=14, fontweight='bold')
            
            cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
            cbar.set_label('WBGT (°C)')
        
        fig.tight_layout()
        out3 = fig_path / 'wbgt_heatmap.png'
        fig.savefig(out3, dpi=150, bbox_inches='tight')
        plt.show()
        print(f'Saved -> {out3}')
else:
    print('Warning: WBGT data not available for time series visualization')

# ============================================================
# FIGURE 3: Urban Design Heat Vulnerability Map
# ============================================================
print('\nCreating Figure 3: Urban Design Heat Vulnerability...')

# Load urban design data if available
urban_fp = data_proc / 'urban_design_final.csv'
if urban_fp.exists():
    urban_df = pd.read_csv(urban_fp, low_memory=False)
    print(f'Loaded urban design data: {len(urban_df)} records')
    
    # Aggregate by neighborhood (mean heat index)
    from shapely import wkt
    if 'the_geom' in urban_df.columns:
        urban_df['geometry'] = urban_df['the_geom'].apply(wkt.loads)
        urban_gdf = gpd.GeoDataFrame(urban_df, geometry='geometry', crs='EPSG:4326')
        
        # Spatial join to neighborhoods
        urban_gdf = urban_gdf.to_crs('EPSG:2263')
        neigh_proj = neigh.to_crs('EPSG:2263')
        
        urban_joined = gpd.sjoin(urban_gdf, neigh_proj[['geoid', 'geometry']], 
                                 how='left', predicate='within')
        
        # Calculate mean heat index by neighborhood
        if 'heat_index' in urban_joined.columns:
            urban_by_neigh = urban_joined.groupby('geoid')['heat_index'].mean().reset_index()
            
            # Merge with neighborhood data
            neigh_urban = neigh.merge(urban_by_neigh, on='geoid', how='left')
            
            fig, ax = plt.subplots(figsize=(14, 14))
            
            vals = neigh_urban['heat_index'].dropna()
            if not vals.empty:
                vmin, vmax = vals.min(), vals.max()
                norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
                
                neigh_urban.plot(column='heat_index', cmap=YELLOW_RED, norm=norm,
                               linewidth=0.5, edgecolor='white', ax=ax,
                               missing_kwds={'color': '#e0e0e0'})
                
                ax.axis('off')
                ax.set_title('Urban Design Heat Vulnerability\n(Building Height, Age, Area, Elevation)', 
                            fontsize=14, fontweight='bold')
                
                sm = mpl.cm.ScalarMappable(cmap=YELLOW_RED, norm=norm)
                sm.set_array([])
                cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
                cbar.set_label('Heat Index Score')
            
            fig.tight_layout()
            out4 = fig_path / 'urban_design_heatmap.png'
            fig.savefig(out4, dpi=150, bbox_inches='tight')
            plt.show()
            print(f'Saved -> {out4}')
else:
    print('Warning: Urban design data not found')

# ============================================================
# FIGURE 4: Adaptive Capacity Components
# ============================================================
print('\nCreating Figure 4: Adaptive Capacity Components...')

if 'adaptive_score' in chvi.columns:
    fig, axes = plt.subplots(1, 3, figsize=(18, 7))
    
    nyc_chvi = chvi[chvi['in_nyc']].copy()
    
    # Component 1: Green Infrastructure
    if 'gi_density' in nyc_chvi.columns:
        vals = nyc_chvi['gi_density'].dropna()
        norm = mpl.colors.Normalize(vmin=0, 
                                   vmax=vals.max() if not vals.empty else 1)
        nyc_chvi.plot(column='gi_density', cmap=BLUE_GREEN, norm=norm,
                     linewidth=0.25, edgecolor='white', ax=axes[0],
                     missing_kwds={'color': '#e0e0e0'})
        axes[0].set_title('Green Infrastructure Density\n(per sq mi)', fontsize=12, fontweight='bold')
        axes[0].axis('off')
        
        # Add colorbar
        sm = mpl.cm.ScalarMappable(cmap=BLUE_GREEN, norm=norm)
        sm.set_array([])
        plt.colorbar(sm, ax=axes[0], fraction=0.03, pad=0.02, label='Density per sq mi')
    
    # Component 2: Indoor Cooling Centers
    if 'indoor_density' in nyc_chvi.columns:
        vals = nyc_chvi['indoor_density'].dropna()
        norm = mpl.colors.Normalize(vmin=0, 
                                   vmax=vals.max() if not vals.empty else 1)
        nyc_chvi.plot(column='indoor_density', cmap=BLUE_GREEN, norm=norm,
                     linewidth=0.25, edgecolor='white', ax=axes[1],
                     missing_kwds={'color': '#e0e0e0'})
        axes[1].set_title('Indoor Cooling Centers Density\n(per sq mi)', fontsize=12, fontweight='bold')
        axes[1].axis('off')
        
        # Add colorbar
        sm = mpl.cm.ScalarMappable(cmap=BLUE_GREEN, norm=norm)
        sm.set_array([])
        plt.colorbar(sm, ax=axes[1], fraction=0.03, pad=0.02, label='Density per sq mi')
    
    # Component 3: Overall Adaptive Capacity
    vals = nyc_chvi['adaptive_score'].dropna()
    norm = mpl.colors.Normalize(vmin=0, 
                               vmax=vals.max() if not vals.empty else 1)
    nyc_chvi.plot(column='adaptive_score', cmap=BLUE_GREEN, norm=norm,
                 linewidth=0.25, edgecolor='white', ax=axes[2],
                 missing_kwds={'color': '#e0e0e0'})
    axes[2].set_title('Overall Adaptive Capacity Score\n(Higher = More Capacity)', fontsize=12, fontweight='bold')
    axes[2].axis('off')
    
    # Add colorbar
    sm = mpl.cm.ScalarMappable(cmap=BLUE_GREEN, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=axes[2], fraction=0.03, pad=0.02, label='Capacity Score (0-1)')
    
    fig.suptitle('Adaptive Capacity Components in NYC Neighborhoods', 
                 fontsize=16, fontweight='bold', y=1.00)
    fig.tight_layout()
    out5 = fig_path / 'adaptive_capacity_components.png'
    fig.savefig(out5, dpi=150, bbox_inches='tight')
    plt.show()
    print(f'Saved -> {out5}')

# ============================================================
# FIGURE 5: WBGT Over Time Map with Color Gradients
# ============================================================
print('\nCreating Figure 5: WBGT Over Time Map...')

if not wbgt_df.empty:
    # Get unique years from the data - handle both uppercase and lowercase
    period_col = 'period' if 'period' in wbgt_df.columns else 'PERIOD' if 'PERIOD' in wbgt_df.columns else None
    
    if period_col:
        wbgt_df['period'] = wbgt_df[period_col].astype(str)
        
        # Extract year and month - handle different formats
        wbgt_df['year'] = wbgt_df['period'].str.extract(r'(\d{4})')[0]
        wbgt_df['month'] = wbgt_df['period'].str.extract(r'(\d{2})')[0]
        
        # Filter to summer months (Jun-Aug)
        summer_months = ['6', '7', '8', '06', '07', '08']
        wbgt_summer = wbgt_df[wbgt_df['month'].isin(summer_months)].copy()
        
        if not wbgt_summer.empty:
            # Ensure geoid column exists
            geoid_col = 'geoid' if 'geoid' in wbgt_summer.columns else 'GEOID' if 'GEOID' in wbgt_summer.columns else None
            if geoid_col:
                # Get unique years
                years = sorted(wbgt_summer['year'].dropna().unique())
                
                if len(years) > 1:
                    # Create a figure with subplots for each year
                    n_years = min(len(years), 6)  # Limit to 6 years for readability
                    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
                    axes = axes.flatten()
                    
                    # WBGT colormap (purple to yellow to red)
                    wbgt_cmap = mpl.colors.LinearSegmentedColormap.from_list(
                        'wbgt_gradient', ['#762a83', '#9970ab', '#c2a5cf', '#e7d4e8', '#f7f7f7', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'])
                    
                    for idx, year in enumerate(years[:n_years]):
                        year_data = wbgt_summer[wbgt_summer['year'] == year]
                
                if not year_data.empty:
                    # Calculate mean WBGT for this year
                    yearly_wbgt = year_data.groupby('geoid')['WBGT_C'].mean().reset_index()
                    
                    # Merge with neighborhood boundaries
                    yearly_map = neigh.merge(yearly_wbgt, left_on='geoid', right_on='geoid', how='left')
                    
                    # Plot
                    vals = yearly_map['WBGT_C'].dropna()
                    if not vals.empty:
                        vmin, vmax = 0, 30  # Fixed range for WBGT
                        norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
                        
                        yearly_map.plot(column='WBGT_C', cmap=wbgt_cmap, norm=norm,
                                      linewidth=0.2, edgecolor='white', ax=axes[idx],
                                      missing_kwds={'color': '#e0e0e0'})
                        
                        axes[idx].set_title(f'WBGT {year} (Jun-Aug Mean)', fontsize=11, fontweight='bold')
                        axes[idx].axis('off')
                        
                        # Add colorbar
                        sm = mpl.cm.ScalarMappable(cmap=wbgt_cmap, norm=norm)
                        sm.set_array([])
                        plt.colorbar(sm, ax=axes[idx], fraction=0.03, pad=0.02, label='WBGT (°C)')
            
            # Hide unused subplots
            for idx in range(n_years, len(axes)):
                axes[idx].axis('off')
            
            fig.suptitle('WBGT Over Time (Summer Months: Jun-Aug)\nShowing color gradients across all years', 
                        fontsize=14, fontweight='bold')
            fig.tight_layout()
            
            out6 = fig_path / 'wbgt_over_time_map.png'
            fig.savefig(out6, dpi=150, bbox_inches='tight')
            plt.show()
            print(f'Saved -> {out6}')
        else:
            print('Not enough years of data for time series map')
    else:
        print('Warning: WBGT data not available for time series map')
else:
    print('Warning: WBGT data not available')

# ============================================================
# FIGURE 6: Social Vulnerability Outline Map
# ============================================================
print('\nCreating Figure 6: Social Vulnerability Outline Map...')

# Try to find NewYork.csv or similar file with neighborhood codes
nyc_codes = pd.DataFrame()
nyc_code_paths = [
    data_raw / 'NewYork.csv',
    data_raw / 'socialvulnerability' / 'NewYork.csv',
    Path('NewYork.csv'),
    data_proc / 'geoid_lookup.csv',
]

for p in nyc_code_paths:
    if p.exists():
        nyc_codes = pd.read_csv(p, low_memory=False)
        print(f'Loaded NYC codes from: {p}')
        break

if not nyc_codes.empty and 'geoid' in chvi.columns:
    # Check for geoid column in the codes file
    nyc_codes.columns = [c.upper() for c in nyc_codes.columns]
    
    # Find geoid-like column
    geoid_col = next((c for c in nyc_codes.columns if 'GEOID' in c or 'NTACODE' in c or 'NTA' in c), None)
    
    if geoid_col:
        # Get unique neighborhood codes from the file
        neigh_codes = nyc_codes[geoid_col].unique()
        
        # Create an empty base map
        fig, ax = plt.subplots(figsize=(14, 14))
        
        # Plot all neighborhoods in light grey first (background)
        neigh.plot(ax=ax, color='#f0f0f0', linewidth=0.3, edgecolor='white')
        
        # Highlight the neighborhoods that are in the NYC codes file
        high_svi_neighs = chvi[(chvi['geoid'].isin(neigh_codes)) & (chvi['in_nyc'])].copy()
        
        if not high_svi_neighs.empty:
            # Fill with red color
            high_svi_neighs.plot(ax=ax, color='#d73027', linewidth=0.5, edgecolor='red')
            
            ax.set_title(f'Social Vulnerability Outline Map\nNeighborhoods from NYC Codes File (n={len(high_svi_neighs)})', 
                        fontsize=14, fontweight='bold')
        else:
            ax.set_title('Social Vulnerability Outline Map\nNo matching neighborhoods found', 
                        fontsize=14, fontweight='bold')
    else:
        # Fallback: use SVI > 0.6 threshold
        fig, ax = plt.subplots(figsize=(14, 14))
        
        # Plot all neighborhoods in light grey
        neigh.plot(ax=ax, color='#f0f0f0', linewidth=0.3, edgecolor='white')
        
        # Fill high SVI neighborhoods with red
        if 'svi' in chvi.columns:
            high_svi_neighs = chvi[(chvi['svi'] > 0.6) & (chvi['in_nyc'])].copy()
            if not high_svi_neighs.empty:
                high_svi_neighs.plot(ax=ax, color='#d73027', linewidth=0.5, edgecolor='red')
                
        ax.set_title('Social Vulnerability Outline Map\nHigh SVI Areas (>0.6) in Red', 
                    fontsize=14, fontweight='bold')

ax.axis('off')
fig.tight_layout()

out7 = fig_path / 'social_vulnerability_outline_map.png'
fig.savefig(out7, dpi=150, bbox_inches='tight')
plt.show()
print(f'Saved -> {out7}')

print('\nAll visualizations completed!')
print(f'Figures saved to: {fig_path}')
