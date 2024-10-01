import json
from pathlib import Path
import pickle
import sys
from typing import Union, Dict

import numpy as np
import pandas as pd

from .settings import Settings

# sys.path.append("../../visualisation/abnormalTrajectoriesMap")

import src.fairsea.visualisation.abnormalTrajectoriesMap.atMap as atMap 
from src.fairsea.visualisation.abnormalTrajectoriesMap.atMap import ATMap


visualisation_cols = [
    "loitering_ratio_2_00",
    "loitering_ratio_4_00",
    "loitering_ratio_8_00",
    "sneak_ratio",
]

column_labels = {
    "loitering_ratio_2_00": "LotRat2",
    "loitering_ratio_4_00": "LotRat4",
    "loitering_ratio_8_00": "LotRat8",
    "sneak_ratio": "SneakRat",
}


class GeneralMap(ATMap):
    @classmethod
    def init_map(cls, settings: Settings, *args, **kwargs):
        tmp_iw_path = atMap.EEZ_IW_PATH
        tmp_12_path = atMap.EEZ_12NM_PATH
        tmp_24_path = atMap.EEZ_24NM_PATH
        tm_200_path = atMap.EEZ_200NM_PATH
        tmp_bbox = atMap.BOUNDING_BOX

        atMap.EEZ_IW_PATH = settings.eez_files.internal
        atMap.EEZ_12NM_PATH = settings.eez_files.territorial
        atMap.EEZ_24NM_PATH = settings.eez_files.contiguous
        atMap.EEZ_200NM_PATH = settings.eez_files.eez
        atMap.BOUNDING_BOX = settings.bbox

        map = super().init_map(*args, **kwargs)

        # Update the colormap with entries for extra countries

        map.territory_cmap.update(
            {
                "Germany": "#800012",
                "United States": "#800012",
            }
        )

        atMap.EEZ_IW_PATH = tmp_iw_path
        atMap.EEZ_12NM_PATH = tmp_12_path
        atMap.EEZ_24NM_PATH = tmp_24_path
        atMap.EEZ_200NM_PATH = tm_200_path
        atMap.BOUNDING_BOX = tmp_bbox

        return map


def add_layer_to_map(
    map: ATMap,
    df: pd.DataFrame,
    column: str,
    threshold: float,
    c_min: float = 1.0,
    c_max: float = 5.0,
    cmap_name: str = "Spectral_r",
):
    print(f"Adding layer for {column}")
    mask = (
        (df[column] > threshold)
        & (df["EEZ_Type"] != "Internal Waters")
        & (df["EEZ_Type"].notnull())
    )
    voyage = "voyage_id"
    voyage_ids = df.loc[mask, voyage].unique()

    df_tmp = df[df[voyage].isin(voyage_ids)]

    try:
        label = f"Abnormal trajectories {column_labels[column]} > {str(threshold)}"
    except KeyError:
        label = f"Abnormal trajectories {column} > {str(threshold)}"

    map.add_voyages(
        label,
        df_tmp,
        column,
        cmap_name=cmap_name,
        c_min=c_min,
        c_max=c_max,
        render_with_gaps=True,
    )

    return map


def add_monochrome_layer(map: ATMap, df: pd.DataFrame, label: str):
    df = df.assign(dummycolumn=1)
    map.add_voyages(
        label,
        df,
        "dummycolumn",
        cmap_name="coolwarm",
        c_min=0.0,
        c_max=10.0,
        render_with_gaps=True,
    )
    return map


def main(
    settings: Settings,
    df: pd.DataFrame,
    voyage_classes_all: Union[Dict[str, int], None] = None,
):
    # OUTPUT_PATH = Path("../output")
    # reduced_file = "reduced_data_20231027_1434.pkl"
    # reduced_file = "reduced_data_20231004_1125.pkl"
    # cluster_file = "voyage_clustering.json"
    # print(f"Reading {OUTPUT_PATH / reduced_file}...")
    # with open(OUTPUT_PATH / reduced_file, "rb") as file:
    #    df = pickle.load(file)

    # with open(OUTPUT_PATH / cluster_file, "r") as file:
    #    voyage_classes_all = json.load(file)

    for col in visualisation_cols:
        df[col] = df[col].fillna(1.0)
        df[col] = df[col].replace([np.inf, -np.inf], 1.0)

    map = GeneralMap.init_map(settings, territories=True, zones=True)
    map = add_layer_to_map(
        map, df, "loitering_ratio_2_00", threshold=100, c_min=1.0, c_max=5.0
    )
    map = add_layer_to_map(
        map, df, "loitering_ratio_4_00", threshold=100, c_min=1.0, c_max=5.0
    )
    map = add_layer_to_map(
        map, df, "loitering_ratio_8_00", threshold=100, c_min=1.0, c_max=5.0
    )
    map = add_layer_to_map(
        map,
        df,
        "sneak_ratio",
        threshold=20.0,
        c_min=1.0,
        c_max=20.0,
        cmap_name="coolwarm",
    )
    map = add_layer_to_map(
        map, df, "timegap", threshold=0.0, c_min=0.0, c_max=1.0, cmap_name="autumn_r"
    )

    if voyage_classes_all is not None:
        cluster_voyages = [
            voyage for voyage, outlier in voyage_classes_all.items() if outlier == 1
        ]
        df_cluster = df[df["voyage_id"].isin(cluster_voyages)]
        map = add_monochrome_layer(map, df_cluster, "Cluster outlier")

    # map.save("./baltic.html")
    return map


if __name__ == "__main__":
    main()
