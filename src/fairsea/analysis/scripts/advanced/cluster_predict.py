from pathlib import Path
from typing import Dict, List
from hdbscan import HDBSCAN
from dtw import dtw
import numpy as np
import pickle
import json
from sklearn.cluster import DBSCAN
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from tqdm import tqdm

from compress_and_compare_voyages import calc_proximity_matrix

eps_compression = 0.003
epsilon_suffix = f"{eps_compression:.4f}".replace(".", "_")


def calc_extra_distance(
    train_voyages: Dict[str, np.ndarray], new_voyage: np.ndarray
) -> np.ndarray:
    distances = [dtw(voyage, new_voyage, distance_only=True).distance for voyage in train_voyages.values()]
    return np.array(distances)


def expand_distance_matrix(
    orig_matrix: np.ndarray, new_distances: np.ndarray
) -> np.ndarray:
    temp_matrix = np.append(orig_matrix, np.expand_dims(new_distances, axis=0), axis=0)
    temp_vector = np.expand_dims(np.append(new_distances, [0]), axis=-1)
    return np.append(temp_matrix, temp_vector, axis=1)


def predict_single_voyage(
    train_voyages, distance_matrix, new_voyage: np.ndarray, epsilon=12.0
) -> int:
    new_distance_array = calc_extra_distance(train_voyages, new_voyage)
    new_distance_matrix = expand_distance_matrix(distance_matrix, new_distance_array)
    clusterer = DBSCAN(eps=epsilon, metric="precomputed")
    label = clusterer.fit_predict(new_distance_matrix)[-1]
    return label


def predict_voyages(
    compressed_voyages: Dict[str, np.ndarray],
    train_voyages: List[str],
    test_voyages: List[str],
    name: str,
    epsilon: float = 12.0,
):
    # get the train/test sets
    train_set = {vid: compressed_voyages[vid] for vid in train_voyages}
    test_set = {vid: compressed_voyages[vid] for vid in test_voyages}

    # establish a baseline from the train set
    base_distances = calc_proximity_matrix(train_set, name)
    train_clusterer = DBSCAN(eps=epsilon, metric="precomputed")
    train_labels = train_clusterer.fit_predict(base_distances)
    train_predictions = {
        vid: cluster for vid, cluster in zip(train_set.keys(), train_labels)
    }

    # predict individual voyages from the test_set
    test_predictions = {}

    for vid, voyage in tqdm(test_set.items()):
        label = predict_single_voyage(
            train_set, base_distances, voyage, epsilon=epsilon
        )
        test_predictions.update({vid: label})

    return train_predictions, test_predictions

def make_binary_class(predictions: Dict[str, int]):
    return {key: int(value < 0) for key, value in predictions.items()}


if __name__ == "__main__":
    datapath = "../output/compressed_voyages/"
    with open(f"{datapath}/compressed_eps_{epsilon_suffix}_west_coast.pkl", "rb") as file:
        compressed_voyages = pickle.load(file=file)
    distances_all = calc_proximity_matrix(compressed_voyages, __name__)
    clusterer_all = DBSCAN(eps=12., metric="precomputed")
    # clusterer_all = HDBSCAN(cluster_selection_epsilon=12. , metric="precomputed")
    
    clusterer_all.fit(distances_all)
    
    voyage_classes_all = {
        vid: int(label < 0)
        for vid, label in zip(compressed_voyages.keys(), clusterer_all.labels_)
    }

    # save voyage_classes_all to a file
    OUTPUT_PATH = Path("../output")
    voyage_file = "voyage_clustering.json"

    with open(OUTPUT_PATH / voyage_file, "w") as file:
        json.dump(voyage_classes_all, file)
    
    print(np.mean(list(voyage_classes_all.values())))
    train, test = train_test_split(list(compressed_voyages.keys()), train_size=0.8, random_state=1234)

    train_pred, test_pred = predict_voyages(compressed_voyages, train_voyages=train, test_voyages=test, name=__name__, epsilon=12.)

    train_bin, test_bin = make_binary_class(train_pred), make_binary_class(test_pred)

    y_pred = train_bin.copy()
    y_pred.update(test_bin) 

    y_true = {v: voyage_classes_all[v] for v in y_pred.keys()}
    y_true_value = list(y_true.values())
    y_pred_value = list(y_pred.values())
    
    print(np.mean(y_true_value))
    print(np.mean(y_pred_value))

    cm = confusion_matrix(y_true_value, y_pred_value)
    print(cm)

