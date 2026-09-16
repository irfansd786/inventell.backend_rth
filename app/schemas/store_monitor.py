from pydantic import BaseModel


class CalibrationIn(BaseModel):
    camera_points: list
    map_points: list


class StartIn(BaseModel):
    camera_id: str = 'camera_01'
    force: bool = False
