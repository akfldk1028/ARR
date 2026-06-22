"""
Data schemas for the land app.

Pure dataclasses (no dependencies). Services continue returning dicts;
these serve as documentation and type guides for gradual adoption.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PnuInfo:
    pnu: str
    sido: str
    sigungu: str
    eupmyeondong: str
    ri: str
    land_type: str
    main_number: str
    sub_number: str
    land_type_name: str = ""
    address: str = ""
    coordinate_x: float | None = None
    coordinate_y: float | None = None


@dataclass
class LandInfo:
    success: bool
    pnu: str = ""
    zones: list[str] = field(default_factory=list)
    land_area_m2: float | None = None
    official_land_price: int | None = None
    land_use_situation: str = ""
    source: str = "stub"


@dataclass
class GeocodeResult:
    success: bool
    address: str = ""
    pnu: str | None = None
    coordinates: dict | None = None
    error: str = ""


@dataclass
class ReverseGeocodeResult:
    success: bool
    pnu: str | None = None
    address: str | None = None
    geometry: dict | None = None  # GeoJSON — future: shapely.Polygon
    coordinates: dict | None = None
    error: str = ""


@dataclass
class LawArticles:
    articles: list[dict] = field(default_factory=list)
    total_count: int = 0
    errors: list[str] = field(default_factory=list)
