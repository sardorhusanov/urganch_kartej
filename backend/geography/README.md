# Xorazm location classification

`xorazm.geojson` is the versioned WGS84 classification dataset. GeoJSON coordinates are `[longitude, latitude]`; API inputs use explicit `lat` / `lng` fields.

The initial dataset contains 11 district areas and 3 city areas. Urganch and Xiva cities are children of Xorazm; Pitnak is a child of Tuproqqal’a district. Future custom areas can be added as Polygon/MultiPolygon features with stable IDs and a `parentId`. The deepest matching area wins; shared borders or overlapping sibling areas return `ambiguous`, rather than assigning an arbitrary district. Holes and disconnected polygons are supported. Coordinates outside all supported areas return `outside`.

## Source and accuracy

© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Snapshot retrieved 2026-11-26. The dataset embeds the source URL for each feature and its version. The derived dataset is available through `GET /api/locations/boundaries` under the same license.

District geometry comes from OSM administrative relations at level 6 in Xorazm relation [196242](https://www.openstreetmap.org/relation/196242), including Tuproqqal’a relation 11992833. City geometry comes from OSM settlement polygons: Urganch way 110132970, Xiva way 110260748, and Pitnak way 394570342. **The city polygons are settlement outlines, not certified municipal boundaries.** They are working service areas; they must be replaced with authoritative municipal limits before relying on this classification as an official administrative determination. District polygons also inherit OSM accuracy limitations. No rectangular or nearest-center approximations are used.

Region-level city polygons are removed from district geometries to avoid overlapping sibling service areas. Pitnak remains nested inside Tuproqqal’a. This normalization does not claim to modify legal district boundaries.

## Updating the dataset

Download the reviewed Overpass geometry (`out geom`) for the 11 district relations, plus Nominatim GeoJSON results for the three cities. Respect the source services' usage limits. Run from the repository root:

```sh
uv run python scripts/import_xorazm_boundaries.py /path/to/districts.json /path/to/cities-directory
uv run --locked python -m unittest discover -s backend/tests -v
```

The city files are named `city-Urganch.json`, `city-Xiva.json`, and `city-Pitnak.json`. The importer rejects incomplete rings and invalid geometry. For official replacement boundaries, write the same FeatureCollection schema directly and assign a new `version`. Preserve stable IDs, inspect coverage/overlaps, and update the provenance/license. Restart or redeploy the app after updating; the index is cached per process.

Confirmed locations and new booking endpoints store their classification and boundary version. Existing orders are not silently reclassified. New submissions are classified again on the server, regardless of any area metadata supplied by the browser.
