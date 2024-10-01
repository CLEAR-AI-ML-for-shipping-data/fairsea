import pandas as pd
import utils
import argparse
import json

def findClosestShips(aisPath, obsPath, dt, outPath):
    print(f"Using time diff = {dt}");

    print(f"Importing AIS data from {aisPath}")
    df_ais = pd.read_csv(aisPath, parse_dates=["Timestamp_datetime"])
    print(f"Importing observation data from {obsPath}")
    df_observations = pd.read_csv(obsPath, delimiter=';', header=None ,names=["date", "time", "Latitude", "Longitude"])

    print(f"Imported data for {df_ais.IMO.nunique()} ships and {len(df_observations.index)} observations")

    print("Converting observation date and time columns into formatted datetime column")
    df_observations['datetime'] = df_observations['date'] + ' ' + df_observations['time']
    df_observations = df_observations.drop(columns=['date', 'time'])
    df_observations.datetime = pd.to_datetime(df_observations.datetime, format='%m/%d/%Y %H:%M')


    print("Find ships closest to observations")
    df_observations['closestShip'] = df_observations.apply(lambda o: utils.findClosestShips(o.squeeze(), df_ais, dt, 3), axis=1)

    print(f"Saving closest trajectories to {outPath}")
    trajs = [
        {
            'Latitude': row['Latitude'],
            'Longitude': row['Longitude'],
            'datetime': row['datetime'].timestamp(),
            'closestShips': row['closestShip'],
            'closestShipTrajs': [json.loads(df_ais[
                (df_ais["IMO"] == imo) &
                (df_ais["Timestamp_datetime"] > row['datetime'] - dt) &
                (df_ais["Timestamp_datetime"] <= row['datetime'] + dt)
            ].to_json(orient="records")) for imo in row['closestShip'] if imo != 0
        ]} for _, row in df_observations.iterrows()
    ]

    # Save trajectories to json
    with open(outPath, 'w') as f:
        json.dump(trajs, f)

    print(f"Finished!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                    prog='Find closest ship',
                    description='Finds ships closest to a set of observations',
                    epilog=None)
    parser.add_argument('aisPath', help="Path to AIS data CSV")
    parser.add_argument('obsPath', help="Path to observations data CSV")
    parser.add_argument('-t', '--maxTimeDiff', type=pd.to_timedelta, default='2h')
    parser.add_argument('-o', '--outFile', default='closestShips.json')

    args = parser.parse_args()
    findClosestShips(args.aisPath, args.obsPath, args.maxTimeDiff, args.outFile)