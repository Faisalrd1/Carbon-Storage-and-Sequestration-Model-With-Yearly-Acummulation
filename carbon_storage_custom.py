#!/usr/bin/env python3
"""
Modifikasi perhitungan stok & perubahan karbon:
  - baca CSV dengan sep=";"
  - hitung stok baseline & alternate (sum pool)
  - hitung selisih stok statis (alternate – baseline)
  - hitung selisih laju statis (rate_alt – rate_bas)
  - akumulasi selisih laju × (end_year – start_year)
  - net change = selisih stok + akumulasi selisih laju
"""
import os
import logging
import numpy as np
from osgeo import gdal
import pygeoprocessing
import pandas as pd

LOGGER = logging.getLogger(__name__)
default_nodata = -1.0

def execute(args):
    # 1) Direktori kerja
    wd = args.get('workspace_dir')
    if not wd:
        raise KeyError("workspace_dir tidak ditemukan di args")
    os.makedirs(wd, exist_ok=True)
    mid = os.path.join(wd, 'intermediate')
    os.makedirs(mid, exist_ok=True)

    # 2) Baca carbon_pools.csv (delimiter ';')
    csv_p = args.get('carbon_pools_path')
    if not csv_p or not os.path.isfile(csv_p):
        raise KeyError(f"File carbon_pools tidak ada: {csv_p}")
    df = pd.read_csv(csv_p, sep=';')
    # normalisasi header
    df.columns = [c.strip().lower() for c in df.columns]
    if 'lucode' not in df.columns:
        raise KeyError(f"Kolom 'lucode' tidak ditemukan di carbon_pools: {csv_p}")
    df = df.set_index('lucode')

    # 3) Validasi kolom stok & laju
    stok_keys = [k for k in ['c_above','c_below','c_soil','c_dead'] if k in df.columns]
    if not stok_keys:
        raise KeyError("Tidak ada kolom stok (c_above, c_below, c_soil, c_dead)")
    if 'c_sequestration' not in df.columns:
        raise KeyError("Kolom 'c_sequestration' tidak ditemukan")
    stocks    = {k: df[k].to_dict() for k in stok_keys}
    rate_dict = df['c_sequestration'].to_dict()

    # 4) Reclassify stok (baseline & alternate)
    ras_bas, ras_alt = [], []
    for pool, lookup in stocks.items():
        out_b = os.path.join(mid, f"{pool}_bas.tif")
        pygeoprocessing.reclassify_raster(
            (args['lulc_bas_path'], 1), lookup, out_b,
            gdal.GDT_Float32, default_nodata)
        ras_bas.append(out_b)

        out_a = os.path.join(mid, f"{pool}_alt.tif")
        pygeoprocessing.reclassify_raster(
            (args['lulc_alt_path'], 1), lookup, out_a,
            gdal.GDT_Float32, default_nodata)
        ras_alt.append(out_a)

    # 5) Reclassify laju (baseline & alternate)
    rate_b = os.path.join(mid, 'rate_bas.tif')
    pygeoprocessing.reclassify_raster(
        (args['lulc_bas_path'], 1), rate_dict, rate_b,
        gdal.GDT_Float32, default_nodata)
    rate_a = os.path.join(mid, 'rate_alt.tif')
    pygeoprocessing.reclassify_raster(
        (args['lulc_alt_path'], 1), rate_dict, rate_a,
        gdal.GDT_Float32, default_nodata)

    # 6) Hitung stok total statis
    bas_static = os.path.join(wd, 'storage_baseline.tif')
    pygeoprocessing.raster_calculator(
        [(p, 1) for p in ras_bas],
        lambda *arrs: np.where(
            np.any([a == default_nodata for a in arrs], axis=0),
            default_nodata,
            sum(arrs)),
        bas_static, gdal.GDT_Float32, default_nodata)

    alt_static = os.path.join(wd, 'storage_alternate.tif')
    pygeoprocessing.raster_calculator(
        [(p, 1) for p in ras_alt],
        lambda *arrs: np.where(
            np.any([a == default_nodata for a in arrs], axis=0),
            default_nodata,
            sum(arrs)),
        alt_static, gdal.GDT_Float32, default_nodata)

    # 7) Selisih stok statis (alt – bas)
    diff_static = os.path.join(wd, 'change_static.tif')
    pygeoprocessing.raster_map(
        op=lambda b, a: np.where(
            (b == default_nodata)|(a == default_nodata),
            default_nodata,
            a - b),
        rasters=[bas_static, alt_static],
        target_path=diff_static,
        target_nodata=default_nodata)

    # 8) Selisih laju statis (rate_alt – rate_bas)
    diff_rate = os.path.join(wd, 'delta_rate.tif')
    pygeoprocessing.raster_map(
        op=lambda rb, ra: np.where(
            (rb == default_nodata)|(ra == default_nodata),
            default_nodata,
            ra - rb),
        rasters=[rate_b, rate_a],
        target_path=diff_rate,
        target_nodata=default_nodata)

    # 9) Akumulasi selisih laju
    start_y = int(args.get('lulc_bas_year'))
    end_y   = int(args.get('lulc_alt_year'))
    years   = end_y - start_y

    dyn_accum = os.path.join(wd, 'change_accumulated.tif')
    pygeoprocessing.raster_map(
        op=lambda dr: np.where(
            dr == default_nodata,
            default_nodata,
            dr * years),
        rasters=[diff_rate],
        target_path=dyn_accum,
        target_nodata=default_nodata)

    # 10) Net change = selisih stok + akumulasi selisih laju
    net_path = os.path.join(wd, 'change_net.tif')
    pygeoprocessing.raster_map(
        op=lambda ds, da: np.where(
            (ds == default_nodata)|(da == default_nodata),
            default_nodata,
            ds + da),
        rasters=[diff_static, dyn_accum],
        target_path=net_path,
        target_nodata=default_nodata)

    LOGGER.info(f"Periode {start_y}→{end_y} selesai. Net change: {net_path}")
