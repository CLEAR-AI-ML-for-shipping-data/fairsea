import datetime as dt
import os
import pickle
from pathlib import Path
from time import perf_counter

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

from .helpers import geo_features as gf
from .helpers import feature_engineering as fe
from .settings import Settings

os.environ["USE_PYGEOS"] = "0"
tqdm.pandas()


# ----------------------#
# Function definitions #
# ----------------------#


def create_zone_dfs(settings: Settings):
    """Create zones for the zones and territories.

    Returns:

    """
    # Read and process EEZ polygons
    df_eez_internal = gpd.read_file(settings.eez_files.internal)
    df_eez_12nm = gpd.read_file(settings.eez_files.territorial)
    df_eez_24nm = gpd.read_file(settings.eez_files.contiguous)
    df_eez_200nm = gpd.read_file(settings.eez_files.eez)

    # Filter by bounding box.
    bbox = settings.get_bbox()
    # bbox_edge will be used to pre-clip the data, to reduce the size of the dataframe
    df_eez_internal = gpd.clip(df_eez_internal, mask=bbox)
    df_eez_12nm = gpd.clip(df_eez_12nm, mask=bbox)
    df_eez_24nm = gpd.clip(df_eez_24nm, mask=bbox)
    df_eez_200nm = gpd.clip(df_eez_200nm, mask=bbox)

    # Read into GeoDataFrame
    df_eez = gpd.GeoDataFrame(
        data={
            "EEZ_Type": [
                "EEZ (200NM)",
                "Contiguous Sea (24NM)",
                "Territorial Sea (12NM)",
                "Internal Waters",
            ],
            "geometry": [
                df_eez_200nm["geometry"].unary_union,
                df_eez_24nm["geometry"].unary_union,
                df_eez_12nm["geometry"].unary_union,
                df_eez_internal["geometry"].unary_union,
            ],
        },
        crs="EPSG:4326",
    )

    df_eez_territory = pd.concat((df_eez_internal, df_eez_12nm))[
        ["TERRITORY1", "geometry"]
    ]

    return df_eez, df_eez_territory


def create_chemical_filter(settings: Settings):
    """Produce the list of IMOs that belong to chemical tankers.

    Returns:

    """
    # Read list of IMOs to filter certain ships that we are interested in.
    df_filter_imos = pd.read_csv(settings.meta_data_path)

    df_filter_imos["imo_chemical"] = (
        df_filter_imos["imo_chemical"].astype(int).astype(str)
    )
    return df_filter_imos


def read_ais_data(settings: Settings):
    """Read data with all the AIS data points.

    Returns:

    """
    print("Reading.")
    # Reading AIS data for Chemical Tankers.
    df = pd.read_csv(settings.ais_data_path)

    df[["MMSI", "IMO"]] = df[["MMSI", "IMO"]].astype(int).astype(str)
    return df


def pipeline(
    dataf: pd.DataFrame,
    df_eez: gpd.GeoDataFrame,
    df_eez_territory: gpd.GeoDataFrame,
    settings: Settings,
) -> pd.DataFrame:
    """Define the pipeline that is applied to the full dataset.

    This pipeline can be applied on a per-IMO basis.

    Args:
        dataf: dataset with AIS data points
        df_eez: the different nautical zones
        df_eez_territory: the different territories

    Returns:

    """
    timestamp = "Timestamp_datetime"
    voyage_id = "voyage_id"
    distance_col = "Distance_Diff_m"
    heading_col = "Heading"
    hours = 4
    minutes = 0

    logwidth = 72
    filler = "-"

    t0 = perf_counter()
    ship_id = dataf["IMO"].iloc[0]
    lines = dataf.shape[0]

    # TODO make this proper, optional, logging
    # print(
    #     f"#{'' :{filler}<{logwidth}}#\n#{f'Processing ship IMO {ship_id} with {lines:,} lines':^{logwidth}}#\n#{'' :{filler}<{logwidth}}#"
    # )
    bbox_edge = settings.get_bbox(edge=2.0)
    bbox = settings.get_bbox()
    rdf = dataf.pipe(gf.make_geodf).pipe(gf.filter_bounding_box, bbox=bbox_edge)
    # filtering by bounding box might return an empty dataframe
    if rdf.shape[0] > 0:
        rdf = (
            rdf.pipe(gf.apply_zones, df_eez)
            .pipe(gf.apply_territory, df_eez_territory)
            .pipe(fe.make_datetime, timestamp, format="%Y-%m-%d %H:%M:%S")
            .pipe(gf.compute_voyages, timestamp=timestamp)
            .pipe(
                fe.filter_column_values,
                "Navigational status (text)",
                ["Moored", "Anchor"],
                inverse=True,
            )
            .pipe(gf.filter_bounding_box, bbox=bbox)
        )

    # filtering by bounding box might return an empty dataframe
    if rdf.shape[0] > 0:
        rdf = (
            rdf.pipe(fe.remove_doubles, subset=[voyage_id, timestamp])
            .pipe(fe.sort_values, [voyage_id, timestamp])
            .pipe(fe.distance_diff_meters, distance_col)
            .pipe(fe.make_heading, heading_col, filter=7.0)
            .pipe(
                fe.distance_travelled,
                voyage_id,
                distance_col=distance_col,
                timestamp=timestamp,
            )
            .pipe(
                fe.create_moving_agg_time,
                voyage_id,
                timestamp,
                [distance_col, f"{heading_col}_abs_diff"],
                hours=hours,
                minutes=minutes,
                agg="sum",
            )
            .pipe(
                fe.loitering_ratio_timewindow,
                voyage_id,
                distance_col=distance_col,
                timestamp=timestamp,
                hours=hours,
                minutes=minutes,
            )
            .pipe(
                fe.create_moving_agg_time,
                voyage_id,
                timestamp,
                [distance_col, f"{heading_col}_abs_diff"],
                hours=2,
                minutes=minutes,
                agg="sum",
            )
            .pipe(
                fe.loitering_ratio_timewindow,
                voyage_id,
                distance_col=distance_col,
                timestamp=timestamp,
                hours=2,
                minutes=minutes,
            )
            .pipe(
                fe.loitering_ratio_timewindow,
                voyage_id,
                distance_col=distance_col,
                timestamp=timestamp,
                hours=8,
                minutes=minutes,
            )
            .pipe(
                fe.get_mahalanobis,
                columns=[
                    f"{heading_col}_abs_diff_sum_2_00",
                    "loitering_ratio_2_00",
                    f"{heading_col}_abs_diff_sum_4_00",
                    "loitering_ratio_4_00",
                ],
            )
            .pipe(fe.time_gap, minutes=30, voyage_id=voyage_id, timestamp=timestamp)
        )

    t1 = perf_counter()
    # print(f">>> Processing speed: {int((lines)/(t1 - t0)):,} lines / sec\n\n")
    if not rdf.empty:
        return rdf


def main(settings: Settings = Settings()):
    df_features = read_ais_data(settings)
    imos_filter = create_chemical_filter(settings)

    df_eez, df_eez_territory = create_zone_dfs(settings)

    # Do filter out the ships that are not chemical tankers
    df_features = df_features.pipe(
        fe.filter_column_values, "IMO", imos_filter["imo_chemical"]
    )

    df_features = df_features.groupby("IMO").progress_apply(
        pipeline, df_eez=df_eez, df_eez_territory=df_eez_territory, settings=settings
    )

    settings.write_data(df_features, "voyages")

    print(f"Output written to {settings.voyages_filename} in output folder")
    return df_features


if __name__ == "__main__":
    output = main()
