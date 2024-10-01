#!/usr/bin/env python
from pprint import pprint
import tomllib
import argparse
from typing import Dict, Union
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from . import create_features as cf
from . import compress_and_compare_voyages as cc
from . import create_map as cm
from .settings import Settings
from .helpers.pipeline_helpers import extract_coords


def run_features(settings: Settings):
    """Create the engineered features from the create_features module.

    If settings.stages does not contain "features", this step will be skipped
    and return None.

    Args:
        settings: Settings object containing all the necessary settings

    Returns: a DataFrame with the engineered features.

    """
    if "features" in settings.stages:
        print("Engineering features...")
        return cf.main(settings=settings)


def compress_voyages(settings: Settings, data: pd.DataFrame, name: str = "name"):
    """Compress voyages using the RDP algorithm.

    A detailed explanation of the RDP algorithm can be found on
    https://rdp.readthedocs.io/
    Settings.compression_eps is used to set the compression parameter.


    Args:
        settings: Settings object containing necessary settings
        data: input dataframe
        name: protector for the multiprocessing calculations

    Returns:
        A dictionary with key-value pairs of voyage-id and an (n x 2) numpy array
        containing the x,y-coordinates.

    """
    # If "compression is not in settings.stages, just the pass the data on"
    if "compression" not in settings.stages:
        return data

    print("Compressing voyages...")

    # If the input-data is None, the previous step was probably skipped.
    # So instead read the voyages-file and use that data,
    if data is None:
        data = settings.read_data_file("voyages")

    # Compress the voyages, store in the output file, and return the compressed voyages
    compressed_voyages = cc.compress_voyages(data, settings.compression_eps, name)

    settings.write_data(compressed_voyages, "compressed")

    return compressed_voyages


def compare_voyages(
    settings: Settings, data: Dict[str, np.ndarray], name: str = "name"
):
    """Compare the similarity of compressed voyages using dynamic time warping.

    Args:
        data: dictionary with key-value pairs of voyage-id and an (n x 2) numpy array
              containing the x,y-coordinates.
        settings: Settings object containing necessary settings
        name: protector for the multiprocessing calculations

    Returns: an NxN matrix containing the DTW similarities of all voyages

    """
    if "dtw" not in settings.stages:
        return data

    print("Comparing voyages...")

    # if no data is provided, read the data containing the compressed voyages.
    if isinstance(data, pd.DataFrame):
        data = extract_coords(data)
    elif data is None:
        data = settings.read_data_file("compressed")

    proximity_matrix = cc.calc_proximity_matrix(data, name)

    settings.write_data(proximity_matrix, "proximity")

    return proximity_matrix


def cluster_voyages(
    settings: Settings,
    voyage_dict: Union[Dict[str, np.ndarray], pd.DataFrame],
    distance_matrix: np.ndarray,
):
    if "clustering" not in settings.stages:
        return None
    print("Clustering voyages...")
    if voyage_dict is None:
        voyage_dict = settings.read_data_file("compressed")
    elif isinstance(voyage_dict, pd.DataFrame):
        voyage_dict = extract_coords(voyage_dict)

    if distance_matrix is None:
        distance_matrix = settings.read_data_file("proximity")

    clusterer = DBSCAN(eps=settings.clustering_eps, metric="precomputed")
    clusterer.fit(distance_matrix)

    output = {
        vid: cluster for vid, cluster in zip(voyage_dict.keys(), clusterer.labels_)
    }
    return output


def make_voyage_maps(
    settings: Settings, dataf, voyage_clusters: Union[Dict[str, int], None]
):
    if "plotting" not in settings.stages:
        return None
    print("Creating map")
    if dataf is None:
        dataf = settings.read_data_file("voyages")

    if voyage_clusters is not None and -1 in voyage_clusters.values():
        voyage_clusters = {
            key: int(value < 0) for key, value in voyage_clusters.items()
        }

    map = cm.main(settings, dataf, voyage_clusters)
    settings.save_map(map)
    return map


def run_pipeline(configfile: str, name: str = "name"):
    """Run the main pipeline by running all the individual components

    Args:
        configfile: path to the configfile
        name: use '__main__' for parallel processing
    """
    # Load config file and use the global options
    with open(configfile, "rb") as file:
        configs = tomllib.load(file)
    general_options = configs["global"]
    pipeline_settings = Settings(**general_options)

    print("Running analysis pipeline with the following settings")
    pprint(pipeline_settings.model_dump())

    # Run the individual steps of the pipeline
    data = run_features(settings=pipeline_settings)
    voyage_dict = compress_voyages(settings=pipeline_settings, data=data, name=name)
    proximity_matrix = compare_voyages(
        settings=pipeline_settings, data=voyage_dict, name=name
    )
    clusters = cluster_voyages(
        settings=pipeline_settings,
        voyage_dict=voyage_dict,
        distance_matrix=proximity_matrix,
    )
    map = make_voyage_maps(
        settings=pipeline_settings, dataf=data, voyage_clusters=clusters
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="main_pipeline",
        description="Analyze, compare, and plot AIS trajectories",
        epilog=None,
    )
    parser.add_argument(
        "-c",
        "--config",
        default="pipeline_config.toml",
        help="Specify a configuration file",
    )

    args = parser.parse_args()

    run_pipeline(args.config, __name__)
