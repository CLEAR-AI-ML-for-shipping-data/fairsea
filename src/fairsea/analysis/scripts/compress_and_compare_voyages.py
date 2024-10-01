import multiprocessing as mp
from rdp import rdp
import pickle
import numpy as np

from dtw import dtw
import time
import os
import pandas as pd

from .settings import Settings


def get_data(settings: Settings):
    """Load voyage data from a processed file.

    Args:
        settings: onbject containing the filename

    Returns:
        a pandas DataFrame with the voyages
    """
    filename = settings.voyages_filename
    print(f"Reading {filename}...")
    with open(filename, "rb") as file:
        df = pickle.load(file)
    print("Finished reading data.")
    return df


def compute_compressed_voyage(vid: str, coords: np.ndarray, epsilon: float):
    """Compress a voyage using the RDP algorithm

    Args:
        vid: voyage id
        coords: 2D array containing all the x,y coordinates of the voyage
        epsilon: compression parameter

    Returns:
        tuple of voyage id and the compressed voyage coordinates
    """
    mv_coords = rdp(coords, epsilon=epsilon)
    return (vid, mv_coords)


def compress_voyages(df: pd.DataFrame, epsilon: float = 0.001, name: str = "name"):
    """Compress voyages that are stored inside a dataframe.

    Args:
        df: DataFrame containing the voyages
        epsilon: compression parameter, larger epsilon means more compression
        name: this is a safeguard for the multiprocessing part. It will prevent
              a pool being created when the module is imported.

    Returns:
        a dictionary with voyage IDs as the keys, and compressed coordindate
        arrays as the value.

    """
    df = df.droplevel("IMO")[["voyage_id", "Longitude", "Latitude"]]
    voyage = "voyage_id"
    all_voyages_ID = df[voyage].unique()

    t0 = time.perf_counter()
    if name == "__main__":
        print("Starting pool...")
        nprocs = mp.cpu_count()
        pool = mp.Pool(processes=nprocs - 1)

        print("Creating inputs...")
        gdf = df.groupby(voyage)

        inputs = [
            (item[0], item[1].drop(columns=voyage).values, epsilon) for item in gdf
        ]

        print("Running starmap...")
        result = pool.starmap(compute_compressed_voyage, inputs)
        pool.close()
        t1 = time.perf_counter()

        print(f"Compressed {len(all_voyages_ID):,} voyages in {int(t1 - t0)} sec")

        result = {key: value for key, value in result if value.shape[0] > 1}
        return result


def proximity_parallel(i: int, j: int, i_coords: np.ndarray, j_coords: np.ndarray):
    """Calculate the distance between two (compressed) trajectories.

    This distance is calculated using dynamic time warp.
    More information can be found on https://dynamictimewarping.github.io/

    Args:
        i: index of the first trajectory
        j: index of the second trajectory
        i_coords: Nx2 numpy array of the coordinates of the first trajectory
        j_coords: Nx2 numpy array of the coordinates of the second trajectory

    Returns:
        a tuple with containing the i- and j-index, and the DTW distance.

    """
    return (i, j, dtw(i_coords, j_coords, distance_only=True).distance)


def calc_proximity_matrix(compressed_voyages: dict, name: str):
    """Calculate the distance matrix for a set of (compressed) voyages.

    Args:
        compressed_voyages (dict): Should be of the form {voyage_id: xy-coords}
        name: this is a safeguard for the multiprocessing part. It will prevent
              a pool being created when the module is imported.

    Returns:
        A matrix with the distances between trajectories according to the DTW algorithm.
    """
    if name == "__main__":
        n_voyages = len(compressed_voyages)
        voyages = list(compressed_voyages.keys())
        inputs = []

        number_combinations = int(n_voyages * (n_voyages - 1) / 2)

        print("Creating inputs for proximity calculation...")
        inputs = np.empty((number_combinations,), dtype=object)
        for i in range(n_voyages - 1):
            for j in range(i + 1, n_voyages):
                flat_index = n_voyages * i - int(i * (i + 1) / 2) + j - i - 1
                inputs[flat_index] = (
                    i,
                    j,
                    compressed_voyages[voyages[i]],
                    compressed_voyages[voyages[j]],
                )

        t0 = time.perf_counter()
        nprocs = mp.cpu_count()
        pool = mp.Pool(processes=nprocs)

        print("Running proximity calculation, this may take a while...")
        result = pool.starmap(proximity_parallel, inputs)
        pool.close()
        t1 = time.perf_counter()

        print(f"Calculated {number_combinations:,} distances in {int(t1 - t0)} sec")
        print(f"Constructing {n_voyages}x{n_voyages} distance matrix...")

        distances = np.zeros((n_voyages, n_voyages))
        for item in result:
            i, j = item[0], item[1]
            distances[i, j] = item[2]

        distances += distances.T

        t2 = time.perf_counter()
        print(f"Constructed distance matrix in {int(t2 - t1)} sec")

        return distances


def single_run(df: pd.DataFrame, epsilon: float = 0.003, name: str = "name"):
    """Do a single run of voyage compression and comparison.

    Args:
        df: DataFrame containing the voyages
        epsilon: compression parameter, larger epsilon means more compression
        name: this is a safeguard for the multiprocessing part. It will prevent
              a pool being created when the module is imported.
    """
    epsilon_suffix = f"{epsilon:.4f}".replace(".", "_")
    compressed_voyages = compress_voyages(df, epsilon=epsilon, name=name)

    datapath = "../output/compressed_voyages"
    if not os.path.exists(datapath):
        os.makedirs(datapath)

    # datetime_suffix = current_suffix = dt.datetime.now().strftime("%Y%m%d_%H%M")
    # with open(f"{datapath}/compressed_eps_{epsilon_suffix}_bothnia.pkl", "wb") as file:
    with open(
        f"{datapath}/compressed_eps_{epsilon_suffix}_west_coast.pkl", "wb"
    ) as file:
        pickle.dump(compressed_voyages, file=file)

    distance_matrix = calc_proximity_matrix(compressed_voyages, name=name)
    datapath = "../output/distance_matrices"
    if not os.path.exists(datapath):
        os.makedirs(datapath)

    # with open(f"{datapath}/distances_eps_{epsilon_suffix}.pkl", "wb") as file:
    with open(
        f"{datapath}/distances_eps_{epsilon_suffix}_west_coast.pkl", "wb"
    ) as file:
        pickle.dump(distance_matrix, file=file)


if __name__ == "__main__":
    df = get_data(Settings())
    epsilons = [0.003]
    for epsilon in epsilons:
        print(f"Running for epsilon={epsilon}")
        single_run(df, epsilon=epsilon, name=__name__)
