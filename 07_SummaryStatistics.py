# 07_SummaryStatistics.py - Summary statistics and disparity analysis
# This script generates final statistics and disparity analysis for the heat vulnerability project

import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)
pd.set_option('display.float_format', '{:.4f}'.format)

# Paths configuration
config_path = Path('config.json')
if config_path.exists():
    with open(config_path, 'r') as f:
        config = json.load(f)
    data_proc = Path(config['paths']['data_processed'])
    fig_path = Path(config['paths']['figures'])
    stat_path = Path(config['paths']['statistics'])
else:
    data_proc = Path('Data/Processed')
    fig_path = Path('Outputs/Figures')
    stat_path = Path('Outputs/Statistics')

stat_path.mkdir(parents=True, exist_ok=True)

print('='*80)
print('SUMMARY STATISTICS AND DISPARITY ANALYSIS')
print('Equitable Access to Urban Heat Adaptation Infrastructure')
print('='*80)

# Load data
print('\nLoading data...')

# Load CHVI data
chvi_fp = data_proc / 'neighborhoods_chvi.gpkg'
if not chvi_fp.exists():
    raise FileNotFoundError(f'CHVI data not found: {chvi_fp}')

chvi = gpd.read_file(chvi_fp)
print(f'Loaded CHVI data: {len(chvi)} neighborhoods')

# Load WBGT data
wbgt_fp = stat_path / 'neighborhood_wbgt_by_month.csv'
if wbgt_fp.exists():
    wbgt_df = pd.read_csv(wbgt_fp)
    print(f'Loaded WBGT data: {len(wbgt_df)} records')

# NYC prefix
NYC_PREFIXES = {'BK', 'MN', 'BX', 'QN', 'SI'}
chvi['in_nyc'] = chvi['geoid'].str[:2].isin(NYC_PREFIXES) if 'geoid' in chvi.columns else True
nyc_chvi = chvi[chvi['in_nyc']].copy()

# Borough mapping
BORO_MAPPING = {
    'BK': 'Brooklyn',
    'MN': 'Manhattan', 
    'BX': 'Bronx',
    'QN': 'Queens',
    'SI': 'Staten Island'
}

# ============================================================
# 1. OVERALL CHVI STATISTICS
# ============================================================
print('\n' + '='*80)
print('1. OVERALL CHVI STATISTICS')
print('='*80)

if 'chvi' in nyc_chvi.columns:
    print('\nCHVI Score Distribution:')
    print(nyc_chvi['chvi'].describe().round(4).to_string())
    
    print('\nCHVI Quintile Distribution:')
    if 'chvi_class' in nyc_chvi.columns:
        print(nyc_chvi['chvi_class'].value_counts().sort_index().to_string())

# ============================================================
# 2. WBGT STATISTICS
# ============================================================
print('\n' + '='*80)
print('2. WBGT (HEAT EXPOSURE) STATISTICS')
print('='*80)

if 'wbgt' in nyc_chvi.columns:
    print('\nWBGT (°C) - Summer Mean:')
    print(nyc_chvi['wbgt'].describe().round(4).to_string())

# WBGT by borough
if 'geoid' in nyc_chvi.columns:
    nyc_chvi['borough'] = nyc_chvi['geoid'].str[:2].map(BORO_MAPPING)
    
    print('\nWBGT by Borough:')
    boro_wbgt = nyc_chvi.groupby('borough')['wbgt'].agg(['mean', 'std', 'min', 'max']).round(4)
    print(boro_wbgt.to_string())

# ============================================================
# 3. SOCIAL VULNERABILITY STATISTICS
# ============================================================
print('\n' + '='*80)
print('3. SOCIAL VULNERABILITY INDEX (SVI) STATISTICS')
print('='*80)

if 'svi' in nyc_chvi.columns:
    print('\nSVI Score Distribution:')
    print(nyc_chvi['svi'].describe().round(4).to_string())
    
    print('\nSVI by Borough:')
    boro_svi = nyc_chvi.groupby('borough')['svi'].agg(['mean', 'std', 'min', 'max']).round(4)
    print(boro_svi.to_string())

