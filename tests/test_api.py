"""Автотести REST API. Запуск: python -m unittest -v   (з кореня проєкту)

Кожен тест працює з окремою тимчасовою базою, тому реальні дані не зачіпаються.
"""
import os
import tempfile
import unittest

_db_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
_db_file.close()
os.environ['DATABASE'] = _db_file.name  # має бути ДО імпорту app

from app import app  # noqa: E402
import models  # noqa: E402


def reset_db():
    with app.app_context():
        db = models.get_db()
        db.executescript('DROP TABLE IF EXISTS order_items; DROP TABLE IF EXISTS orders; DROP TABLE IF EXISTS feedback;'
                         'DROP TABLE IF EXISTS promo_codes; DROP TABLE IF EXISTS products; DROP TABLE IF EXISTS roast_levels;'
                         'DROP TABLE IF EXISTS users;')
        models.init_db()


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.client = app.test_client()
        self.admin = self.login('admin', 'admin123')

    def tearDown(self):
        pass

    def login(self, username, password):
        r = self.client.post('/api/v1/auth/login', json={'username': username, 'password': password})
        self.assertEqual(r.status_code, 200, r.json)
        return {'Authorization': 'Bearer ' + r.json['token']}

    def register(self, username='client', password='client123'):
        r = self.client.post('/api/v1/auth/register', json={'username': username, 'password': password})
        self.assertEqual(r.status_code, 201, r.json)
        return {'Authorization': 'Bearer ' + r.json['token']}


class AuthTests(ApiTestCase):
    def test_register_login_me(self):
        headers = self.register()
        r = self.client.get('/api/v1/me', headers=headers)
        self.assertEqual((r.status_code, r.json['role']), (200, 'client'))

    def test_register_validation_and_conflict(self):
        r = self.client.post('/api/v1/auth/register', json={'username': 'ab', 'password': '123'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('username', r.json['details'])
        self.assertIn('password', r.json['details'])  # обидві помилки одразу
        self.register('dup')
        r = self.client.post('/api/v1/auth/register', json={'username': 'dup', 'password': 'secret1'})
        self.assertEqual(r.status_code, 409)

    def test_wrong_password_401(self):
        r = self.client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'wrong'})
        self.assertEqual(r.status_code, 401)

    def test_no_token_and_bad_token_401(self):
        self.assertEqual(self.client.get('/api/v1/me').status_code, 401)
        r = self.client.get('/api/v1/me', headers={'Authorization': 'Bearer fake'})
        self.assertEqual(r.status_code, 401)

    def test_client_cannot_use_admin_endpoints_403(self):
        headers = self.register()
        r = self.client.post('/api/v1/products', headers=headers, json={'name': 'X', 'price': 1, 'roast_id': 1})
        self.assertEqual(r.status_code, 403)

    def test_invalid_json_400(self):
        r = self.client.post('/api/v1/auth/login', data='not json', content_type='application/json')
        self.assertEqual(r.status_code, 400)


class ProductTests(ApiTestCase):
    def test_list_get_filter_search_sort(self):
        r = self.client.get('/api/v1/products')
        self.assertEqual((r.status_code, len(r.json)), (200, 12))
        self.assertEqual(len(self.client.get('/api/v1/products?roast=1').json), 4)
        self.assertEqual(len(self.client.get('/api/v1/products?q=ШОКОЛАД').json), 4)  # кирилиця без регістру
        prices = [p['price'] for p in self.client.get('/api/v1/products?sort=price_asc').json]
        self.assertEqual(prices, sorted(prices))
        self.assertEqual(self.client.get('/api/v1/products/1').json['id'], 1)

    def test_bad_query_params_400(self):
        self.assertEqual(self.client.get('/api/v1/products?sort=wrong').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/products?roast=abc').status_code, 400)

    def test_not_found_json_404(self):
        r = self.client.get('/api/v1/products/9999')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content_type, 'application/json')
        self.assertIn('error', r.json)

    def test_crud(self):
        body = {'name': 'Тест', 'description': 'опис', 'price': 99.5, 'roast_id': 2}
        r = self.client.post('/api/v1/products', headers=self.admin, json=body)
        self.assertEqual(r.status_code, 201)
        pid = r.json['id']
        self.assertEqual(r.headers['Location'], f'/api/v1/products/{pid}')

        r = self.client.patch(f'/api/v1/products/{pid}', headers=self.admin, json={'price': 120})
        self.assertEqual((r.status_code, r.json['price'], r.json['name']), (200, 120.0, 'Тест'))

        r = self.client.put(f'/api/v1/products/{pid}', headers=self.admin, json={**body, 'name': 'Нова назва'})
        self.assertEqual(r.json['name'], 'Нова назва')

        self.assertEqual(self.client.delete(f'/api/v1/products/{pid}', headers=self.admin).status_code, 204)
        self.assertEqual(self.client.get(f'/api/v1/products/{pid}').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/v1/products/{pid}', headers=self.admin).status_code, 404)

    def test_validation_errors(self):
        r = self.client.post('/api/v1/products', headers=self.admin,
                             json={'name': '  ', 'price': 'дорого', 'roast_id': 999})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json['details']), {'name', 'price'})  # roast_id перевіряється після типів
        r = self.client.post('/api/v1/products', headers=self.admin, json={'name': 'X', 'price': -5, 'roast_id': 1})
        self.assertIn('price', r.json['details'])
        r = self.client.post('/api/v1/products', headers=self.admin, json={'name': 'X', 'price': True, 'roast_id': 1})
        self.assertIn('price', r.json['details'])  # bool не є числом
        r = self.client.post('/api/v1/products', headers=self.admin, json={'name': 'X', 'price': 5, 'roast_id': 999})
        self.assertIn('roast_id', r.json['details'])

    def test_delete_product_in_order_409(self):
        headers = self.register()
        self.client.post('/api/v1/orders', headers=headers,
                         json={'address': 'Луцьк, вул. Тестова 1', 'items': [{'product_id': 1, 'quantity': 1}]})
        r = self.client.delete('/api/v1/products/1', headers=self.admin)
        self.assertEqual(r.status_code, 409)


