
import folium
from math import radians,sin,cos,atan2,sqrt

# https://math.stackexchange.com/q/2573800
def heading(p1, p2):
    lat1, lng1 = p1
    lat2, lng2 = p2
    deltaLng = lng2 - lng1
    return atan2(
        sin(deltaLng) * cos(lat2),
        cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(deltaLng)
    )

def headingFromRow(row):
    p1 = [row['Latitude'], row['Longitude']]
    p2 = [row['previousLatitude'], row['previousLongitude']]
    return heading(p1, p2)

def gpsDistance(lat1,lng1,lat2,lng2):
        earthRadius = 3958.75
        dLat = radians(lat2-lat1)
        dLng = radians(lng2-lng1)
        a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLng / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = earthRadius * c
        meterConversion = 1609
        return abs(distance*meterConversion)

def calcDistsToObservation(observation, df_ais, dt):
    # Get everything no further than dt in time from the observation time t
    t = observation['datetime']
    df = df_ais[(df_ais['Timestamp_datetime'] > t - dt) & (df_ais['Timestamp_datetime'] <= t + dt)].copy()

    # Calculate the distances in meters to the observation
    lat = observation['Latitude']
    lng = observation['Longitude']
    df['dist'] = df.apply(
        lambda ais: gpsDistance(ais['Latitude'], ais['Longitude'], lat, lng),
        axis=1
    )

    return df

def findClosestShip(observation, df_ais, dt):
    # Calculate distances
    df = calcDistsToObservation(observation, df_ais, dt)

    # Find the record with the minimum distance and return the ship's IMO
    return df[df['dist']==df['dist'].min()].squeeze()['IMO']


def findClosestShips(observation, df_ais, dt, maxNumShips=None):
    # Calculate distances
    df = calcDistsToObservation(observation, df_ais, dt)

    # Find the record with the minimum distance and return the ship's IMO
    imos = list(v for v in df.sort_values(by=['dist'], ascending=True)['IMO'].drop_duplicates().values if v != 0)

    if maxNumShips is not None:
         return imos[:maxNumShips]
    else:
         return imos

def plotTrajectory(traj, fromDate=None, toDate=None):
    m = folium.Map()
    df = traj.sort_values(by=['Timestamp_datetime'], ascending=True)
    if fromDate is not None:
          df = df[df['Timestamp_datetime'] >= fromDate]
    if toDate is not None:
          df = df[df['Timestamp_datetime'] <= toDate.ceil('2D')]

    coords = df[['Latitude', 'Longitude']]

    sw = coords.min().values.tolist()
    ne = coords.max().values.tolist()
    m.fit_bounds([sw,ne])
    folium.PolyLine(coords.values.tolist()).add_to(m)
    return m

def mapObservations(df_observations, trajs):
    # Modify Marker template to include the onClick event
    # From https://stackoverflow.com/a/74908180
    click_template = """{% macro script(this, kwargs) %}
        var {{ this.get_name() }} = L.marker(
            {{ this.location|tojson }},
            {{ this.options|tojson }}
        ).addTo({{ this._parent.get_name() }}).on('click', onClick);
    {% endmacro %}"""

    # Change template to custom template
    folium.map.Marker._template = folium.map.Template(click_template)

    m = folium.Map()

    for i, row in df_observations.iterrows():
        folium.Marker(
            [row['Latitude'], row['Longitude']],
            tooltip=row['closestShip'],
            icon=folium.Icon(color="red", icon="exclamation-sign"),
            pathCoords=[traj[['Latitude', 'Longitude']].values.tolist() for traj in trajs[i]]
        ).add_to(m)

    # Add js to draw paths on marker click
    map_id = m.get_name()
    click_js = f"""function onClick(e) {{
        var coordslist = e.target.options.pathCoords;

        {map_id}.eachLayer(function(layer){{
            if (layer instanceof L.Polyline)
                {{ {map_id}.removeLayer(layer) }}
                }});

        for (let coords of coordslist) {{
            var path = L.polyline(coords);
            path.addTo({map_id});
        }}

        }}"""

    e = folium.Element(click_js)
    html = m.get_root()
    html.script.add_child(e)

    return m