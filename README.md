# Equitable Access to Urban Heat Adaptation Infrastructure and Heat Vulnerability in New York City

## Project Overview

This research examines how equitable access to urban heat adaptation infrastructure influences heat vulnerability in historically underserved neighborhoods of New York City.

### Methodology

**Composite Heat Vulnerability Index (CHVI):**
- **Heat Exposure**: Measured using Wet Bulb Globe Temperature (WBGT > 28°C)
- **Social Vulnerability**: 12 factors simplified (excluding transportation) from the CDC Social Vulnerability Index (SVI) to measure community susceptibility to heat-related health impacts
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
- [2020 Demographics by Neighborhood Tabulation Area (NTA) from Department for the Aging](https://www.nyc.gov/assets/dfta/downloads/pdf/reports/Demographics_by_NTA.pdf)
- [2016-2020 Economic and Housing Data from NYC.GOV](https://a816-dohbesp.nyc.gov/IndicatorPublic/data-explorer/economic-conditions/?id=103#display=summary)
- [1982-2020 30 year nominal climate data from PRISM](https://prism.oregonstate.edu/normals/)
- [2020 NYC Social Vulnerability from CDC/ATSDR Social Vulnerability Index](https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html?CDC_AAref_Val=https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html)
- []()
