"""
Site polygon processing utilities.

WGS84↔UTM coordinate conversion, Vworld WFS parcel boundary fetch,
and site validation.
"""

import logging

from shapely.geometry import MultiPolygon, Polygon, box, shape, mapping
from shapely.ops import transform
from pyproj import Transformer

from design import config
from design.exceptions import SiteGeometryError

logger = logging.getLogger(__name__)

# Korea is in UTM zone 52N (126°E–132°E)
_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32652", always_xy=True)
_to_wgs = Transformer.from_crs("EPSG:32652", "EPSG:4326", always_xy=True)


def wgs84_to_utm(polygon: Polygon) -> Polygon:
    """Convert WGS84 (lon/lat) polygon to UTM52N (meters)."""
    return transform(_to_utm.transform, polygon)


def utm_to_wgs84(polygon: Polygon) -> Polygon:
    """Convert UTM52N (meters) polygon to WGS84 (lon/lat)."""
    return transform(_to_wgs.transform, polygon)


def geojson_to_polygon(geojson: dict) -> Polygon:
    """Convert GeoJSON geometry dict to Shapely Polygon."""
    geom = shape(geojson)
    if isinstance(geom, MultiPolygon):
        return max(geom.geoms, key=lambda polygon: polygon.area)
    return geom


def polygon_to_geojson(polygon: Polygon) -> dict:
    """Convert Shapely Polygon to GeoJSON geometry dict."""
    return mapping(polygon)


def fetch_parcel_boundary(pnu: str) -> dict | None:
    """
    Fetch parcel boundary polygon from Vworld Data API (LP_PA_CBND_BUBUN).

    Args:
        pnu: 19-digit PNU code

    Returns:
        GeoJSON geometry dict or None if not found
    """
    if not config.VWORLD_API_KEY:
        logger.warning("VWORLD_API_KEY not set, cannot fetch parcel boundary")
        return None

    try:
        resp = config.vworld_client.get(
            "https://api.vworld.kr/req/data",
            params={
                "service": "data",
                "request": "GetFeature",
                "data": "LP_PA_CBND_BUBUN",
                "attrFilter": f"pnu:=:{pnu}",
                "format": "json",
                "crs": "EPSG:4326",
                "key": config.VWORLD_API_KEY,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        response = data.get("response", {})
        if response.get("status") != "OK":
            logger.warning("Vworld Data API error for PNU %s: %s", pnu, response.get("status"))
            return None

        features = (
            response
            .get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        if not features:
            logger.warning("No parcel boundary found for PNU %s", pnu)
            return None

        return polygon_to_geojson(geojson_to_polygon(features[0].get("geometry")))

    except Exception as e:
        logger.error("Vworld Data API fetch failed for PNU %s: %s", pnu, e)
        return None


def validate_site(polygon: Polygon) -> dict:
    """
    Validate site polygon for optimization.

    Returns:
        {"valid": bool, "area_m2": float, "errors": [str]}
    """
    errors = []

    if not polygon.is_valid:
        errors.append("Polygon geometry is invalid")

    utm_poly = wgs84_to_utm(polygon)
    area = utm_poly.area

    if area < 10:
        errors.append(f"Site too small: {area:.1f} m² (minimum 10 m²)")

    if area > 100000:
        errors.append(f"Site too large: {area:.1f} m² (maximum 100,000 m²)")

    bounds = utm_poly.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width < 3 or height < 3:
        errors.append(f"Site too narrow: {width:.1f}m × {height:.1f}m (minimum 3m each)")

    return {
        "valid": len(errors) == 0,
        "area_m2": round(area, 2),
        "bounds_m": {
            "width": round(width, 2),
            "height": round(height, 2),
        },
        "errors": errors,
    }
