"""Store zones: boundaries, occupancy, queue status.

Coordinates are store-map percent (x: 0..100, y: 0..70) matching the SVG
viewBox used by the frontend 2D map. Zone colors follow the global system:
neutral normally, green healthy, red crowded/critical.
"""

ZONES = [
    {'id': 'entry', 'name': 'Entry', 'polygon': [[2, 1], [24, 1], [24, 8], [2, 8]], 'kind': 'entry'},
    {'id': 'exit', 'name': 'Exit', 'polygon': [[76, 1], [98, 1], [98, 8], [76, 8]], 'kind': 'exit'},
    {'id': 'beverages', 'name': 'Beverages', 'polygon': [[5, 12], [35, 12], [35, 30], [5, 30]], 'kind': 'shelf'},
    {'id': 'snacks', 'name': 'Snacks & Food', 'polygon': [[40, 12], [70, 12], [70, 30], [40, 30]], 'kind': 'shelf'},
    {'id': 'grocery', 'name': 'Grocery', 'polygon': [[5, 34], [35, 34], [35, 52], [5, 52]], 'kind': 'shelf'},
    {'id': 'personal', 'name': 'Personal Care', 'polygon': [[40, 34], [70, 34], [70, 52], [40, 52]], 'kind': 'shelf'},
    {'id': 'checkout', 'name': 'Checkout', 'polygon': [[10, 56], [65, 56], [65, 67], [10, 67]], 'kind': 'checkout', 'queue_threshold': 7},
]

DWELL_ALERT_SECONDS = 300.0
STORE_CAPACITY = 80


def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xinters = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1
            if x < xinters:
                inside = not inside
    return inside


def zone_for_point(x: float, y: float) -> dict | None:
    for zone in ZONES:
        if point_in_polygon(x, y, zone['polygon']):
            return zone
    return None


def zone_status(zone: dict, count: int) -> str:
    threshold = zone.get('queue_threshold', 10)
    if zone.get('kind') == 'checkout':
        if count >= threshold * 2:
            return 'critical'
        if count >= threshold:
            return 'busy'
        return 'normal'
    if count >= threshold:
        return 'crowded'
    if count == 0:
        return 'empty'
    return 'normal'
