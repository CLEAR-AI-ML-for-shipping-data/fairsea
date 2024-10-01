"""Functions for feature engineering.

The functions are designed to be used with the .pipe method of pandas
DataFrames. This allows for method chaining in the following manner:
```python
feature_df = (df
    .pipe(func0, *args0, **kwargs0)
    .pipe(func1, *args1, **kwargs1)
)
```
"""

from os import times
import re
from functools import wraps
from time import perf_counter
from typing import Callable, List, Union
from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.covariance import EmpiricalCovariance
from .utilities import gps_distance_meters, heading


def log_pipeline(func: Callable):
    """A logging decorator for pandas.Dataframe pipe functions

    :param func: the function to be decorated
    :type func: Callable
    """

    @wraps(func)
    def wrapper(dataf: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
        """Wrapper function to log timing and new DataFrame dimensions

        :param dataf: input dataframe
        :type dataf: pd.DataFrame
        :return: modified dataframe
        :rtype: pd.DataFrame
        """
        t0 = perf_counter()
        dataf = func(dataf, *args, **kwargs)
        t1 = perf_counter()
        # print(f'Applied {func.__name__:25s} in {(t1 - t0)*1000:6.0f} ms, new shape is {dataf.shape}')
        return dataf

    return wrapper


@log_pipeline
def start_pipeline(dataf: pd.DataFrame) -> pd.DataFrame:
    """Start pipeline by making a copy of the dataframe

    :param dataf: input dataframe
    :type dataf: pd.DataFrame
    :return: copy of the dataframe
    :rtype: pd.DataFrame
    """
    return dataf.copy()


@log_pipeline
def remove_doubles(
    dataf: pd.DataFrame, subset: Union[str, List[str]] = None
) -> pd.DataFrame:
    """Remove duplicate rows from the dataframe

    :param dataf: input dataframe
    :type dataf: pd.DataFrame
    :return: de-duplicated dataframe
    :rtype: pd.DataFrame
    """
    return dataf.drop_duplicates(subset=subset)


@log_pipeline
def select_columns(dataf: pd.DataFrame, columns: Union[str, List[str]]) -> pd.DataFrame:
    """Select columns from the dataframe.

    :param dataf: input dataframe
    :type dataf: pd.DataFrame
    :param columns: column(s) to select from the dataframe
    :type columns: Union[str, List[str]]
    :return: dataframe with only selected columns
    :rtype: pd.DataFrame
    """
    return dataf[columns]


@log_pipeline
def make_datetime(
    dataf: pd.DataFrame, column: Union[str, List[str]], format: str = None
) -> pd.DataFrame:
    """Convert columns to datetime.

    :param dataf: Input dataframe
    :type dataf: pd.DataFrame
    :param column: column(s) to be converted
    :type column: Union[str, List[str]]
    :return: new dataframe
    :rtype: pd.DataFrame
    """
    dataf[column] = pd.to_datetime(dataf[column], format=format)
    return dataf


@log_pipeline
def create_moving_agg_time(
    dataf: pd.DataFrame,
    voyage_id: str,
    timestamp: str,
    sum_column: Union[str, List[str]],
    agg: str = "sum",
    hours: int = 0,
    minutes: int = 0,
) -> pd.DataFrame:
    """Create the sum of a column over a rolling time window, per voyage.

    Window width can be given as a combination of hours and minutes.

    :param dataf: input dataframe
    :type dataf: pd.DataFrame
    :param voyage_id: name of the voyage_id column
    :type voyage_id: str
    :param timestamp: name of the timestamp column
    :type timestamp: str
    :param sum_column: column name(s) over which to sum
    :type sum_column: Union[str, List[str]]
    :param agg: aggregate function, choose from sum, mean, median, std, var, prod
    :type agg: str
    :param hours: number of hours in the window, defaults to 0
    :type hours: int, optional
    :param minutes: number of minutes in the window, defaults to 0
    :type minutes: int, optional
    :return: data with the moving summed columns
    :rtype: pd.DataFrame
    """

    # convert minutes > 60 to hours
    hours += minutes // 60
    minutes %= 60

    if isinstance(sum_column, str):
        # convert the string to a list,
        # to ensure DataFrame is not converted to Series
        sum_column = [sum_column]

    agg_functions = {col: agg for col in sum_column}

    sum_df = dataf.groupby(voyage_id).apply(
        lambda x: (
            x.sort_values(timestamp)[sum_column + [timestamp]]
            .rolling(pd.Timedelta(hours=hours, minutes=minutes), on=timestamp, min_periods=hours*2)
            .agg(agg_functions)
            .fillna(0)
        )
    )

    new_col_names = {
        col: f"{col}_{agg}_{int(hours or 0):d}_{int(minutes or 0):02d}"
        for col in sum_column
    }

    # We rename the columns, and drop the voyage_id from the row_index, so that
    # we can merge on index alone.
    sum_df = sum_df.rename(columns=new_col_names).droplevel(voyage_id)

    dataf = dataf.join(sum_df, how="inner")
    return dataf


def _distance_travelled_single_group(
    dataf: pd.DataFrame,
    distance_col: str = "Distance_Diff_Meters",
    territory_column: str = "EEZ_Territory",
    latitude_col: str = "Latitude",
    longitude_col: str = "Longitude",
    travel_distance_col: str = "Travelled_Distance",
    absol_distance_col: str = "Absolute_Distance",
    timestamp: str = "dt",
):
    """Calculate the travelled distance, on a per-voyage basis.

    Args:
        dataf: original dataframe
        distance_col: column name containing the distance between 2 subsequent data points
        territory_column: column containing the name of the territory
        latitude_col: latitude column
        longitude_col: longitude column
        travel_distance_col: column to put the travelled distance
        absol_distance_col: column to put the absolute distance
        timestamp: timestamp column

    Returns:

    """
    # Create new columns for the new data

    crossing_latitude_column = f"Crossing_{latitude_col}"
    crossing_longitude_column = f"Crossing_{longitude_col}"

    dataf = dataf.assign(
        **{
            travel_distance_col: np.nan,
            absol_distance_col: np.nan,
            crossing_latitude_column: np.nan,
            crossing_longitude_column: np.nan,
            "sneak_ratio": np.nan,
        }
    )

    dataf = dataf.sort_values(timestamp)

    # Get the crossings of borders between territories
    border_crossing_regex = re.compile(r"10+1")
    df_territory_dummies = pd.get_dummies(dataf[territory_column])
    # Make sure it is not an empty series
    if len(df_territory_dummies.columns) > 0:
        for col in df_territory_dummies.columns:
            # Cast the series to a single string of 1s and 0s
            # perform regex search to find the transitions
            binary_sequence = (
                df_territory_dummies[col].astype(int).astype(str).str.cat()
            )
            for r in border_crossing_regex.finditer(binary_sequence):
                idx = r.span()
                first_moment, last_moment = idx
                dataf.loc[
                    dataf.iloc[idx[1] - 1].name, absol_distance_col
                ] = gps_distance_meters(
                    dataf.iloc[idx[0]][latitude_col],
                    dataf.iloc[idx[0]][longitude_col],
                    dataf.iloc[idx[1] - 1][latitude_col],
                    dataf.iloc[idx[1] - 1][longitude_col],
                )

                df_slice = dataf.loc[
                    dataf.iloc[first_moment].name : dataf.iloc[last_moment - 1].name
                ]

                first_name, last_name = df_slice.iloc[0].name, df_slice.iloc[-1].name

                # Calculate the distance to the last bordercrossing
                df_slice.loc[:, crossing_latitude_column] = df_slice.loc[
                    first_name, latitude_col
                ]
                df_slice.loc[:, crossing_longitude_column] = df_slice.loc[
                    first_name, longitude_col
                ]

                df_slice.loc[:, absol_distance_col] = df_slice.apply(
                    lambda x: gps_distance_meters(
                        x[latitude_col],
                        x[longitude_col],
                        x[crossing_latitude_column],
                        x[crossing_longitude_column],
                    ),
                    axis=1,
                )

                # Start integrating the travelled distance since the last border-crossing
                df_slice.loc[:, travel_distance_col] = df_slice[distance_col].cumsum()
                df_slice.loc[:, "sneak_ratio"] = (
                    df_slice[travel_distance_col] / df_slice[absol_distance_col]
                ).replace(np.inf, 0)

                # Insert slice back into dataframe
                dataf.loc[
                    dataf.iloc[first_moment].name : dataf.iloc[last_moment - 1].name
                ] = df_slice

    return dataf


@log_pipeline
def distance_travelled(
    dataf: pd.DataFrame,
    voyage_id: str,
    latitude_col: str = "Latitude",
    longitude_col: str = "Longitude",
    distance_col="Distance_Diff_Meters",
    **kwargs,
):
    """Calculate distance travelled since a territory crossing.

    This function calculates both absolute distance and pathlength.

    :param dataf: input dataframe
    :type dataf: pd.DataFrame
    :param voyage_id: column name that contains different voyage_ids
    :type voyage_id: str
    :param latitude_col: name of latitude column, defaults to 'Latitude'
    :type latitude_col: str, optional
    :param longitude_col: name of longitude column, defaults to 'Longitude'
    :type longitude_col: str, optional
    :param distance_col: column containing distance to previous datapoint, defaults to 'Distance_Diff_Meters'
    :type distance_col: str, optional
    :return: dataframe with calculated columns
    :rtype: pd.DataFrame
    """
    return (
        dataf.groupby(voyage_id)
        .apply(
            _distance_travelled_single_group,
            latitude_col=latitude_col,
            longitude_col=longitude_col,
            distance_col=distance_col,
            **kwargs,
        )
        .droplevel(voyage_id)
    )


@log_pipeline
def loitering_ratio_timewindow(
    dataf: pd.DataFrame,
    voyage_id,
    latitude_col: str = "Latitude",
    longitude_col: str = "Longitude",
    distance_col: str = "Distance_Diff_Km",
    timestamp: str = "dt",
    hours: int = 0,
    minutes: int = 0,
) -> pd.DataFrame:
    """Calculate the loitering ratio over a given time window.

    The loitering ratio is the ratio of (travelled distance) / (absolute distance)
    over a given time window, as a function of time.
    I.e. at any time T, we divide the distance the ship has travelled (pathlength)
    between (T - window) and T, and the actual dislocation that has taken place
    in the same timeframe.

    Args:
        voyage_id ():
        dataf:
        latitude_col:
        longitude_col:
        distance_col:
        timestamp:
        hours:
        minutes:

    Returns:

    """
    agg_functions = {
        latitude_col: lambda rows: rows.iloc[0],
        longitude_col: lambda rows: rows.iloc[0],
        distance_col: "sum",
    }

    new_suffix = f"{int(hours or 0):d}_{int(minutes or 0):02d}"
    new_column_names = {
        col: f"{col}_{new_suffix}"
        for col in [latitude_col, longitude_col, distance_col]
    }

    # Calculate the GPS-point at the beginning of the window, and the integrated distance since then
    rolling_df = (
        dataf.groupby(voyage_id)
        .apply(
            lambda x: (
                x.sort_values(timestamp)[
                    [timestamp, latitude_col, longitude_col, distance_col]
                ]
                .rolling(pd.Timedelta(hours=hours, minutes=minutes), on=timestamp, min_periods=hours*2)
                .agg(agg_functions)
                .rename(columns=new_column_names)
            )
        )
        .droplevel(voyage_id)
    )

    dataf = dataf.join(rolling_df, how="inner")

    # Calculate the direct distance between the current datapoint, and the one from the beginning of the window
    dataf[f"location_shift_{new_suffix}"] = dataf.apply(
        lambda x: gps_distance_meters(
            x[latitude_col],
            x[longitude_col],
            x[f"{latitude_col}_{new_suffix}"],
            x[f"{longitude_col}_{new_suffix}"],
        )
        # / 1000
        ,
        axis=1,
    )

    # Calculate the ratio.
    # Cast the numerator to np.float64, to only get warnings when dividing by 0
    dataf[f"{distance_col}_{new_suffix}"] = dataf[
        f"{distance_col}_{new_suffix}"
    ].astype(np.float64)

    dataf[f"loitering_ratio_{new_suffix}"] = np.divide(
        dataf[f"{distance_col}_{new_suffix}"], dataf[f"location_shift_{new_suffix}"]
    )

    return dataf


@log_pipeline
def filter_column_values(
    dataf: pd.DataFrame, column: str, values: Iterable, inverse: bool = False
):
    """Filter out rows by the values of a certain column.

    Selects the rows where the value of <column> is in <values>.
    If inverse is True, it selects the rows where the value of <column> is not in <values>.

    Args:
        dataf:
        column:
        values:
        inverse:

    Returns:

    """
    if inverse:
        return dataf[~dataf[column].isin(values)]
    else:
        return dataf[dataf[column].isin(values)]


@log_pipeline
def sort_values(dataf: pd.DataFrame, columns: Union[str, List[str]]) -> pd.DataFrame:
    """Sort dataframe by values in one or more columns.

    Args:
        dataf:
        columns:

    Returns:

    """
    return dataf.sort_values(columns)


def _distance_diff_meters(
    dataf: pd.DataFrame,
    distance_col: str,
    latitude_col: str = "Latitude",
    longitude_col: str = "Longitude",
) -> pd.DataFrame:
    """Calculate the distance between a datapoint and its previous point.

    Args:
        dataf:
        distance_col:
        latitude_col:
        longitude_col:

    Returns:

    """
    dataf[distance_col] = gps_distance_meters(
        dataf[latitude_col].shift(1),
        dataf[longitude_col].shift(1),
        dataf[latitude_col],
        dataf[longitude_col],
    )
    return dataf


@log_pipeline
def distance_diff_meters(
    dataf: pd.DataFrame,
    distance_col: str,
    voyage_id: str = "voyage_id",
    latitude_col: str = "Latitude",
    longitude_col: str = "Longitude",
) -> pd.DataFrame:
    """Calculate the distance between subsequent datapoints.

    This is done on a per-voyage basis, so as to not calculate the distance between
    two points belonging to different voyages.

    Args:
        dataf:
        distance_col:
        voyage_id:
        latitude_col:
        longitude_col:

    Returns:

    """
    # do it per voyage, to never get the distance to a previous voyage
    return (
        dataf.groupby(voyage_id)
        .apply(
            _distance_diff_meters,
            distance_col=distance_col,
            latitude_col=latitude_col,
            longitude_col=longitude_col,
        )
        .droplevel(voyage_id)
    )


def _make_heading(
    dataf: pd.DataFrame,
    heading_col: str = "heading",
    latitude_col: str = "Latitude",
    longitude_col: str = "Longitude",
) -> pd.DataFrame:
    dataf[heading_col] = heading(
        dataf[latitude_col].shift(1),
        dataf[longitude_col].shift(1),
        dataf[latitude_col],
        dataf[longitude_col],
    )
    return dataf


@log_pipeline
def make_heading(
    dataf: pd.DataFrame,
    heading_col: str = "heading",
    voyage_id: str = "voyage_id",
    latitude_col: str = "Latitude",
    longitude_col: str = "Longitude",
    filter: float = 0.0,
) -> pd.DataFrame:
    """Calculate difference in heading between two data points.

    This is done on a per-voyage basis, so as to not calculate the difference between
    two points belonging to different voyages.

    Args:
        dataf:
        heading_col:
        voyage_id:
        latitude_col:
        longitude_col:
        filter:

    Returns:

    """
    dataf = (
        dataf.groupby(voyage_id)
        .apply(
            _make_heading,
            heading_col=heading_col,
            latitude_col=latitude_col,
            longitude_col=longitude_col,
        )
        .droplevel(voyage_id)
    )

    dataf[f"{heading_col}_abs_diff"] = np.abs(
        dataf[heading_col] - dataf[heading_col].shift(1)
    )
    # We can cap the difference in heading, so as to not highlight extreme
    # manoeuvering inside of harbours.
    if filter:
        dataf.loc[
            dataf[f"{heading_col}_abs_diff"] > filter, f"{heading_col}_abs_diff"
        ] = 0.0
    return dataf


@log_pipeline
def get_mahalanobis(dataf: pd.DataFrame, columns: Union[str, List[str]]):
    """Get the mahalanobis distance of each datapoint, based on one or more columns.

    This helps determining how much of an outlier a certain point is.

    Args:
        dataf: the input dataframe
        columns: columns over which to get

    Returns:

    """
    cov = EmpiricalCovariance()
    maha_df = dataf[columns].copy()
    maha_df = maha_df.replace({np.inf: 0, np.nan: 0})
    cov.fit(maha_df)

    dataf = dataf.assign(mahalanobis=cov.mahalanobis(maha_df))
    return dataf


def flag_time_gap(
    dataf: pd.DataFrame, minutes: int = 30, timestamp="Timestamp_datetime"
):
    temp_col = f"temp_{timestamp}_1"
    dataf[temp_col] = dataf[timestamp].shift(1)
    dataf["timegap"] = (
        (dataf[timestamp] - dataf[temp_col]) > pd.Timedelta(minutes=minutes)
    ).astype(int)
    return dataf.drop(columns=temp_col)


@log_pipeline
def time_gap(
    dataf: pd.DataFrame,
    minutes: int = 30,
    timestamp="Timestamp_datetime",
    voyage_id="voyage_id",
):
    return dataf.groupby(voyage_id, as_index=False).apply(
        flag_time_gap, minutes, timestamp
    )