class RoastTests(ApiTestCase):
    def test_crud_and_conflicts(self):
        self.assertEqual(len(self.client.get('/api/v1/roasts').json), 3)
        r = self.client.post('/api/v1/roasts', headers=self.admin, json={'name': 'Еспресо', 'color': '#112233'})
        self.assertEqual(r.status_code, 201)
        rid = r.json['id']
        self.assertEqual(self.client.post('/api/v1/roasts', headers=self.admin, json={'name': 'Еспресо'}).status_code, 409)
        self.assertEqual(self.client.post('/api/v1/roasts', headers=self.admin,
                                          json={'name': 'Погане', 'color': 'red'}).status_code, 400)
        self.assertEqual(self.client.delete('/api/v1/roasts/1', headers=self.admin).status_code, 409)  # є товари
        self.assertEqual(self.client.delete(f'/api/v1/roasts/{rid}', headers=self.admin).status_code, 204)


class OrderTests(ApiTestCase):
    ORDER = {'address': 'м. Луцьк, вул. Володимирська, 1', 'promo_code': 'coffee10',
             'items': [{'product_id': 1, 'quantity': 2}, {'product_id': 2, 'quantity': 1}]}

    def test_create_with_promo_total_from_db(self):
        headers = self.register()
        r = self.client.post('/api/v1/orders', headers=headers, json=self.ORDER)
        self.assertEqual(r.status_code, 201, r.json)
        # (2×420 + 460) = 1300, знижка 10% → 1170
        self.assertEqual((r.json['total_price'], r.json['discount_percent']), (1170.0, 10))
        self.assertEqual(len(r.json['items']), 2)

    def test_order_validation(self):
        headers = self.register()
        bad = {'address': 'x', 'items': [{'product_id': 9999, 'quantity': 0}, 'abc'], 'promo_code': 'NOPE'}
        r = self.client.post('/api/v1/orders', headers=headers, json=bad)
        self.assertEqual(r.status_code, 400)
        self.assertIn('address', r.json['details'])
        r = self.client.post('/api/v1/orders', headers=headers, json={'address': 'Луцьк, вул. 1', 'items': []})
        self.assertIn('items', r.json['details'])
        r = self.client.post('/api/v1/orders', headers=headers,
                             json={'address': 'Луцьк, вул. 1', 'promo_code': 'NOPE',
                                   'items': [{'product_id': 1, 'quantity': 1}]})
        self.assertIn('promo_code', r.json['details'])
        r = self.client.post('/api/v1/orders', headers=headers,
                             json={'address': 'Луцьк, вул. 1', 'items': [{'product_id': 9999, 'quantity': 1}]})
        self.assertEqual(r.status_code, 400)

    def test_requires_auth(self):
        self.assertEqual(self.client.post('/api/v1/orders', json=self.ORDER).status_code, 401)

    def test_visibility_between_users(self):
        alice, bob = self.register('alice'), self.register('bobby')
        oid = self.client.post('/api/v1/orders', headers=alice, json=self.ORDER).json['id']
        self.assertEqual(self.client.get(f'/api/v1/orders/{oid}', headers=alice).status_code, 200)
        self.assertEqual(self.client.get(f'/api/v1/orders/{oid}', headers=bob).status_code, 404)  # чуже
        self.assertEqual(self.client.get(f'/api/v1/orders/{oid}', headers=self.admin).status_code, 200)
        self.assertEqual(len(self.client.get('/api/v1/orders', headers=bob).json), 0)
        self.assertEqual(len(self.client.get('/api/v1/orders', headers=alice).json), 1)

    def test_status_change_admin_only(self):
        headers = self.register()
        oid = self.client.post('/api/v1/orders', headers=headers, json=self.ORDER).json['id']
        url = f'/api/v1/orders/{oid}/status'
        self.assertEqual(self.client.patch(url, headers=headers, json={'status': 'Оплачено'}).status_code, 403)
        self.assertEqual(self.client.patch(url, headers=self.admin, json={'status': 'вигадано'}).status_code, 400)
        r = self.client.patch(url, headers=self.admin, json={'status': 'Оплачено'})
        self.assertEqual((r.status_code, r.json['status']), (200, 'Оплачено'))
        self.assertEqual(self.client.delete(f'/api/v1/orders/{oid}', headers=self.admin).status_code, 204)


