"""Download PRISM 30-year monthly normals (800m) for variables used in the WBGT notebook.

Downloads and extracts into Data/Raw/Climate/<variable>_us_30s_monthly/
Variables downloaded by default: tmax, vpdmax, soltotal, soltrans

Usage: python scripts/download_prism_normals.py
"""
import sys
import os
from pathlib import Path
import urllib.request
import time
import zipfile

BASE = 'https://data.prism.oregonstate.edu/normals/us/800m'
OUT_ROOT = Path('Data/Raw/Climate')
OUT_ROOT.mkdir(parents=True, exist_ok=True)

VARIABLES = [
    'tmax',      # maximum temperature (30yr monthly normals)
    'vpdmax',    # max vapor pressure deficit
    'soltotal',  # solar radiation (horiz sfc)
    'soltrans',  # cloud transmittance
]

MONTHS = [f'2020{m:02d}' for m in range(1,13)]
ANNUAL = '2020'


def download(url, dest, max_retries=3):
    if dest.exists():
        print('Exists, skipping:', dest)
        return
    for attempt in range(1, max_retries+1):
        try:
            print(f'Downloading ({attempt}/{max_retries}):', url)
            urllib.request.urlretrieve(url, dest)
            print('Saved to', dest)
            return
        except Exception as e:
            print('Download failed:', e)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise


def extract_zip(zip_path, out_dir):
    print('Extracting', zip_path, '->', out_dir)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(out_dir)


def main():
    downloaded = []
    for var in VARIABLES:
        var_monthly_dir = OUT_ROOT / f'prism_{var}_us_30s_monthly'
        var_monthly_dir.mkdir(parents=True, exist_ok=True)
        remote_dir = f'{BASE}/{var}/monthly'

        # download all months
        for m in MONTHS + [ANNUAL]:
            if m == ANNUAL:
                zipname = f'prism_{var}_us_30s_{m}_avg_30y.zip'
            else:
                zipname = f'prism_{var}_us_30s_{m}_avg_30y.zip'
            url = f'{remote_dir}/{zipname}'
            local_zip = OUT_ROOT / 'download_cache' / zipname
            local_zip.parent.mkdir(parents=True, exist_ok=True)
            # (re)download and verify extraction; retry if extraction fails
            tries = 0
            success = False
            while tries < 3 and not success:
                tries += 1
                try:
                    # (re)download the zip if missing or if this is a retry
                    if not local_zip.exists() or tries > 1:
                        if local_zip.exists():
                            local_zip.unlink()
                        download(url, local_zip)
                    extract_zip(local_zip, var_monthly_dir)

                    # verify the expected .tif exists in the destination directory
                    expected_tif_stem = zipname.replace('.zip', '.tif')
                    expected_tif = var_monthly_dir / expected_tif_stem
                    if expected_tif.exists():
                        downloaded.append((var, zipname))
                        success = True
                        break
                    else:
                        print('Extraction succeeded but expected .tif not found:', expected_tif)
                        # force a re-download on next loop
                        if local_zip.exists():
                            local_zip.unlink()
                except Exception as e:
                    print(f'Attempt {tries} failed for {zipname}:', e)
                    # remove corrupt zip before retry
                    if local_zip.exists():
                        try:
                            local_zip.unlink()
                        except Exception:
                            pass
                    time.sleep(1)
            if not success:
                print('Failed after retries:', url)

    # report
    print('\nDownload summary:')
    for var in VARIABLES:
        d = OUT_ROOT / f'prism_{var}_us_30s_monthly'
        tif_count = len(list(d.glob('*.tif')))
        print(f'  {var}: {tif_count} .tif files in {d}')

    print('\nDone. Files are placed under Data/Raw/Climate/.')
    print('Run the notebook `03_WbgtCalculation.ipynb` to process the new rasters.')


if __name__ == '__main__':
    main()
