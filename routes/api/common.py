"""Спільні інструменти REST API: помилки, токени, валідація, серіалізація, пагінація."""
import math
import re
from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, URLSafeTimedSerializer

import models

TOKEN_MAX_AGE = 60 * 60 * 24  # токен діє 24 години

ERROR_CODES = {
    400: 'bad_request', 401: 'unauthorized', 403: 'forbidden', 404: 'not_found',
    405: 'method_not_allowed', 409: 'conflict', 415: 'unsupported_media_type', 500: 'server_error',
}
ERROR_MESSAGES = {
    400: 'Некоректний запит', 401: 'Потрібна авторизація', 403: 'Недостатньо прав',
    404: 'Ресурс не знайдено', 405: 'Метод не дозволений для цього ресурсу',
    415: 'Очікується JSON (Content-Type: application/json)', 500: 'Внутрішня помилка сервера',
}


# ------------------------------------------------------------------ помилки

class ApiError(Exception):
    """Помилка API. Перетворюється на JSON-відповідь з потрібним кодом статусу."""

    def __init__(self, status, code, message, details=None, headers=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details, self.headers = details, headers or {}


def error_response(status, code, message, details=None, headers=None):
    """Формат помилки залежить від версії API (за адресою запиту)."""
    if request.path.startswith('/api/v2/'):
        body = {'error': {'code': code, 'message': message}}
        if details:
            body['error']['details'] = details
    else:
        body = {'error': message}
        if details:
            body['details'] = details
    response = jsonify(body)
    response.status_code = status
    for name, value in (headers or {}).items():
        response.headers[name] = value
    return response


def handle_api_error(error):
    return error_response(error.status, error.code, error.message, error.details, error.headers)


def handle_http_error(error):
    """Помилки Flask/Werkzeug (404 для невідомої адреси, 405 тощо) теж віддаємо як JSON."""
    status = error.code or 500
    return error_response(status, ERROR_CODES.get(status, 'error'), ERROR_MESSAGES.get(status, error.description))


def not_found(what='Ресурс'):
    return ApiError(404, 'not_found', f'{what} не знайдено')


# ------------------------------------------------------ автентифікація (stateless)

def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='api-token')


def make_token(user_id):
    """Підписаний токен із id користувача. Сервер не зберігає сесій: уся інформація в токені."""
    return _serializer().dumps({'uid': user_id})


def read_token(token):
    try:
        return _serializer().loads(token, max_age=TOKEN_MAX_AGE).get('uid')
    except BadSignature:  # підробка або термін дії минув
        return None


def token_required(view):
    """Вимагає заголовок `Authorization: Bearer <token>`. Користувач кладеться в g.api_user."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            raise ApiError(401, 'unauthorized', 'Потрібен заголовок Authorization: Bearer <token>',
                           headers={'WWW-Authenticate': 'Bearer'})
        user_id = read_token(header[7:].strip())
        user = models.get_user(user_id) if user_id else None
        if user is None:
            raise ApiError(401, 'invalid_token', 'Токен недійсний або термін його дії минув',
                           headers={'WWW-Authenticate': 'Bearer'})
        g.api_user = user  # роль беремо з БД щоразу: зміна ролі діє одразу
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @token_required
    def wrapped(*args, **kwargs):
        if g.api_user['role'] != 'admin':
            raise ApiError(403, 'forbidden', 'Ця дія доступна лише адміністратору')
        return view(*args, **kwargs)
    return wrapped


# ----------------------------------------------------------------- валідація

def json_body():
    """Тіло запиту як словник; інакше 400."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, 'invalid_json', 'Тіло запиту має бути JSON-об\'єктом (Content-Type: application/json)')
    return data


def validate(data, spec, partial=False):
    """Перевіряє поля за описом `spec` і повертає очищені значення.

    spec: {поле: {'type': 'str'|'int'|'number', 'required': True, 'default': ...,
                  'min': ..., 'max': ..., 'pattern': ..., 'message': ..., 'strip': True}}
    partial=True (PATCH): відсутні поля пропускаються. Усі помилки збираються разом (400).
    """
    errors, clean = {}, {}
    for field, rule in spec.items():
        if field not in data:
            if partial:
                continue
            if rule.get('required', True):
                errors[field] = "Поле обов'язкове"
            else:
                clean[field] = rule.get('default')
            continue

        value, kind = data[field], rule['type']
        if kind == 'str':
            if not isinstance(value, str):
                errors[field] = 'Має бути рядком'
                continue
            if rule.get('strip', True):
                value = value.strip()
            if len(value) < rule.get('min', 0):
                errors[field] = 'Не може бути порожнім' if rule['min'] == 1 else f'Мінімум {rule["min"]} символів'
                continue
            if len(value) > rule.get('max', 1000):
                errors[field] = f'Максимум {rule["max"]} символів'
                continue
            if 'pattern' in rule and not re.fullmatch(rule['pattern'], value):
                errors[field] = rule.get('message', 'Невірний формат')
                continue
        else:
            allowed = int if kind == 'int' else (int, float)
            if isinstance(value, bool) or not isinstance(value, allowed) or \
                    (isinstance(value, float) and not math.isfinite(value)):
                errors[field] = 'Має бути цілим числом' if kind == 'int' else 'Має бути числом'
                continue
            if kind == 'number':
                value = round(float(value), 2)
            if value < rule.get('min', -math.inf) or value > rule.get('max', math.inf):
                errors[field] = f'Допустимі значення: від {rule.get("min", "−∞")} до {rule.get("max", "∞")}'
                continue
        clean[field] = value

    if errors:
        raise ApiError(400, 'validation_error', 'Помилка валідації вхідних даних', errors)
    return clean


