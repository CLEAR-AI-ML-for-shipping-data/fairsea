# FAIRSEA

Feasibility study of AI techniques to monitor tank cleaning in Swedish Waters


#### Collaboration agreement for research projects

Terms of agreement for collaborating with Digital Research Engineers at e-commons

---

We share programming code and results with the understanding that:

 1. It will be used for non-commercial research purposes only, unless agreed upon in a separate agreement.

 2. It won't be made publicly available without formally seeking our consent.

 3. If one uses it for some scientific article/report, or similar, we will be part of the authors/contributors list and formally included in the process of writing and presenting the results. Resulting publications follow the Chalmers Open Access policy (<https://www.chalmers.se/en/about-chalmers/organisation-and-governance/how-chalmers-is-steered/general-policy-documents/open-access-policy/>).

 4. A data management plan will be developed and updated.

Complying with the above authorizes you to use, copy, modify, and publish project code and results.

## FAIRSEA Pipeline

The FAIRSEA pipeline can be used in the following way

## Basics

The pipeline has been designed for Python 3.11 and higher.
Lower versions are not supported.

### Set-up

You only have to do this once

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Starting your environment

You can start your environment using this simple terminal command:

```sh
source .venv/bin/activate
```

Afterwards, your terminal prompt should have `(.venv)` in front of it.

### Running the script

The script will automatically get its configuration from the file `pipeline_config.toml`
You can then easily run the script with the command:

```sh
python pipeline_runner.py
```

This is equivalent to

```sh
python pipeline_runner.py --config pipeline_config.toml
```

You can also make your own config-file, and specify it with:

```sh
python pipeline_runner.py --config my_own_configfile.toml
```

## Configfile

The configfile consists of several sections.
The most important section is `[global]`, containing the global settings.

### Stages

The first setting in `[global]` is `stages`.
With this setting you can specify which parts of the pipeline will be executed.
The stages are, in order:

1. feature engineering
2. trajectory compression
3. trajectory comparison using dynamic time warp
4. clustering similar voyages
5. Plotting voyages on a map

If we want to disable a certain stage, we can just comment them out using the `#`-sign.
Let's say we only want to run stages 1, 3, and 4, then we would configure that as

```ini
stages = [
  "features",
#  "compression",
  "dtw",
  "clustering",
#  "plotting"
]
```

### Input data

Input data files are specified with the parameters `ais_data_path` for the AIS data, and `meta_data_path` for the ship metadata.

#### AIS data

The input AIS data should meet the following criteria:

1. It is a CSV-file
2. Latitude and longitude are in decimal degrees (US/international decimal convention), in the columns names `"Latitude"` and `"Longitude"`, respectively
3. We use the IMO number as a unique ship identifier, and this should be encoded in the column named `"IMO"`.
   a. There should also be a column `"MMSI"`
4. The timestamp should be of the [format](https://docs.python.org/3/library/datetime.html#format-codes) `"%Y-%m-%d %H:%M:%S"`.
   This means that 12 minutes and 35 seconds past 2 in the afternoon on the 14th of March of 2023 is represented as `2023-03-14 14:12:05`.
   Also, the timestamp column should be named `"Timestamp_datetime"`.
5. Naviational status should described in the column `"Navigational status (text)"`.
   The possible values in this field should be `"Moored"`, `"Anchor"`, `"Engine"`.
   Other values are possible, but might be ignored when the pipeline determines navigational status.

#### IMO data

The pipeline expects a file with ship metadata.
It will automatically filter all the ships that are not classified as a chemical tanker.
The location of this file can be specified using the `meta_data_path`-keyword.
The file should be a CSV, and at least contain the column `"imo_chemical` that contains the IMO numbers of chemical tankers.

#### EEZ data

Input files containing the EEZ-data are specified under the header `[global.eez_files]`.

```ini
[global.eez_files]
internal = "../../data/eco_zones/eez_internal_waters_v3.gpkg"
territorial = "../../data/eco_zones/eez_12nm_v3.gpkg"
contiguous = "../../data/eco_zones/eez_24nm_v3.gpkg"
eez = "../../data/eco_zones/eez_v11.gpkg"

```
These files can be obtained from <http://www.marineregions.org>.

## Common errors
### 1. KeyError in plotting stage.
If you have changed the bounding box, it is possible to get a KeyError in the plotting fase.
This error will look something like this:
```bash
Writing map to ../output/voyage_map_20231121_1458.html
Traceback (most recent call last):
  File "/Users/boschman/projects/fairsea/fairsea/analysis/scripts/pipeline_runner.py", line 194, in <module>
    run_pipeline(args.config, __name__)
                                            ^^^^^^^^^^^^^^^^^^
...
  File "/Users/boschman/projects/fairsea/fairsea/analysis/scripts/../../visualisation/abnormalTrajectoriesMap/atMap.py", line 327, in style_func
    'fillColor': self.territory_cmap[x['properties']['TERRITORY1']],
                 ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
KeyError: 'Germany'
```

Instead of `'Germany'`, you will see the name of a different territory/country.
If this happens, you will need to add an extra line in the file `create_map.py`, inside the call to `map.territories_cmap.update`.
Add a line after `"United States": "#800012",` so that it reads

```python
"United States": "800012",
"<Country mentioned in the KeyError>": "800012",
```
