# Equitable Access to Urban Heat Adaptation Infrastructure and Heat Vulnerability in New York City

## Project Overview

This research examines how equitable access to urban heat adaptation infrastructure influences heat vulnerability in historically underserved neighborhoods of New York City.

### Methodology

**Composite Heat Vulnerability Index (CHVI):**
- **Heat Exposure**: Measured using Wet Bulb Globe Temperature (WBGT > 28°C)
- **Social Vulnerability**: CDC's Social Vulnerability Index (SVI) to measure community susceptibility to heat-related health impacts
- **Adaptive Capacity**: Access to cooling centers, green spaces, and urban design factors

### Directory Structure

```
APRESPRO/
├── Code/
│   └── Notebooks/
├── Data/
│   ├── Raw/
│   │   ├── Climate/
│   │   ├── Demographics/
│   │   ├── Infrastructure/
│   │   ├── Shapefiles/
│   │   └── Redlining/
│   └── Processed/
├── Outputs/
│   ├── Figures/
│   └── Statistics/
└── config.json
```

### Notebooks

Run in this order:
1. **00_Initialization.ipynb** - Setup project structure
2. **01_Preprocessing.ipynb** - Clean and standardize spatial data
3. **02_Setup.ipynb** - Configure analysis parameters
4. **03_DataImport.ipynb** - Load all datasets
5. **04_WbgtCalculation.ipynb** - Calculate heat exposure metrics
6. **05_CompositeHeatVulnerabilityIndex.ipynb** - Compute social vulnerability
7. **06_AdaptiveCapacity.ipynb** - Measure infrastructure access
8. **07_Visualization.ipynb** - Create maps and figures
9. **08_SummaryStatistics.ipynb** - Generate final statistics and disparity analysis

### Data Availability

- [2020 Census Tracts Shapefile from NYC Department of City Planning](https://www.nyc.gov/content/planning/pages/resources/datasets/census-tracts)
- [2020 Neighborhood Tabulation Areas (NTAs) Shapefile from NYC Department of City Planning](https://www.nyc.gov/content/planning/pages/resources/datasets/neighborhood-tabulation)
- [2020 Community Districts Shapefile from NYC Department of City Planning](https://www.nyc.gov/content/planning/pages/resources/datasets/community-districts)
- [1982-2020 30 year nominal climate data from PRISM](https://prism.oregonstate.edu/normals/)
- [2020 NYC Social Vulnerability from CDC/ATSDR Social Vulnerability Index](https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html?CDC_AAref_Val=https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html)
- [Historical Redlining dating 1970s from NYC GOV](https://a816-dohbesp.nyc.gov/IndicatorPublic/data-stories/redlining/)
- [Urban Building design from NYC Department of City Planning](https://data.cityofnewyork.us/City-Government/BUILDING/3g6p-4u5s)
- [Green Infrastructure from Department of Environmental Protection](https://data.cityofnewyork.us/Environment/DEP-Green-Infrastructure-Point-Layer-/df32-vzax/about_data)
- [CoolIt! NYC Cooling features (Outdoor) from Department of Parks and Recreation](https://data.cityofnewyork.us/dataset/Cool-It-NYC-2020-Cooling-Sites/h2bn-gu9k/about_data)
- [Cooling centers (Indoors) from NYC.DATA.MAPS](https://www.arcgis.com/home/item.html?id=a0643f21b5e24d1ea3ba1406775c4e52)
