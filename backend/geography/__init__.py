"""Provider-independent, versioned geographic classification in WGS84."""
import json
import math
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape

DATASET = Path(__file__).with_name('xorazm.geojson')


class AreaIndex:
    def __init__(self, dataset):
        self.version = dataset['version']
        self.nodes = {node['id']: node for node in dataset['hierarchy']}
        self.areas = []
        for feature in dataset['features']:
            properties = feature['properties']
            geometry = shape(feature['geometry'])
            if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Polygon', 'MultiPolygon'):
                raise ValueError(f"Invalid area geometry: {properties['id']}")
            if properties['id'] in self.nodes:
                raise ValueError('Duplicate area ID')
            self.nodes[properties['id']] = properties
            self.areas.append((properties, geometry))
        for area in self.nodes.values():
            self.path(area['id'])  # Check missing parents and cycles at load time.

    def path(self, area_id):
        path, seen = [], set()
        while area_id:
            if area_id in seen:
                raise ValueError('Cycle in area hierarchy')
            seen.add(area_id)
            node = self.nodes[area_id]
            path.insert(0, {key: node[key] for key in ('id', 'name', 'kind')})
            area_id = node.get('parentId')
        return path

    def classify(self, lat, lng):
        if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError('Invalid coordinates')
        point = Point(lng, lat)  # GeoJSON uses longitude first; API uses named fields.
        matches = [(area, geometry) for area, geometry in self.areas if geometry.covers(point)]
        if not matches:
            return {'status': 'outside', 'area': None, 'path': [], 'boundaryVersion': self.version}
        depth = max(len(self.path(area['id'])) for area, _ in matches)
        matches = [(area, geom) for area, geom in matches if len(self.path(area['id'])) == depth]
        # Never silently choose between overlapping siblings or a shared boundary.
        if len(matches) != 1:
            return {'status': 'ambiguous', 'area': None, 'path': [], 'boundaryVersion': self.version,
                    'candidates': [self.path(area['id'])[-1] for area, _ in matches]}
        area, geometry = matches[0]
        path = self.path(area['id'])
        return {'status': 'matched', 'area': path[-1], 'path': path,
                'onBoundary': geometry.boundary.covers(point), 'boundaryVersion': self.version}


@lru_cache(maxsize=1)
def area_index():
    return AreaIndex(json.loads(DATASET.read_text()))


def classify(lat, lng):
    return area_index().classify(lat, lng)
