"""Location endpoints: Geoapify lookup adapter + independent area classification."""
import json
import os
from typing import Annotated, Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .geography import DATASET, area_index, classify

router = APIRouter(prefix='/api/locations', tags=['locations'])
Latitude = Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


class Coordinates(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ExactLocation(Coordinates):
    address: Address
    source: Literal['map', 'search', 'gps', 'manual'] = 'manual'
    accuracy: float | None = Field(default=None, ge=0, le=10000000)


def confirmed_location(location):
    """Reclassify at each persistence boundary; never trust a client-supplied area."""
    result = classify(location.lat, location.lng)
    if result['status'] == 'outside':
        raise HTTPException(422, 'Hozircha faqat Xorazm viloyatidagi manzillar qabul qilinadi.')
    if result['status'] == 'ambiguous':
        raise HTTPException(422, 'Nuqta hududlar chegarasida. Belgini aniq manzilga suring.')
    return {**location.model_dump(), 'classification': result}


@router.get('/config')
def config(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    enabled = bool(os.getenv('GEOAPIFY_API_KEY'))
    return {'provider': 'geoapify', 'addressSearch': enabled, 'businessSearch': enabled}


@router.get('/areas')
def areas():
    index = area_index()
    return {'version': index.version, 'areas': list(index.nodes.values())}


@router.get('/boundaries')
def boundaries():
    return FileResponse(DATASET, media_type='application/geo+json', filename='xorazm.geojson')


@router.post('/classify')
def classification(body: Coordinates):
    return classify(body.lat, body.lng)


@router.post('/confirm')
def confirm(body: ExactLocation):
    return confirmed_location(body)


def geocoder(operation, parameters):
    key = os.getenv('GEOAPIFY_API_KEY')
    if not key:
        raise HTTPException(503, 'Manzil qidiruvi hali sozlanmagan. Xaritadan yoki GPS orqali tanlang.')
    params = {**parameters, 'format': 'json', 'apiKey': key}
    request = Request(f'https://api.geoapify.com/v1/geocode/{operation}?' + urlencode(params))
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Response too large')
        locations = []
        for item in json.loads(raw)['results']:
            lat, lng = float(item['lat']), float(item['lon'])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180) or not item.get('formatted'):
                continue
            locations.append({'lat': lat, 'lng': lng, 'address': item['formatted'],
                              'name': item.get('name') or item['formatted'], 'precision': item.get('result_type')})
        return locations
    except (OSError, TimeoutError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Manzil qidiruvi vaqtincha ishlamayapti. Qayta urinib ko‘ring.') from None


@router.get('/search')
def search(response: Response, q: Annotated[str, Query(min_length=2, max_length=200)], kind: Literal['address', 'business'] = 'address'):
    response.headers['Cache-Control'] = 'no-store'
    results = geocoder('search', {'text': q, 'limit': 10, 'filter': 'rect:59.8,40.4,62.6,42.2',
                                  'bias': 'proximity:60.6317,41.5506'})
    return {'results': [r for r in results if (kind != 'business' or r.get('precision') == 'amenity')
                        and classify(r['lat'], r['lng'])['status'] != 'outside']}


@router.get('/reverse')
def reverse(response: Response, lat: Latitude, lng: Longitude):
    response.headers['Cache-Control'] = 'no-store'
    results = geocoder('reverse', {'lat': lat, 'lon': lng, 'limit': 1})
    return {'address': results[0]['address'] if results else '', 'precision': results[0]['precision'] if results else None}
