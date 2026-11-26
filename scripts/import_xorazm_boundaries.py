"""Build the versioned classification dataset from downloaded OSM geometry.

uv run python scripts/import_xorazm_boundaries.py DISTRICTS.json CITIES_DIRECTORY
DISTRICTS is Overpass `out geom` for admin_level=6 in relation 196242.
CITIES_DIRECTORY contains Nominatim city-{Urganch,Xiva,Pitnak}.json responses.
No network calls: review the input snapshot before replacing the dataset.
"""
import json
import sys
from datetime import date
from pathlib import Path

from shapely.geometry import LineString, mapping, shape
from shapely.ops import polygonize_full, unary_union

NAMES = {
    2097623: ('gurlan', 'Gurlan'), 2097624: ('shovot', 'Shovot'),
    2097625: ('yangibozor', 'Yangibozor'), 2097689: ('qoshkopir', 'Qo‘shko‘pir'),
    2097690: ('urganch', 'Urganch'), 2097691: ('xiva', 'Xiva'),
    2097692: ('yangiariq', 'Yangiariq'), 2097711: ('bogot', 'Bog‘ot'),
    2097712: ('xonqa', 'Xonqa'), 2097814: ('hazorasp', 'Hazorasp'),
    11992833: ('tuproqqala', 'Tuproqqal’a'),
}


def rings(relation, role):
    lines = [LineString([(p['lon'], p['lat']) for p in member['geometry']])
             for member in relation['members'] if member['type'] == 'way' and member['role'] == role]
    polygons, cuts, dangles, invalid = polygonize_full(lines)
    if any(len(part.geoms) for part in (cuts, dangles, invalid)):
        raise ValueError(f"Incomplete {role} rings in relation {relation['id']}")
    return unary_union(list(polygons.geoms))


def main():
    source = json.loads(Path(sys.argv[1]).read_text())
    cities_directory = Path(sys.argv[2])
    features, cities = [], {}
    for name in ('Urganch', 'Xiva', 'Pitnak'):
        candidates = json.loads((cities_directory / f'city-{name}.json').read_text())
        item = next(p for p in candidates if p.get('geojson', {}).get('type') in ('Polygon', 'MultiPolygon') and 'Xorazm' in p['display_name'])
        geometry = shape(item['geojson'])
        assert geometry.is_valid
        cities[name] = geometry
        features.append({'type': 'Feature', 'properties': {
            'id': f'uz-xo-{name.lower()}-city', 'name': name + ' shahri', 'kind': 'city',
            'parentId': 'uz-xo-tuproqqala-district' if name == 'Pitnak' else 'uz-xo',
            'sourceUrl': f"https://www.openstreetmap.org/{item['osm_type']}/{item['osm_id']}",
            'boundaryBasis': 'OSM mapped settlement polygon; not a certified municipal boundary',
        }, 'geometry': mapping(geometry)})
    seen = set()
    independent_cities = unary_union([cities['Urganch'], cities['Xiva']])
    for relation in source['elements']:
        slug, name = NAMES[relation['id']]
        seen.add(relation['id'])
        geometry = rings(relation, 'outer').difference(rings(relation, 'inner'))
        # Separate region-level city areas from district areas for this service's classification.
        geometry = geometry.difference(independent_cities)
        if not geometry.is_valid or geometry.is_empty:
            raise ValueError(name)
        features.append({'type': 'Feature', 'properties': {
            'id': f'uz-xo-{slug}-district', 'name': name + ' tumani', 'kind': 'district', 'parentId': 'uz-xo',
            'sourceUrl': f"https://www.openstreetmap.org/relation/{relation['id']}",
            'boundaryBasis': 'OSM administrative relation, with region-level city service areas excluded',
        }, 'geometry': mapping(geometry)})
    assert seen == set(NAMES)
    dataset = {
        'type': 'FeatureCollection', 'version': 'xorazm-osm-' + source['osm3s']['timestamp_osm_base'][:10],
        'source': {'name': 'OpenStreetMap contributors', 'license': 'ODbL-1.0',
                   'url': 'https://www.openstreetmap.org/copyright', 'retrievedOn': str(date.today()),
                   'osmTimestamp': source['osm3s']['timestamp_osm_base'],
                   'note': 'Working service-area boundaries. City polygons are settlement outlines, not certified administrative limits.'},
        'hierarchy': [{'id': 'uz', 'name': 'O‘zbekiston', 'kind': 'country', 'parentId': None},
                      {'id': 'uz-xo', 'name': 'Xorazm viloyati', 'kind': 'region', 'parentId': 'uz'}],
        'features': features,
    }
    Path('backend/geography/xorazm.geojson').write_text(json.dumps(dataset, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f"Imported {len(features)} areas: 11 districts and 3 cities.")


if __name__ == '__main__':
    main()
