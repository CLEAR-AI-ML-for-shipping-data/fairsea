import pandas as pd
import pickle
from pathlib import Path
from plotting_functions import make_map

datapath = Path("../output/")


def get_selected_voyages(
    voyage_file: str = "reduced_data_20230927_1438.pkl",
    voyage: str = "voyage_id",
    filter_column: str = "mahalanobis",
    threshold_value=None,
    fraction=None,
) -> pd.DataFrame:
    """Select voyages based on a variable exceeding a threshold.

    Args:
        voyage_file: filename containing pickled voyages
        voyage: column name containing the voyage ID's
        filter_column: column name on which to filter
        threshold_value (): threshold value (optional)
        fraction (): (optional), fraction at which to put the threshold

    Returns: pd.DataFrame

    """
    with open(datapath / voyage_file, "rb") as file:
        dataframe = pickle.load(file)
    max_df = dataframe.groupby(voyage).agg({filter_column: "max"})
    if threshold_value is None:
        threshold_value = max_df[filter_column].quantile(fraction)
    max_df = list(max_df[max_df[filter_column] >= threshold_value].index)

    selected_voyages = dataframe[dataframe[voyage].isin(max_df)]
    return selected_voyages


def get_pollution_events():
    """Get data bout pollution events in 2018.

    Returns: pd.DataFrame

    """
    pollution_data = pd.read_csv(
        "../../data/pollution-obs-2018.csv", sep=";", header=None
    ).rename(
        columns={
            0: "date",
            1: "time",
            2: "lat",
            3: "lon",
        }
    )
    pollution_data["datetime"] = pd.to_datetime(
        pollution_data.apply(lambda x: f"{x['date']} {x['time']}", axis=1)
    )
    return pollution_data


def _map_voyages_pollution(
    pollution_timestamp,
    voyage_data,
    voyage="voyage_id",
    timestamp_column="Timestamp_datetime",
):
    """Select voyages that overlap with a pollution event.

    Args:
        pollution_timestamp (): timestamp of the pollution events
        voyage_data (): dataframe with all voyage data points
        voyage (): column name of containing voyage ID's
        timestamp_column (): column name containing data timestamps

    Returns:

    """
    agg_functions = {
        "min_time": pd.NamedAgg(column=timestamp_column, aggfunc="min"),
        "max_time": pd.NamedAgg(column=timestamp_column, aggfunc="max"),
    }
    filters = voyage_data.groupby(voyage).agg(**agg_functions)
    overlapping_voyages = filters[
        (filters["min_time"] <= pollution_timestamp)
        & (filters["max_time"] >= pollution_timestamp)
    ]
    return overlapping_voyages


def map_pollution(pollution_events, voyage_data):
    """Create maps of pollution events and voyages that happened  at the same time.

    Args:
        pollution_events (): table of pollution events
        voyage_data (): table with data points of all voyages
    """
    for i in range(pollution_events.shape[0]):
        row = pollution_events.iloc[i]
        timestamp = row["datetime"]
        location = (row["lat"], row["lon"])
        overlapping_voyages = _map_voyages_pollution(timestamp, voyage_data)
        print(timestamp)
        print(overlapping_voyages.shape[0], " overlapping voyages")
        print("- - - - - -\n")
        make_map(
            voyage_data,
            plot_column="mahalanobis",
            plot_list=overlapping_voyages.index,
            save_folder="../output/",
            prefix=f"{i:02d}_",
            xy_marker=location,
            colors=True,
        )
        i += 1


if __name__ == "__main__":
    pollution = get_pollution_events()
    voyages = get_selected_voyages(fraction=0.95)
    map_pollution(pollution, voyages)
