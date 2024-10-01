import numpy as np
import pickle

from sklearn.cluster import DBSCAN
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split, KFold

from compress_and_compare_voyages import calc_proximity_matrix

from cluster_predict import predict_voyages, make_binary_class

from matplotlib import pyplot as plt

def do_k_fold_validation(compressed_voyages, train_ids, test_ids, voyage_classes_all, name):
    train_pred, test_pred = predict_voyages(compressed_voyages, train_voyages=train_ids, test_voyages=test_ids, name=name, epsilon=12.)
    train_bin, test_bin = make_binary_class(train_pred), make_binary_class(test_pred)

    y_pred = test_bin.copy()
    y_pred.update(test_bin)
    y_true = {v: voyage_classes_all[v] for v in y_pred.keys()}
    y_true_value = list(y_true.values())
    y_pred_value = list(y_pred.values())

    return confusion_matrix(y_true_value, y_pred_value)

if __name__ == "__main__":
   
    eps_compression = 0.003
    epsilon_suffix = f"{eps_compression:.4f}".replace(".", "_")
    
    datapath = "../output/compressed_voyages/"
    with open(f"{datapath}/compressed_eps_{epsilon_suffix}.pkl", "rb") as file:
        compressed_voyages = pickle.load(file=file)
    distances_all = calc_proximity_matrix(compressed_voyages, __name__)
    clusterer_all = DBSCAN(eps=12., metric="precomputed")
    # clusterer_all = HDBSCAN(cluster_selection_epsilon=12. , metric="precomputed")
    
    clusterer_all.fit(distances_all)
    
    voyage_classes_all = {
        vid: int(label < 0)
        for vid, label in zip(compressed_voyages.keys(), clusterer_all.labels_)
    }
    
    print(np.mean(list(voyage_classes_all.values())))
    
    voyage_ids = np.array(list(compressed_voyages.keys()))
    
    folder = KFold(n_splits=5, shuffle=True, random_state=1234)
    
    cms = []
    
    for split in folder.split(voyage_ids):
        train_idx, test_idx = split
        train_set, test_set = voyage_ids[train_idx], voyage_ids[test_idx]
        
        cm = do_k_fold_validation(compressed_voyages, train_set, test_set, voyage_classes_all, __name__)
        cms.append(cm)
    
    for cm in cms:
        print(cm)

