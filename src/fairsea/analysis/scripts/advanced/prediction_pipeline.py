import datetime as dt
import pickle
from typing import Dict

from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from sklearn.cluster import DBSCAN

from compress_and_compare_voyages import compress_voyages, calc_proximity_matrix
from cluster_predict import predict_voyages


def plot_voyage_cluster(voyage_list, compressed_voyages, ax: Axes, title='', cluster_labels=None, color=None):
    #colors = list(mcolors.XKCD_COLORS.keys())
    #title_suffix = ''

    #if cluster_labels is not None:
    #    n_clusters = np.unique(cluster_labels).size
    #    title_suffix = f', $\mathrm{{n_{{cluster}}}}$ = {n_clusters}'
    #    for cluster, v in zip(cluster_labels, voyage_list):
    #        color = colors[cluster]
    #        ax.plot(compressed_voyages[v][:, 0], compressed_voyages[v][:, 1], color=color, alpha=.1, linewidth=0.5)
    #else:
    #    for v in voyage_list:
    #        ax.plot(compressed_voyages[v][:, 0], compressed_voyages[v][:, 1], color="blue", alpha=.1, linewidth=0.5)
    for v in voyage_list:
        ax.plot(compressed_voyages[v][:, 0], compressed_voyages[v][:, 1], color="blue", alpha=.1, linewidth=0.5)
    # ax.set_xlabel('Longitude (degrees)')
    # ax.set_title((f"{title}, n = {voyage_list.size}{title_suffix}"))
    # ax.set_aspect('equal', adjustable='box')
        
    return ax

def make_plot(voyage_dict, voyage_labels: Dict[str, int], compression_eps, clustering_eps):
    fig, (ax_out, ax_reg) = plt.subplots(nrows=1, ncols=2, figsize=(25, 10), sharey=True, sharex=True)

    regulars = [voyage for voyage, label in voyage_labels.items() if label==0]
    outliers = [voyage for voyage, label in voyage_labels.items() if label==1]

    print(len(regulars))
    print(len(outliers))

    ax_reg = plot_voyage_cluster(regulars, voyage_dict, ax_reg, title='Regular voyages')
    ax_out = plot_voyage_cluster(outliers, voyage_dict, ax_out, title='Unclustered voyages')

    ax_out.set_ylabel('Latitude (degrees)')

    plt.suptitle(f"$\epsilon_{{\mathrm{{RDP}}}}$ = {compression_eps}, $\epsilon_{{\mathrm{{DBSCAN}}}}$ = {clustering_eps:.2f}")

    datetime_suffix = dt.datetime.now().strftime("%Y%m%d_%H%M")
    


    plt.savefig(f"../output/plots/compressed_voyages/clustering_{datetime_suffix}.png", dpi=300)
    plt.close()
    



def main(datafile="", name="name"):
    with open(datafile, "rb") as file:
        df = pickle.load(file)
    df = df.droplevel("IMO")[["voyage_id", "Longitude", "Latitude"]]

    compression_eps = 0.01
    cluster_eps= 12.

    compressed_voyages = compress_voyages(df, epsilon=compression_eps, name=name)
    distance_matrix = calc_proximity_matrix(compressed_voyages, name=name)
    
    cluster = DBSCAN(eps=cluster_eps, metric="precomputed")
    labels = cluster.fit_predict(distance_matrix)
    
    classes = {voyage: int(label < 0) for voyage, label in zip(compressed_voyages.keys(), labels)}

    make_plot(compressed_voyages, classes, compression_eps, cluster_eps)

if __name__ == "__main__":
    main("../output/reduced_data_20231027_1434.pkl", __name__)



