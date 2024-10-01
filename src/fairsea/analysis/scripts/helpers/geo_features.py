from typing import List

import geopandas as gpd
import numpy as np
import pandas as pd

from .feature_engineering import log_pipeline


def _apply_single_zone(dataf: gpd.GeoDataFrame, zone_df: gpd.GeoDataFrame, 
                       zone_column: str='EEZ_Type', zone_name: str='Internal Waters') -> gpd.GeoDataFrame:
    """Label datapoints with the zone they are in.

    Args:
        dataf (gpd.GeoDataFrame): original dataframe
        zone_df (gpd.GeoDataFrame): dataframe containing zone information
        zone_column (str, optional): column name containing zone information. Defaults to 'EEZ_Type'.
        zone_name (str, optional): The name of the zone that is being labeled. Defaults to 'Internal Waters'.

    Returns:
        gpd.DataFrame: dataframe with zone labels
    """
    slice_df = dataf.loc[dataf[zone_column].isnull()]

    slice_geo = zone_df.loc[zone_df[zone_column]==zone_name, :]

    slice_df.loc[:, zone_column] = gpd.sjoin(
        slice_df,
        slice_geo,
        how='left',
        predicate='within'
    ).loc[:, f'{zone_column}_right']

    dataf.loc[dataf[zone_column].isnull(), zone_column] = slice_df[zone_column]

    return dataf


@log_pipeline
def apply_zones(dataf: gpd.GeoDataFrame, zone_df: gpd.GeoDataFrame, zone_column: str='EEZ_Type') -> gpd.GeoDataFrame:
    """Label the datapoints with the zone they are in.

    Args:
        dataf (gpd.GeoDataFrame): original dataframe
        zone_df (gpd.GeoDataFrame): dataframe containing zone information
        zone_column (str, optional): column containing zone names. Defaults to 'EEZ_Type'.

    Returns:
        gpd.GeoDataFrame: datapoints labeled with applicable zones
    """
    # Insert empty column to store the zone information
    dataf[zone_column] = None
        
    # Names of the zones, in order of increasing size
    # The order is important, as each zone is a superset of the previous one
    zones = ['Internal Waters', 'Territorial Sea (12NM)', 'Contiguous Sea (24NM)', 'EEZ (200NM)']
    for zone in zones:
        dataf = _apply_single_zone(dataf, zone_df, zone_column=zone_column, zone_name=zone)

    return dataf


@log_pipeline
def apply_territory(dataf: gpd.GeoDataFrame, territory_df: gpd.GeoDataFrame, 
                    territory_column: str='TERRITORY1', new_column_name: str='EEZ_Territory') -> gpd.GeoDataFrame:
    """Label the datapoints by the country they are in.

    Args:
        dataf (gpd.GeoDataFrame): original dataframe with the datapoints
        territory_df (gpd.GeoDataFrame): dataframe with territory information
        territory_column (str, optional): column name containing territory names. Defaults to 'TERRITORY1'.
        new_column_name (str, optional): territory column name in the output. Defaults to 'EEZ_Territory'.

    Returns:
        gpd.GeoDataFrame: datapoints with country labels
    """
    dataf.loc[:, new_column_name] = gpd.sjoin(dataf, territory_df, how='left', predicate='within')[territory_column]
    return dataf


@log_pipeline
def add_density_map(dataf: gpd.GeoDataFrame, density_df: gpd.GeoDataFrame, density_name: str, null_filter_col: str='EEZ_Type'):
    """Add density numbers to each datapoint.

    This is a measure of the number of ship movements through that square kilometer per year.

    Args:
        dataf: 
        density_df: 
        density_name: 
        null_filter_col: 

    Returns:
        
    """
    # create an empty column
    dataf[density_name] = np.nan

    row_selection = dataf[null_filter_col].notnull()

    # use the Swedish coordinate system (https://epsg.io/3006)
    swedish_ref = 3006
    df_nearest = gpd.sjoin_nearest(
        dataf.to_crs(epsg=swedish_ref)[row_selection],
        density_df.to_crs(epsg=swedish_ref),
        how='left'
    )

    # Sometimes there are two density points that are identically close to the datapoint
    duplicated_rows = df_nearest.index.duplicated(keep='first')

    dataf.loc[row_selection, density_name] = df_nearest.loc[~duplicated_rows, f'{density_name}_right']

    return dataf

def _voyage_per_ship(dataf: gpd.GeoDataFrame, still_column:str='nav_status_still', eez_type: str='EEZ_Type',
                     still_status: List[str]=['Moored', 'Anchor'], temp_voyage:str='voyage_temp',
                     timestamp: str='Timestamp_datetime'
                     ):
    """Compute the different voyages for a ship.

    A new voyage is started when one of these conditions has been met:
        1. the ship is anchored or moored
        2. the ship has left the bounding box
        3. There is more than a full day between 2 datapoints.

    Args:
        dataf: 
        still_column: 
        eez_type: 
        still_status: 
        temp_voyage: 
        timestamp: 

    Returns:
        
    """
    dataf = dataf.sort_values(timestamp)
    
    dataf[temp_voyage] = 0
    mask = (
        # For when the ship is moored/anchored
        (dataf[still_column].shift(1).astype(bool) & ~dataf[still_column].astype(bool))
        # when the ship is leaving/entering the bounding box
        | (dataf[eez_type].shift(1).isnull() ^ dataf[eez_type].isnull())
        # When there is more than 1 day between timestamps
        | (dataf[timestamp] - dataf[timestamp].shift(1) > pd.Timedelta(days=1))
    )

    dataf.loc[mask, temp_voyage] = 1
    dataf[temp_voyage] = dataf[temp_voyage].cumsum()

    return dataf


@log_pipeline
def compute_voyages(dataf: gpd.GeoDataFrame, nav_column: str='Navigational status (text)', ship_column: str='IMO',
                    timestamp: str='dt', voyage_id: str='voyage_id', eez_type='EEZ_Type',
                    still_status: List[str]=['Moored', 'Anchor']) -> gpd.GeoDataFrame:
    """Group the data points into voyages.

    Args:
        eez_type (): 
        dataf: 
        nav_column: 
        ship_column: 
        timestamp: 
        voyage_id: 
        still_status: 

    Returns:
        
    """
    temp_voyage = 'voyage_temp'
    still_column = 'nav_status_still'

    dataf = dataf.sort_values(by=[ship_column, timestamp])
    dataf[still_column] = dataf[nav_column].isin(still_status)
    dataf = dataf.groupby(ship_column, group_keys=False).apply(_voyage_per_ship)

    dataf[voyage_id] = dataf[ship_column] + '_' + dataf[temp_voyage].astype(str)

    return dataf.drop(columns=still_column)


@log_pipeline
def make_geodf(dataf: pd.DataFrame, longitude: str='Longitude', latitude: str='Latitude', crs: int=4326) -> gpd.GeoDataFrame:
    """Turn a DataFrame into a GeoDataFrame

    Args:
        dataf: 
        longitude: 
        latitude: 
        crs: 

    Returns:
        
    """
    return gpd.GeoDataFrame(
        dataf,
        geometry=gpd.points_from_xy(
            dataf[longitude],
            dataf[latitude]
        ),
        crs=crs
    )


@log_pipeline
def filter_bounding_box(dataf: gpd.GeoDataFrame, bbox) -> gpd.GeoDataFrame:
    """Filter a GeoDataFrame by a bounding box.

    This means removing all the points that are outside the bounding box.

    Args:
        bbox (): 
        dataf: 

    Returns:
        
    """
    return gpd.clip(dataf, mask=bbox)