# ============================================================
# 4. ADAPTIVE CAPACITY STATISTICS
# ============================================================
print('\n' + '='*80)
print('4. ADAPTIVE CAPACITY STATISTICS')
print('='*80)

if 'adaptive_score' in nyc_chvi.columns:
    print('\nAdaptive Capacity Score Distribution:')
    print(nyc_chvi['adaptive_score'].describe().round(4).to_string())
    
    print('\nInfrastructure Counts by Borough:')
    infra_cols = ['gi_count', 'indoor_count']
    existing_infra_cols = [c for c in infra_cols if c in nyc_chvi.columns]
    if existing_infra_cols:
        boro_infra = nyc_chvi.groupby('borough')[existing_infra_cols].sum()
        print(boro_infra.to_string())
    
    print('\nInfrastructure Density by Borough:')
    density_cols = ['gi_density', 'indoor_density']
    existing_density_cols = [c for c in density_cols if c in nyc_chvi.columns]
    if existing_density_cols:
        boro_density = nyc_chvi.groupby('borough')[existing_density_cols].mean().round(4)
        print(boro_density.to_string())

# ============================================================
# 5. DISPARITY ANALYSIS
# ============================================================
print('\n' + '='*80)
print('5. DISPARITY ANALYSIS')
print('='*80)

# Compare high vs low SVI neighborhoods
if 'svi' in nyc_chvi.columns and 'chvi' in nyc_chvi.columns:
    high_svi = nyc_chvi[nyc_chvi['svi'] >= 0.6]
    low_svi = nyc_chvi[nyc_chvi['svi'] < 0.4]
    
    print('\nComparison: High SVI (>=0.6) vs Low SVI (<0.4) Neighborhoods')
    print(f'High SVI neighborhoods: {len(high_svi)}')
    print(f'Low SVI neighborhoods: {len(low_svi)}')
    
    if 'wbgt' in nyc_chvi.columns:
        print(f'\nMean WBGT:')
        print(f'  High SVI: {high_svi["wbgt"].mean():.2f}°C')
        print(f'  Low SVI:  {low_svi["wbgt"].mean():.2f}°C')
    
    if 'adaptive_score' in nyc_chvi.columns:
        print(f'\nMean Adaptive Capacity:')
        print(f'  High SVI: {high_svi["adaptive_score"].mean():.4f}')
        print(f'  Low SVI:  {low_svi["adaptive_score"].mean():.4f}')
    
    print(f'\nMean CHVI:')
    print(f'  High SVI: {high_svi["chvi"].mean():.4f}')
    print(f'  Low SVI:  {low_svi["chvi"].mean():.4f}')

# ============================================================
# 6. TOP 10 MOST VULNERABLE NEIGHBORHOODS
# ============================================================
print('\n' + '='*80)
print('6. TOP 10 MOST HEAT-VULNERABLE NEIGHBORHOODS')
print('='*80)

if 'chvi' in nyc_chvi.columns:
    top10 = nyc_chvi.nlargest(10, 'chvi')[['geoid', 'borough', 'wbgt', 'svi', 'adaptive_score', 'chvi']]
    if 'ntaname' in nyc_chvi.columns:
        top10 = nyc_chvi.nlargest(10, 'chvi')[['geoid', 'ntaname', 'borough', 'wbgt', 'svi', 'adaptive_score', 'chvi']]
    print(top10.round(4).to_string(index=False))

# ============================================================
# 7. TOP 10 LEAST VULNERABLE NEIGHBORHOODS
# ============================================================
print('\n' + '='*80)
print('7. TOP 10 LEAST HEAT-VULNERABLE NEIGHBORHOODS')
print('='*80)

if 'chvi' in nyc_chvi.columns:
    bottom10 = nyc_chvi.nsmallest(10, 'chvi')[['geoid', 'borough', 'wbgt', 'svi', 'adaptive_score', 'chvi']]
    if 'ntaname' in nyc_chvi.columns:
        bottom10 = nyc_chvi.nsmallest(10, 'chvi')[['geoid', 'ntaname', 'borough', 'wbgt', 'svi', 'adaptive_score', 'chvi']]
    print(bottom10.round(4).to_string(index=False))

