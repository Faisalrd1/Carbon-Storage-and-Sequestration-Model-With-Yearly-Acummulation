#!/usr/bin/env python3
"""
Sequential runner:
  - periode 2009→2024
  - periode 2024→2044
"""
import os
import sys
# agar modul carbon_storage_custom.py bisa di-impor
sys.path.append(os.path.dirname(__file__))

from carbon_storage_custom import execute

def run_period(bas, alt, lulc_b, lulc_a, pools_csv, ws_root):
    ws = os.path.join(ws_root, f"{bas}_{alt}")
    os.makedirs(ws, exist_ok=True)
    args = {
        'workspace_dir':     ws,
        'lulc_bas_path':     lulc_b,
        'lulc_alt_path':     lulc_a,
        'carbon_pools_path': pools_csv,
        'lulc_bas_year':     bas,
        'lulc_alt_year':     alt,
    }
    print(f"\n=== Running period {bas}→{alt} ===")
    execute(args)

if __name__ == '__main__':
    project_root = os.path.dirname(os.path.dirname(__file__))
    data_dir     = os.path.join(project_root, 'data')
    pools_csv    = os.path.join(data_dir, 'carbon_pools.csv')

    periods = [
        (2009, 2024,
            os.path.join(data_dir, 'lulc_2009.tif'),
            os.path.join(data_dir, 'lulc_2024.tif')),
        (2024, 2044,
            os.path.join(data_dir, 'lulc_2024.tif'),
            os.path.join(data_dir, 'LULC_2044.tif')),
    ]
    ws_root = os.path.join(project_root, 'workspace')
    for bas, alt, lb, la in periods:
        run_period(bas, alt, lb, la, pools_csv, ws_root)

    print("\n=== Semua periode selesai ===")