class ExtrasTests(ApiTestCase):
    def test_promo_validate_and_admin_crud(self):
        self.assertEqual(self.client.get('/api/v1/promos/validate?code=coffee10').json['discount_percent'], 10)
        self.assertEqual(self.client.get('/api/v1/promos/validate?code=nope').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/promos').status_code, 401)
        r = self.client.post('/api/v1/promos', headers=self.admin, json={'code': 'SUMMER15', 'discount_percent': 15})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.post('/api/v1/promos', headers=self.admin,
                                          json={'code': 'SUMMER15', 'discount_percent': 15}).status_code, 409)
        self.assertEqual(self.client.post('/api/v1/promos', headers=self.admin,
                                          json={'code': 'BIG', 'discount_percent': 99}).status_code, 400)
        self.assertEqual(self.client.delete(f'/api/v1/promos/{r.json["id"]}', headers=self.admin).status_code, 204)

    def test_feedback(self):
        headers = self.register()
        self.assertEqual(self.client.post('/api/v1/feedback', json={'message': 'Смачно'}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/feedback', headers=headers, json={'message': 'ok'}).status_code, 400)
        r = self.client.post('/api/v1/feedback', headers=headers, json={'message': 'Смачна кава!'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.client.get('/api/v1/feedback').json), 1)
        self.assertEqual(self.client.delete(f'/api/v1/feedback/{r.json["id"]}', headers=headers).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/v1/feedback/{r.json["id"]}', headers=self.admin).status_code, 204)

    def test_users_and_roles(self):
        headers = self.register()
        self.assertEqual(self.client.get('/api/v1/users', headers=headers).status_code, 403)
        users = self.client.get('/api/v1/users', headers=self.admin).json
        self.assertNotIn('password_hash', users[0])
        client_id = next(u['id'] for u in users if u['username'] == 'client')
        self.assertEqual(self.client.patch(f'/api/v1/users/{client_id}/role', headers=self.admin,
                                           json={'role': 'admin'}).json['role'], 'admin')
        self.assertEqual(self.client.patch('/api/v1/users/1/role', headers=self.admin,
                                           json={'role': 'client'}).status_code, 409)  # власна роль


class VersioningTests(ApiTestCase):
    def test_v1_vs_v2_format(self):
        v1 = self.client.get('/api/v1/products')
        v2 = self.client.get('/api/v2/products?per_page=5&page=2')
        self.assertEqual((v1.headers['X-API-Version'], v2.headers['X-API-Version']), ('1', '2'))
        self.assertIsInstance(v1.json, list)
        self.assertEqual(set(v2.json), {'data', 'meta'})
        self.assertEqual(v2.json['meta'], {'page': 2, 'per_page': 5, 'total': 12, 'pages': 3})
        self.assertEqual(len(v2.json['data']), 5)
        self.assertIsInstance(v2.json['data'][0]['roast'], dict)  # вкладений об'єкт

    def test_error_formats_differ(self):
        e1 = self.client.get('/api/v1/products/9999').json
        e2 = self.client.get('/api/v2/products/9999').json
        self.assertIsInstance(e1['error'], str)
        self.assertEqual(e2['error']['code'], 'not_found')

    def test_v2_pagination_validation(self):
        r = self.client.get('/api/v2/products?page=0&per_page=500')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json['error']['details']), {'page', 'per_page'})

    def test_v2_orders_paginated(self):
        headers = self.register()
        for _ in range(3):
            self.client.post('/api/v1/orders', headers=headers,
                             json={'address': 'Луцьк, вул. 1', 'items': [{'product_id': 1, 'quantity': 1}]})
        r = self.client.get('/api/v2/orders?per_page=2', headers=headers)
        self.assertEqual((len(r.json['data']), r.json['meta']['total'], r.json['meta']['pages']), (2, 3, 2))


class ErrorFormatTests(ApiTestCase):
    def test_unknown_url_and_method_are_json(self):
        r = self.client.get('/api/v1/unknown')
        self.assertEqual((r.status_code, r.content_type), (404, 'application/json'))
        r = self.client.put('/api/v1/products', headers=self.admin, json={})
        self.assertEqual((r.status_code, r.content_type), (405, 'application/json'))

    def test_website_still_returns_html_404(self):
        r = self.client.get('/no-such-page')
        self.assertEqual((r.status_code, r.content_type.split(';')[0]), (404, 'text/html'))

    def test_swagger_available(self):
        self.assertEqual(self.client.get('/apidocs/').status_code, 200)
        spec = self.client.get('/apispec.json').json
        self.assertIn('/api/v1/products', spec['paths'])
        self.assertIn('/api/v2/products', spec['paths'])


if __name__ == '__main__':
    unittest.main()
