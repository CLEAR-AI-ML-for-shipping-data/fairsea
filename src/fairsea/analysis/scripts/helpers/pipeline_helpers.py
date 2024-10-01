from typing import Any, Union
import pandas as pd


def extract_coords(data: Union[pd.DataFrame, Any]):
    """Extract the coordinate columns from the dataframe as a numpy array.

    Args:
        data: original dataframe

    Returns:
        A dictionary with key-value pairs of voyage-id and an (n x 2) numpy array
        containing the x,y-coordinates.

    """
    result = {
        item[0]: item[1][["Longitude", "Latitude"]].values
        for item in data.groupby("voyage_id")
    }
    return result
