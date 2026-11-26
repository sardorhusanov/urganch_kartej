import copy
import json
import os
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from shapely.geometry import Polygon, MultiPolygon, mapping

from backend.geography import AreaIndex, area_index, classify


def feature(area_id, geometry, parent='region'):
    return {'type': 'Feature', 'properties': {'id': area_id, 'name': area_id, 'kind': 'district', 'parentId': parent}, 'geometry': mapping(geometry)}


class GeometryTests(unittest.TestCase):
    def index(self, features):
        return AreaIndex({'version': 'test-v1', 'hierarchy': [{'id': 'region', 'name': 'Region', 'kind': 'region', 'parentId': None}], 'features': features})

    def test_holes_and_multipart(self):
        mainland = Polygon([(0,0),(8,0),(8,8),(0,8)], holes=[[(2,2),(4,2),(4,4),(2,4)]])
        island = Polygon([(10,0),(12,0),(12,2),(10,2)])
        index = self.index([feature('district', MultiPolygon([mainland, island]))])
        self.assertEqual(index.classify(1,1)['status'], 'matched')
        self.assertEqual(index.classify(1,11)['status'], 'matched')
        self.assertEqual(index.classify(3,3)['status'], 'outside')
        self.assertTrue(index.classify(0,1)['onBoundary'])

    def test_shared_border_and_overlapping_siblings_are_ambiguous(self):
        index = self.index([feature('a', Polygon([(0,0),(2,0),(2,2),(0,2)])), feature('b', Polygon([(2,0),(4,0),(4,2),(2,2)]))])
        self.assertEqual(index.classify(1,2)['status'], 'ambiguous')
        self.assertEqual(index.classify(1,1.9)['area']['id'], 'a')
        self.assertEqual(index.classify(1,2.1)['area']['id'], 'b')

    def test_deepest_area_wins_without_map_provider(self):
        index = self.index([feature('district', Polygon([(0,0),(5,0),(5,5),(0,5)])), feature('custom', Polygon([(1,1),(2,1),(2,2),(1,2)]), 'district')])
        result = index.classify(1.5,1.5)
        self.assertEqual([p['id'] for p in result['path']], ['region','district','custom'])

    def test_real_city_and_district_coverage(self):
        self.assertEqual(len(area_index().areas), 14)
        self.assertEqual(classify(41.5506,60.6317)['area']['id'], 'uz-xo-urganch-city')
        self.assertEqual(classify(41.3783,60.3639)['area']['id'], 'uz-xo-xiva-city')
        self.assertEqual(classify(41.3194,61.0742)['area']['id'], 'uz-xo-hazorasp-district')
        self.assertEqual(classify(41.2325,61.3042)['area']['id'], 'uz-xo-tuproqqala-district')
        self.assertEqual(classify(41.3,69.2)['status'], 'outside')
        self.assertEqual(classify(60.6317,41.5506)['status'], 'outside')
        # A representative interior point in every stored polygon must classify.
        for properties, geometry in area_index().areas:
            point = geometry.representative_point()
            self.assertEqual(classify(point.y, point.x)['status'], 'matched', properties['id'])

    def test_invalid_coordinates_and_hierarchy(self):
        for lat,lng in [(91,0),(0,181),(float('nan'),0),(0,float('inf'))]:
            with self.assertRaises(ValueError): classify(lat,lng)
        with self.assertRaises(KeyError): self.index([feature('a',Polygon([(0,0),(1,0),(1,1),(0,1)]),'missing')])


class LocationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backend.main as main
        cls.main = main
        cls.directory = tempfile.TemporaryDirectory()
        cls.password = secrets.token_urlsafe(24)
        cls.environment = patch.dict(os.environ, {'KARTEJ_ADMIN_PASSWORD': cls.password, 'KARTEJ_ADMIN_USERNAME':'admin'}, clear=True)
        cls.environment.start()
        cls.data_patch = patch.object(main, 'DATA', Path(cls.directory.name)); cls.data_patch.start()
        main._initialized = False
        cls.client = TestClient(main.app); cls.client.__enter__()
        token = cls.client.post('/api/admin/login',json={'username':'admin','password':cls.password}).json()['token']
        cls.headers = {'Authorization':'Bearer '+token}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)
        cls.main._initialized = False
        cls.data_patch.stop(); cls.environment.stop(); cls.directory.cleanup()

    def location(self, **changes):
        return {'lat':41.5506,'lng':60.6317,'address':'Urganch, test street 10','source':'manual',**changes}

    def test_confirmation_ignores_forged_area_and_rejects_outside(self):
        response = self.client.post('/api/locations/confirm',json=self.location(classification={'area':{'id':'forged'}}))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['classification']['area']['id'],'uz-xo-urganch-city')
        self.assertEqual(self.client.post('/api/locations/confirm',json=self.location(lat=41.3,lng=69.2)).status_code,422)
        self.assertEqual(self.client.post('/api/locations/confirm',json=self.location(address=' ')).status_code,422)
        self.assertEqual(self.client.post('/api/locations/classify',json={'lat':100,'lng':60}).status_code,422)

    def test_keys_are_optional_and_search_secrets_are_not_exposed(self):
        with patch.dict(os.environ, {'GEOAPIFY_API_KEY':'private-geoapify'}):
            result=self.client.get('/api/locations/config')
            self.assertNotIn('private-',result.text)
            self.assertTrue(result.json()['businessSearch'])
        self.assertEqual(self.client.get('/api/locations/search',params={'q':'Urganch'}).status_code,503)
        self.assertEqual(self.client.get('/api/locations/search',params={'q':'hotel','kind':'business'}).status_code,503)
        self.assertEqual(self.client.get('/api/locations/reverse',params={'lat':41,'lng':60}).status_code,503)

    def test_lookup_results_use_polygons_not_search_bbox(self):
        with patch('backend.locations.geocoder', return_value=[self.location(),self.location(lat=41.3,lng=69.2)]):
            response=self.client.get('/api/locations/search',params={'q':'test'})
            self.assertEqual(len(response.json()['results']),1)
            self.assertEqual(response.headers['cache-control'],'no-store')

    def test_admin_place_classification_is_persisted(self):
        body={'name':'Test venue', **self.location(), 'classification':{'area':{'id':'forged'}}}
        response=self.client.post('/api/admin/cars/malibu/places',json=body,headers=self.headers)
        self.assertEqual(response.status_code,201,response.text)
        place=response.json()['places'][-1]
        self.assertEqual(place['address'],body['address'])
        self.assertEqual(place['classification']['area']['id'],'uz-xo-urganch-city')

    def test_exact_booking_locations_persist_without_changing_tariffs(self):
        result=self.client.put('/api/admin/cars/malibu/route',headers=self.headers,json={'start':'Urganch','end':'Xiva','amount':500000})
        self.assertEqual(result.status_code,200)
        places={p['name']:p for p in self.client.get('/api/places').json()}
        payload={'carId':'malibu','customerName':'Location test','phone':'+998901234567','date':str((datetime.now()+timedelta(days=2)).date()),'time':'12:00','start':places['Urganch'],'end':places['Xiva'],'expectedTotal':500000,
                 'exactStart':self.location(), 'exactEnd':self.location(lat=41.3783,lng=60.3639,address='Xiva, test street 20')}
        response=self.client.post('/api/orders',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(response.json()['deposit'],100000)
        order=next(o for o in self.client.get('/api/admin/orders',headers=self.headers).json() if o['id']==response.json()['id'])
        self.assertEqual(order['exactStart']['classification']['area']['id'],'uz-xo-urganch-city')
        self.assertEqual(order['exactEnd']['classification']['area']['id'],'uz-xo-xiva-city')
        self.assertEqual(order['start']['name'],'Urganch')
        self.assertEqual(order['total'],500000)
        payload['exactEnd']=self.location(lat=41.8447,lng=60.3919,address='Gurlan unrelated route')
        self.assertEqual(self.client.post('/api/orders',json=payload).status_code,422)
        payload['exactEnd']=None
        self.assertEqual(self.client.post('/api/orders',json=payload).status_code,422)
        payload.pop('exactStart');payload.pop('exactEnd')
        self.assertEqual(self.client.post('/api/orders',json=payload).status_code,201)  # Legacy clients.


if __name__ == '__main__': unittest.main()