# Правила для полів, які використовуються в кількох місцях
PRODUCT_SPEC = {
    'name': {'type': 'str', 'min': 1, 'max': 100},
    'description': {'type': 'str', 'max': 500, 'required': False, 'default': ''},
    'price': {'type': 'number', 'min': 0, 'max': 100000},
    'roast_id': {'type': 'int', 'min': 1},
}
ROAST_SPEC = {
    'name': {'type': 'str', 'min': 1, 'max': 50},
    'description': {'type': 'str', 'max': 300, 'required': False, 'default': ''},
    'color': {'type': 'str', 'pattern': r'#[0-9a-fA-F]{6}', 'message': 'Колір у форматі #rrggbb',
              'required': False, 'default': '#8a6a4f'},
}


def check_roast_exists(roast_id):
    if models.get_roast(roast_id) is None:
        raise ApiError(400, 'validation_error', 'Помилка валідації вхідних даних',
                       {'roast_id': 'Такого обсмаження не існує'})


# ---------------------------------------------------------------- пагінація

def get_page_args(default_per_page=10, max_per_page=50):
    errors = {}
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', default_per_page, type=int)
    if page is None or page < 1:
        errors['page'] = 'Має бути цілим числом ≥ 1'
    if per_page is None or not 1 <= per_page <= max_per_page:
        errors['per_page'] = f'Має бути цілим числом від 1 до {max_per_page}'
    if errors:
        raise ApiError(400, 'validation_error', 'Некоректні параметри пагінації', errors)
    return page, per_page


def paginate(items, serialize):
    """Повертає (елементи сторінки, meta). Пагінація в Python: для навчальної БД цього достатньо."""
    page, per_page = get_page_args()
    total = len(items)
    pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    meta = {'page': page, 'per_page': per_page, 'total': total, 'pages': pages}
    return [serialize(i) for i in items[start:start + per_page]], meta


# ------------------------------------------------------------ серіалізація

def user_dict(u):
    return {'id': u['id'], 'username': u['username'], 'role': u['role'], 'created_at': u['created_at']}


def roast_dict(r):
    data = {'id': r['id'], 'name': r['name'], 'description': r['description'], 'color': r['color']}
    if 'products_count' in r.keys():
        data['products_count'] = r['products_count']
    return data


def product_v1(p):
    return {'id': p['id'], 'name': p['name'], 'description': p['description'], 'price': p['price'],
            'roast_id': p['roast_id'], 'roast_name': p['roast_name']}


def product_v2(p):
    """У версії 2 обсмаження — вкладений об'єкт."""
    return {'id': p['id'], 'name': p['name'], 'description': p['description'], 'price': p['price'],
            'roast': {'id': p['roast_id'], 'name': p['roast_name'], 'color': p['roast_color']}}


def order_summary(o):
    return {'id': o['id'], 'user_id': o['user_id'], 'username': o['username'], 'status': o['status'],
            'total_price': o['total_price'], 'date': o['date'], 'items_summary': o['items']}


def order_full(order, items):
    data = order_summary(order)
    del data['items_summary']
    data.update({
        'address': order['address'], 'promo_code': order['promo_code'],
        'discount_percent': order['discount_percent'],
        'items': [{'product_id': i['product_id'], 'name': i['name'], 'quantity': i['quantity'],
                   'unit_price': i['unit_price']} for i in items],
    })
    return data


def feedback_dict(f):
    return {'id': f['id'], 'user_id': f['user_id'], 'username': f['username'],
            'message': f['message'], 'created_at': f['created_at']}


def promo_dict(p):
    return {'id': p['id'], 'code': p['code'], 'discount_percent': p['discount_percent'], 'active': bool(p['active'])}


def created(body, location):
    """201 Created із заголовком Location."""
    response = jsonify(body)
    response.status_code = 201
    response.headers['Location'] = location
    return response