# ============================================================
# 8. CORRELATION ANALYSIS
# ============================================================
print('\n' + '='*80)
print('8. CORRELATION ANALYSIS')
print('='*80)

corr_cols = ['wbgt', 'svi', 'adaptive_score', 'chvi']
existing_corr_cols = [c for c in corr_cols if c in nyc_chvi.columns]
if len(existing_corr_cols) > 1:
    corr_matrix = nyc_chvi[existing_corr_cols].corr()
    print('\nCorrelation Matrix:')
    print(corr_matrix.round(4).to_string())

# ============================================================
# 9. SAVE SUMMARY TO CSV
# ============================================================
print('\n' + '='*80)
print('9. SAVING SUMMARY STATISTICS')
print('='*80)

# Save borough summary
borough_summary = nyc_chvi.groupby('borough').agg({
    'wbgt': ['mean', 'std', 'min', 'max'] if 'wbgt' in nyc_chvi.columns else [],
    'svi': ['mean', 'std', 'min', 'max'] if 'svi' in nyc_chvi.columns else [],
    'adaptive_score': ['mean', 'std', 'min', 'max'] if 'adaptive_score' in nyc_chvi.columns else [],
    'chvi': ['mean', 'std', 'min', 'max'] if 'chvi' in nyc_chvi.columns else []
}).round(4)

borough_summary.to_csv(stat_path / 'borough_summary.csv')
print(f'Saved borough summary -> {stat_path / "borough_summary.csv"}')

# Save neighborhood summary
neighborhood_summary_cols = ['geoid', 'borough']
if 'ntaname' in nyc_chvi.columns:
    neighborhood_summary_cols.append('ntaname')
neighborhood_summary_cols += [c for c in ['wbgt', 'svi', 'adaptive_score', 'chvi', 'chvi_class'] 
                             if c in nyc_chvi.columns]

nyc_chvi[neighborhood_summary_cols].to_csv(stat_path / 'neighborhood_summary.csv', index=False)
print(f'Saved neighborhood summary -> {stat_path / "neighborhood_summary.csv"}')

# Save disparity analysis
disparity_data = []
if 'svi' in nyc_chvi.columns:
    for boro in BORO_MAPPING.values():
        boro_data = nyc_chvi[nyc_chvi['borough'] == boro]
        high_svi_boro = boro_data[boro_data['svi'] >= 0.6]
        low_svi_boro = boro_data[boro_data['svi'] < 0.4]
        
        disparity_data.append({
            'borough': boro,
            'n_neighborhoods': len(boro_data),
            'n_high_svi': len(high_svi_boro),
            'n_low_svi': len(low_svi_boro),
            'mean_wbgt_high_svi': high_svi_boro['wbgt'].mean() if 'wbgt' in boro_data.columns and len(high_svi_boro) > 0 else np.nan,
            'mean_wbgt_low_svi': low_svi_boro['wbgt'].mean() if 'wbgt' in boro_data.columns and len(low_svi_boro) > 0 else np.nan,
            'mean_adaptive_high_svi': high_svi_boro['adaptive_score'].mean() if 'adaptive_score' in boro_data.columns and len(high_svi_boro) > 0 else np.nan,
            'mean_adaptive_low_svi': low_svi_boro['adaptive_score'].mean() if 'adaptive_score' in boro_data.columns and len(low_svi_boro) > 0 else np.nan,
            'mean_chvi_high_svi': high_svi_boro['chvi'].mean() if 'chvi' in boro_data.columns and len(high_svi_boro) > 0 else np.nan,
            'mean_chvi_low_svi': low_svi_boro['chvi'].mean() if 'chvi' in boro_data.columns and len(low_svi_boro) > 0 else np.nan,
        })

disparity_df = pd.DataFrame(disparity_data)
disparity_df.to_csv(stat_path / 'disparity_analysis.csv', index=False)
print(f'Saved disparity analysis -> {stat_path / "disparity_analysis.csv"}')

print('\n' + '='*80)
print('SUMMARY STATISTICS COMPLETE')
print('='*80)
print(f'\nOutput files saved to: {stat_path}')
