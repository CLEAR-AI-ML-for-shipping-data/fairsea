import numpy as np


def heading(lat1: float, lng1: float, lat2: float, lng2: float):
    """Calculate the heading from position 1 to 2, in degrees.

    :param lat1: latitude of position 1
    :type lat1: float
    :param lng1: longitude of position 1
    :type lng1: float
    :param lat2: latitude of position 2
    :type lat2: float
    :param lng2: longitude of position 2
    :type lng2: float
    :return: heading from position 1 to 2
    :rtype: float
    """
    lat1_rad, lng1_rad, lat2_rad, lng2_rad = np.deg2rad([lat1, lng1, lat2, lng2])
    
    deltaLng_rad = lng2_rad - lng1_rad
    heading_rad = np.arctan2(
        np.sin(deltaLng_rad) * np.cos(lat2_rad),
        np.cos(lat1_rad) * np.sin(lat2_rad) - np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(deltaLng_rad)
    )

    return np.rad2deg(heading_rad)


def gps_distance_meters(pos_1_lat: float, pos_1_lon: float, 
                        pos_2_lat: float, pos_2_lon: float) -> float:
    """Calculate GPS distance between two points, in meters.

    :param pos_1_lat: latitude of position 1
    :type pos_1_lat: float
    :param pos_1_lon: longitude of position 1
    :type pos_1_lon: float
    :param pos_2_lat: latitude of position 2
    :type pos_2_lat: float
    :param pos_2_lon: longitude of position 2
    :type pos_2_lon: float
    :return: distance, in meters
    :rtype: float
    """
    
    # Radius of the earth, in meters
    R = 6373000.0

    pos_1_lat = np.radians(pos_1_lat)
    pos_1_lon = np.radians(pos_1_lon)
    pos_2_lat = np.radians(pos_2_lat)
    pos_2_lon = np.radians(pos_2_lon)

    dlon = pos_2_lon - pos_1_lon
    dlat = pos_2_lat - pos_1_lat

    a = np.sin(dlat / 2)**2 + np.cos(pos_1_lat) * np.cos(pos_2_lat) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    distance = R * c

    return distance
