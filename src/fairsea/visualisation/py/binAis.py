import csv
import pandas as pd
import altair as alt
import argparse
from pathlib import Path
import utm
from tqdm import tqdm

def binRound(x, binSize):
    return round(x / binSize) * binSize

# Bin reported positions into a grid by rounded longitude and latitude lines
def binData(aisPath = "../../../../fairsea_data/ais2018_cargo.csv", binSize = 0.01):
    bins = {}
    count = 0
    with open(aisPath) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            x = float(row['Longitude'])
            y = float(row['Latitude'])
            xBin = binRound(x, binSize)
            yBin = binRound(y, binSize)
            if not xBin in bins:
                bins[xBin] = {}
                count += 1
            if not yBin in bins[xBin]:
                bins[xBin][yBin] = 1
            else:
                bins[xBin][yBin] += 1
    print(f"Created {count} bins")

    return pd.DataFrame({'Longitude': x, 'Latitude': y, 'counts': yBins} for x, xBins in bins.items() for y, yBins in xBins.items())


# Bin reported positions into grid with cells of size binSize x binSize metres.
def binDataUTM(aisPath = "../../../../fairsea_data/ais2018_cargo.csv", binSize = 1000):
    # Count the number of rows (for progress bar)
    with open(aisPath) as csvfile:
        totalrows = sum(1 for _ in csvfile)

    print(f"{totalrows} rows in total", flush=True)

    bins = {}
    count = 0
    with open(aisPath) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in tqdm(reader, total=totalrows):
            latitude = float(row['Latitude'])
            longitude = float(row['Longitude'])

            # Convert lat/lon to UTM x, y, and zones
            x, y, zoneNumber, zoneLetter = utm.from_latlon(latitude, longitude)

            # Round to binSize
            xBin = binRound(x, binSize)
            yBin = binRound(y, binSize)

            # Add count to bin
            if not zoneNumber in bins:
                bins[zoneNumber] = {}
            if not zoneLetter in bins[zoneNumber]:
                bins[zoneNumber][zoneLetter] = {}
            if not xBin in bins[zoneNumber][zoneLetter]:
                bins[zoneNumber][zoneLetter][xBin] = {}
            if not yBin in bins[zoneNumber][zoneLetter][xBin]:
                bins[zoneNumber][zoneLetter][xBin][yBin] = 1
                count += 1
            else:
                bins[zoneNumber][zoneLetter][xBin][yBin] += 1

    print(f"Created {count} bins")

    rows = []
    for zoneNumber, zoneLetterBins in bins.items():
        for zoneLetter, xBins in zoneLetterBins.items():
            for xBin, yBins in xBins.items():
                for yBin, count in yBins.items():
                    # Convert UTM x, y, and zones back to lat/lon
                    latitude, longitude = utm.to_latlon(xBin, yBin, zoneNumber, zoneLetter)

                    # Add row for dataframe
                    rows.append({
                        'Longitude': longitude,
                        'Latitude': latitude,
                        'counts': count,
                        'x': xBin,
                        'y': yBin,
                        'zoneLetter': zoneLetter,
                        'zoneNumber': zoneNumber
                    })

    return pd.DataFrame(rows)

# Create heatmap from binned data
def heatmap(binnedDf, colorColumn="counts", scaleType="log", pointSize=2, mapPath="europe.geo.json",
            lngMin=None, lngMax=None, latMin=None, latMax=None, width=2000, height=2000):
    area = (binnedDf[colorColumn] == binnedDf[colorColumn])
    if lngMin is not None:
        area = area & (binnedDf['Longitude'] >= lngMin)
    if lngMax is not None:
        area = area & (binnedDf['Longitude'] <= lngMax)
    if latMin is not None:
        area = area & (binnedDf['Latitude'] >= latMin)
    if latMax is not None:
        area = area & (binnedDf['Latitude'] <= latMax)
    croppedDf = binnedDf.loc[area]
    mapSource = alt.topo_feature(mapPath, 'geometry')
    alt.data_transformers.enable('json')

    return alt.layer(
        alt.Chart(mapSource).mark_geoshape(clip=True, fill='Gainsboro', stroke='grey'),
        alt.Chart(croppedDf).mark_circle(size=pointSize).encode(
            longitude=alt.Longitude("Longitude:Q"),
            latitude=alt.Latitude("Latitude:Q"),
            color=alt.Color(f'{colorColumn}:Q').scale(type=scaleType, scheme='turbo')
        ).properties(
            width=width,
            height=height
        ),
    )

def heatmapFromPath(aisPath = "ais2018_cargo.csv", binSize = 0.01, utm=False):
    df = binDataUTM(aisPath, binSize) if utm else binData(aisPath, binSize)
    return heatmap(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                    prog='Bin AIS data',
                    description='Discretise AIS data into multiple bins',
                    epilog=None)
    parser.add_argument('aisPath', help="Path to AIS data CSV")
    parser.add_argument('-s', '--binSize', type=float, default=0.01)
    parser.add_argument('-o', '--outFile', default='../data/binnedAIS.csv')
    parser.add_argument('-u', '--utm', action='store_true')

    args = parser.parse_args()

    # Bin the data
    df = binDataUTM(args.aisPath, args.binSize) if args.utm else binData(args.aisPath, args.binSize)

    # Create intermediate directories if neccesary
    filepath = Path(args.outFile)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Save CSV output
    df.to_csv(filepath, index=False)