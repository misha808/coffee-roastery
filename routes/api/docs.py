"""Налаштування Swagger UI (flasgger): загальний опис, схема авторизації та схеми даних."""

SWAGGER_TEMPLATE = {
    'swagger': '2.0',
    'info': {
        'title': 'Roastery API',
        'description': (
            'REST API інтернет-магазину крафтової кави (лабораторна робота 05).\n\n'
            '**Як спробувати:** 1) `POST /api/v1/auth/login` з `{"username": "admin", "password": "admin123"}`; '
            '2) скопіюйте `token`; 3) натисніть **Authorize** і вставте `Bearer <token>`; '
            '4) натискайте **Try it out** на будь-якому ендпоінті.\n\n'
            '**Версії:** `/api/v1` — базова, `/api/v2` — з пагінацією, конвертом `{data, meta}` '
            'і структурованими помилками.'
        ),
        'version': '2.0.0',
    },
    'basePath': '/',
    'schemes': ['http', 'https'],
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'securityDefinitions': {
        'Bearer': {'type': 'apiKey', 'name': 'Authorization', 'in': 'header',
                   'description': 'Формат: `Bearer <token>`'}
    },
    'definitions': {
        'Error': {'type': 'object', 'properties': {
            'error': {'type': 'string', 'example': 'Опис помилки'},
            'details': {'type': 'object', 'description': 'Лише для помилок валідації: поле → що не так'}}},
        'ErrorV2': {'type': 'object', 'properties': {'error': {'type': 'object', 'properties': {
            'code': {'type': 'string', 'example': 'validation_error'},
            'message': {'type': 'string', 'example': 'Помилка валідації вхідних даних'},
            'details': {'type': 'object', 'example': {'page': 'Має бути цілим числом ≥ 1'}}}}}},
        'Credentials': {'type': 'object', 'required': ['username', 'password'], 'properties': {
            'username': {'type': 'string', 'example': 'admin'},
            'password': {'type': 'string', 'example': 'admin123'}}},
        'User': {'type': 'object', 'properties': {
            'id': {'type': 'integer', 'example': 1}, 'username': {'type': 'string', 'example': 'admin'},
            'role': {'type': 'string', 'enum': ['client', 'admin']},
            'created_at': {'type': 'string', 'example': '2026-11-24 21:00:00'}}},
        'TokenResponse': {'type': 'object', 'properties': {
            'token': {'type': 'string'}, 'token_type': {'type': 'string', 'example': 'Bearer'},
            'expires_in': {'type': 'integer', 'example': 86400}, 'user': {'$ref': '#/definitions/User'}}},
        'Product': {'type': 'object', 'properties': {
            'id': {'type': 'integer', 'example': 1}, 'name': {'type': 'string', 'example': 'Ефіопія Іргачефф'},
            'description': {'type': 'string', 'example': 'Бергамот, жасмин, лимонна цедра'},
            'price': {'type': 'number', 'example': 420.0}, 'roast_id': {'type': 'integer', 'example': 1},
            'roast_name': {'type': 'string', 'example': 'Світле'}}},
        'ProductV2': {'type': 'object', 'properties': {
            'id': {'type': 'integer', 'example': 1}, 'name': {'type': 'string', 'example': 'Ефіопія Іргачефф'},
            'description': {'type': 'string'}, 'price': {'type': 'number', 'example': 420.0},
            'roast': {'type': 'object', 'properties': {
                'id': {'type': 'integer', 'example': 1}, 'name': {'type': 'string', 'example': 'Світле'},
                'color': {'type': 'string', 'example': '#d8a94a'}}}}},
        'ProductPageV2': {'type': 'object', 'properties': {
            'data': {'type': 'array', 'items': {'$ref': '#/definitions/ProductV2'}},
            'meta': {'type': 'object', 'properties': {
                'page': {'type': 'integer', 'example': 1}, 'per_page': {'type': 'integer', 'example': 10},
                'total': {'type': 'integer', 'example': 12}, 'pages': {'type': 'integer', 'example': 2}}}}},
        'ProductInput': {'type': 'object', 'required': ['name', 'price', 'roast_id'], 'properties': {
            'name': {'type': 'string', 'example': 'Гондурас Копан'},
            'description': {'type': 'string', 'example': 'Какао, мигдаль, червоне яблуко'},
            'price': {'type': 'number', 'example': 395.5}, 'roast_id': {'type': 'integer', 'example': 2}}},
        'Roast': {'type': 'object', 'properties': {
            'id': {'type': 'integer', 'example': 1}, 'name': {'type': 'string', 'example': 'Світле'},
            'description': {'type': 'string'}, 'color': {'type': 'string', 'example': '#d8a94a'},
            'products_count': {'type': 'integer', 'example': 4}}},
        'RoastInput': {'type': 'object', 'required': ['name'], 'properties': {
            'name': {'type': 'string', 'example': 'Еспресо'},
            'description': {'type': 'string', 'example': 'Дуже темне обсмаження для еспресо'},
            'color': {'type': 'string', 'example': '#1f120c'}}},
        'OrderItemInput': {'type': 'object', 'required': ['product_id', 'quantity'], 'properties': {
            'product_id': {'type': 'integer', 'example': 1}, 'quantity': {'type': 'integer', 'example': 2}}},
        'OrderInput': {'type': 'object', 'required': ['address', 'items'], 'properties': {
            'address': {'type': 'string', 'example': 'м. Луцьк, вул. Володимирська, 1'},
            'promo_code': {'type': 'string', 'example': 'COFFEE10'},
            'items': {'type': 'array', 'items': {'$ref': '#/definitions/OrderItemInput'}}}},
        'OrderSummary': {'type': 'object', 'properties': {
            'id': {'type': 'integer', 'example': 1}, 'user_id': {'type': 'integer', 'example': 2},
            'username': {'type': 'string', 'example': 'client'}, 'status': {'type': 'string', 'example': 'Нове'},
            'total_price': {'type': 'number', 'example': 954.0}, 'date': {'type': 'string', 'example': '2026-11-24 21:30:00'},
            'items_summary': {'type': 'string', 'example': 'Ефіопія Іргачефф, Кенія AA'}}},
        'Order': {'type': 'object', 'properties': {
            'id': {'type': 'integer', 'example': 1}, 'user_id': {'type': 'integer'}, 'username': {'type': 'string'},
            'status': {'type': 'string', 'example': 'Нове'}, 'total_price': {'type': 'number', 'example': 954.0},
            'date': {'type': 'string'}, 'address': {'type': 'string'},
            'promo_code': {'type': 'string', 'example': 'COFFEE10'}, 'discount_percent': {'type': 'integer', 'example': 10},
            'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'product_id': {'type': 'integer'}, 'name': {'type': 'string'},
                'quantity': {'type': 'integer'}, 'unit_price': {'type': 'number'}}}}}},
        'StatusInput': {'type': 'object', 'required': ['status'], 'properties': {
            'status': {'type': 'string', 'enum': ['Нове', 'Оплачено', 'В обробці', 'Відправлено', 'Доставлено', 'Скасовано'],
                       'example': 'Оплачено'}}},
        'Promo': {'type': 'object', 'properties': {
            'id': {'type': 'integer'}, 'code': {'type': 'string', 'example': 'COFFEE10'},
            'discount_percent': {'type': 'integer', 'example': 10}, 'active': {'type': 'boolean', 'example': True}}},
        'PromoInput': {'type': 'object', 'required': ['code', 'discount_percent'], 'properties': {
            'code': {'type': 'string', 'example': 'SUMMER15'}, 'discount_percent': {'type': 'integer', 'example': 15}}},
        'Feedback': {'type': 'object', 'properties': {
            'id': {'type': 'integer'}, 'user_id': {'type': 'integer'}, 'username': {'type': 'string', 'example': 'client'},
            'message': {'type': 'string', 'example': 'Смачна кава!'}, 'created_at': {'type': 'string'}}},
        'FeedbackInput': {'type': 'object', 'required': ['message'], 'properties': {
            'message': {'type': 'string', 'example': 'Смачна кава, швидка доставка!'}}},
    },
}

SWAGGER_CONFIG = {
    'headers': [],
    'specs': [{'endpoint': 'apispec', 'route': '/apispec.json',
               'rule_filter': lambda rule: rule.rule.startswith('/api/'), 'model_filter': lambda tag: True}],
    'static_url_path': '/flasgger_static',
    'swagger_ui': True,
    'specs_route': '/apidocs/',
    'title': 'Roastery API',
    'doc_expansion': 'none',
}
