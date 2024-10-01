from os import link
from pathlib import Path
import json
import pickle

import pandas as pd
import folium
from plotting_functions import make_map

data_folder = Path("../../data/")
reduced_data_folder = Path("../output/")


timestamp_column = "Timestamp_datetime"
imo_column = "IMO"
voyage_column = "voyage_id"
n_ships = 3


def get_linked_IMO_data() -> pd.DataFrame:
    """Retrieve IMO numbers linked to pollution events.

    The data contains the timestamp of the pollution events, as well as
    the three closest ships during that event.

    Returned data has columns <timestamp_column>, ship_0, ship_1, ship_2.
    """
    # Open the pollution events linked to the 3 closest IMO numbers
    with open("./closestShips.json") as file:
        linked_IMO_data = (
            pd.DataFrame()
            .from_records(json.load(file))
            .rename(columns={"datetime": timestamp_column})
        )

    # Convert the timestamp to pd.Timestamp
    linked_IMO_data[timestamp_column] = linked_IMO_data[timestamp_column].apply(
        pd.Timestamp.fromtimestamp
    )

    # Extract the 3 closest ships and remove extraneous data
    for i in range(n_ships):
        linked_IMO_data[f"ship_{i}"] = linked_IMO_data.apply(
            lambda x: str(int(x["closestShips"][i])), axis=1
        )

    linked_IMO_data.drop(columns=["closestShips", "closestShipTrajs"], inplace=True)

    return linked_IMO_data


def get_voyage_data() -> pd.DataFrame:
    """Retrieve voyage data.

    Returned data has columns <voyage_column>, <imo_column>, min_time, max_time.
    """
    # Open the dataset containing voyage information
    #    with open(reduced_data_folder / "reduced_data_20230922_1525.pkl", "rb") as file:
    with open(reduced_data_folder / "reduced_data_20230925_1111.pkl", "rb") as file:
        voyage_data = pickle.load(file)

    agg_functions = {
        imo_column: pd.NamedAgg(column=imo_column, aggfunc="first"),
        "min_time": pd.NamedAgg(column=timestamp_column, aggfunc="min"),
        "max_time": pd.NamedAgg(column=timestamp_column, aggfunc="max"),
    }

    voyage_data = (
        voyage_data[[voyage_column, timestamp_column, imo_column]]
        .groupby(voyage_column)
        .agg(**agg_functions)
        .reset_index()
    )
    return voyage_data


linked_IMO_data = get_linked_IMO_data()
linked_IMO_data = linked_IMO_data.reset_index()
# orig_IMO = linked_IMO_data.copy()
voyage_data = get_voyage_data()


with open(reduced_data_folder / "reduced_data_20230925_1111.pkl", "rb") as file:
    full_voyage_data = pickle.load(file)

print(linked_IMO_data.shape)
indexcol = "index"
indices = linked_IMO_data[indexcol].copy()


for i in range(3):
    # change column names to min_time_<i>, max_time_<i>, ship_<i>
    temp_voyages = (
        voyage_data.copy()
        .rename(
            columns={
                col: f"{col}_{i}" for col in voyage_data.columns if col != imo_column
            }
        )
        .rename(columns={"IMO": f"ship_{i}"})
    )

    linked_IMO_data = linked_IMO_data.merge(temp_voyages, how="left", on=f"ship_{i}")
    linked_IMO_data = linked_IMO_data[
        (linked_IMO_data[f"min_time_{i}"] < linked_IMO_data[timestamp_column])
        & (linked_IMO_data[f"max_time_{i}"] > linked_IMO_data[timestamp_column])
    ]
    print(linked_IMO_data.shape)


missing_ships = [
    ship for ship in indices if ship not in list(linked_IMO_data[indexcol])
]
print("---")
print(voyage_data.columns)

for event_nr in range(linked_IMO_data.shape[0]):
    row = linked_IMO_data.iloc[event_nr]
    voyages = list(row[[f"voyage_id_{i}" for i in range(3)]])
    print(voyages)
    map = make_map(full_voyage_data, plot_list=voyages, save=False)

    folium.Marker(
        location=row[["Latitude", "Longitude"]],
        fill=True,
        fill_color="orange",
        radius=10,
    ).add_to(map)

    map.save(f"pollution_event_{event_nr}.html")
