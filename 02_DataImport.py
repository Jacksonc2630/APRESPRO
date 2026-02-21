# Load Libraries
import json
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

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

# Load neighborhood data from preprocessing
neighborhoods = gpd.read_file(data_processed / 'neighborhoods_clean.gpkg')

# Load social vulnerability data
socialvulnerability_data = pd.read_csv(socialvulnerability_path / 'NewYork.csv')

# Load redlining data
redlining_data = pd.read_csv(redlining_path / 'redlining.csv')

# Load infrastructure data
outside_cooling_centers = pd.read_csv(infrastructure_path / 'CoolingCenters' / 'Cool_It!_NYC_2020_-_Cooling_Sites_20260208.csv')
inside_cooling_centers = pd.read_csv(infrastructure_path / 'CoolingCenters' / 'Cooling_centers.csv')
green_spaces = pd.read_csv(infrastructure_path / 'GreenInfrastructure' / 'DEP_Green_Infrastructure_(Point_Layer)_20260208.csv')
urban_design = pd.read_csv(infrastructure_path / 'UrbanDesign' / 'BUILDING_20260208.csv')

# Save all processed datasets for analysis
neighborhoods.to_file(data_processed / 'neighborhoods_final.gpkg', driver='GPKG')
socialvulnerability_data.to_csv(data_processed / 'socialvulnerability.csv', index=False)
outside_cooling_centers.to_csv(data_processed / 'outside_cooling_centers_final.csv', index=False)
inside_cooling_centers.to_csv(data_processed / 'inside_cooling_centers_final.csv', index=False)
green_spaces.to_csv(data_processed / 'green_spaces_final.csv', index=False)
urban_design.to_csv(data_processed / 'urban_design_final.csv', index=False)
redlining_data.to_csv(data_processed / 'redlining_final.csv', index=False)