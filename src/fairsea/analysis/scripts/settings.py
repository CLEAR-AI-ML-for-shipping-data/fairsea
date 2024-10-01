import datetime as dt
import os
import pickle
from typing import Any, List, Tuple

from pydantic import BaseModel, Field, model_validator
from pydantic.functional_validators import field_validator
from shapely.geometry import box


class EezFiles(BaseModel):
    internal: str = "../../data/eco_zones/eez_internal_waters_v3.gpkg"
    territorial: str = "../../data/eco_zones/eez_12nm_v3.gpkg"
    contiguous: str = "../../data/eco_zones/eez_24nm_v3.gpkg"
    eez: str = "../../data/eco_zones/eez_v11.gpkg"

    @classmethod
    def check_path(cls, name: str):
        if not os.path.exists(name):
            raise ValueError(f"Path {name} does not exist")
        return name

    @field_validator("internal", "territorial", "contiguous", "eez")
    @classmethod
    def check_file(cls, name: str):
        name = cls.check_path(name)
        if not os.path.isfile(name):
            raise ValueError(f"Path {name} is not a file")
        return name


class Settings(BaseModel):
    ais_data_path: str = "../../data/ais2018_chemical_tanker.csv"
    meta_data_path: str = "../../data/imo_km_oil.csv"
    output_folder: str = "../output"
    bbox: Tuple[float, float, float, float] = (9.0, 56.0, 25.7, 66.0)
    eez_files: EezFiles = EezFiles()
    stages: List[str] = []
    output_suffix: str = "timestamp"
    compression_eps: float = 0.003
    clustering_eps: float = 12.0
    voyages_filename: str = "default"  # Field(default="default")
    compressed_filename: str = Field(default="default")
    matrix_filename: str = Field(default="default")
    map_filename: str = "default"

    @classmethod
    def check_path(cls, name: str):
        if not os.path.exists(name):
            raise ValueError(f"Path {name} does not exist")
        return name

    @field_validator("ais_data_path", "meta_data_path")
    @classmethod
    def check_file(cls, name: str):
        name = cls.check_path(name)
        if not os.path.isfile(name):
            raise ValueError(f"Path {name} is not a file")
        return name

    @field_validator("output_folder")
    @classmethod
    def check_dir(cls, name: str):
        name = cls.check_path(name)
        if not os.path.isdir(name):
            raise ValueError(f"Path {name} is not a directory")
        return os.path.normpath(name)

    @field_validator("bbox")
    @classmethod
    def check_bounding_box(cls, box: Tuple[float, float, float, float]):
        if not box[0] < box[2]:
            raise ValueError(
                f"Western boundary {box[0]} should be smaller than eastern boundary {box[2]}"
            )
        if not box[1] < box[3]:
            raise ValueError(
                f"Southern boundary {box[1]} should be smaller than northern boundary {box[3]}"
            )
        return box

    @field_validator("output_suffix")
    @classmethod
    def make_output(cls, suffix: str):
        match suffix:
            case "timestamp":
                return dt.datetime.now().strftime("%Y%m%d_%H%M")
            case _:
                return suffix

    @field_validator("compression_eps", "clustering_eps")
    @classmethod
    def check_positive(cls, value: float):
        if value < 0:
            raise ValueError(f"Value {value} should be positive")
        return value

    @model_validator(mode="after")
    def update_filenames(self):
        self.voyages_filename = self.validate_filename(self.voyages_filename, "voyages")
        self.compressed_filename = self.validate_filename(
            self.compressed_filename, "compressed"
        )
        self.matrix_filename = self.validate_filename(self.matrix_filename, "proximity")
        self.map_filename = self.validate_filename(self.map_filename, "map")

        return self

    def validate_filename(self, name: str, filetype: str):
        if name != "default":
            name = self.check_path(name)
            return name
        suffix = f"{self.output_suffix}.pkl"
        match filetype:
            case "voyages":
                prefix = "reduced_data"
            case "compressed":
                prefix = "compressed_voyages"
            case "proximity":
                prefix = "proximity_matrix"
            case "map":
                prefix = "voyage_map"
                suffix = f"{self.output_suffix}.html"

            case _:
                prefix = ""

        return f"{self.output_folder}/{prefix}_{suffix}"

    def get_bbox(self, edge=0.0):
        return box(
            self.bbox[0] - edge,
            self.bbox[1] - edge,
            self.bbox[2] + edge,
            self.bbox[3] + edge,
        )

    def read_data_file(self, filetype: str):
        match filetype:
            case "voyages":
                filename = self.voyages_filename
            case "compressed":
                filename = self.compressed_filename
            case "proximity":
                filename = self.matrix_filename
            case _:
                raise ValueError("Unknown type for read method")
        print(f"Read {filetype} data from {filename}")
        with open(filename, "rb") as file:
            data = pickle.load(file)

        return data

    def write_data(self, data: Any, filetype: str):
        match filetype:
            case "voyages":
                filename = self.voyages_filename
            case "compressed":
                filename = self.compressed_filename
            case "proximity":
                filename = self.matrix_filename
            case _:
                raise ValueError("Unknown type for read method")
        print(f"Write {filetype} data to {filename}")
        with open(filename, "wb") as file:
            data = pickle.dump(data, file=file)

        return data

    def save_map(self, map):
        print(f"Writing map to {self.map_filename}")
        map.save(self.map_filename)
