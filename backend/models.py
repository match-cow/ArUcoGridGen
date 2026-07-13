from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Page(StrictModel):
    paper_size: Literal["A4", "A3", "A2", "A1", "Letter", "Legal"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"


class PrintCompensation(StrictModel):
    x_percent: float = Field(100, gt=0, le=200)
    y_percent: float = Field(100, gt=0, le=200)

    @field_validator("x_percent", "y_percent")
    @classmethod
    def finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("must be finite")
        return value


class Annotations(StrictModel):
    show_ruler: bool = True
    show_parameters: bool = True
    show_frame_legend: bool = False


class Pose(StrictModel):
    translation_x_m: float = 0
    translation_y_m: float = 0
    translation_z_m: float = 0
    roll_deg: float = 0
    pitch_deg: float = 0
    yaw_deg: float = 0

    @field_validator(
        "translation_x_m", "translation_y_m", "translation_z_m", "roll_deg", "pitch_deg", "yaw_deg"
    )
    @classmethod
    def finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("must be finite")
        return value


class CoordinateFrame(StrictModel):
    enabled: bool = False
    pose: Pose = Pose()


class ArucoBoard(StrictModel):
    type: Literal["aruco"]
    dictionary: str = "DICT_5X5_100"
    rows: int = Field(7, ge=1, le=100)
    columns: int = Field(5, ge=1, le=100)
    marker_size_mm: float = Field(30, gt=0, le=200)
    separation_mm: float = Field(10, gt=0, le=200)
    show_ids: bool = True
    id_font_size_pt: float = Field(8, ge=6, le=72)


class CharucoBoard(StrictModel):
    type: Literal["charuco"]
    dictionary: str = "DICT_5X5_250"
    squares_x: int = Field(5, ge=2, le=100)
    squares_y: int = Field(7, ge=2, le=100)
    square_size_mm: float = Field(30, gt=0, le=200)
    marker_size_mm: float = Field(18, gt=0, le=200)

    @model_validator(mode="after")
    def marker_smaller_than_square(self):
        if self.marker_size_mm >= self.square_size_mm:
            raise ValueError("marker_size_mm must be smaller than square_size_mm")
        return self


class Checkerboard(StrictModel):
    type: Literal["checkerboard"]
    squares_x: int = Field(5, ge=2, le=100)
    squares_y: int = Field(8, ge=2, le=100)
    square_size_mm: float = Field(30, gt=0, le=200)
    border_mm: float = Field(20, ge=0, le=100)


Board = Annotated[ArucoBoard | CharucoBoard | Checkerboard, Field(discriminator="type")]


class GenerateRequest(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    page: Page = Page()
    board: Board = ArucoBoard(type="aruco")
    print_compensation: PrintCompensation = PrintCompensation()
    annotations: Annotations = Annotations()
    coordinate_frame: CoordinateFrame = CoordinateFrame()


class FitChange(StrictModel):
    field: str
    before: float
    after: float


class FitResponse(StrictModel):
    request: GenerateRequest
    adjusted: bool
    scale_factor: float = Field(gt=0, le=1)
    changes: tuple[FitChange, ...] = ()
