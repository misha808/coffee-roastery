"""Каталог: товари та ступені обсмаження (версія 1)."""
import sqlite3

from flask import jsonify, request

import models
from . import api_v1
from .common import (PRODUCT_SPEC, ROAST_SPEC, ApiError, admin_required, check_roast_exists,
                     created, json_body, not_found, product_v1, roast_dict, validate)


def query_products():
    """Товари за параметрами q, roast, sort (спільна логіка для v1 і v2)."""
    q = request.args.get('q', '').strip()
    roast_id = request.args.get('roast', type=int) if request.args.get('roast') else None
    sort = request.args.get('sort', 'new')
    if request.args.get('roast') and roast_id is None:
        raise ApiError(400, 'validation_error', 'Некоректні параметри', {'roast': 'Має бути цілим числом'})
    if sort not in models.PRODUCT_SORTS:
        raise ApiError(400, 'validation_error', 'Некоректні параметри',
                       {'sort': f'Допустимі значення: {", ".join(models.PRODUCT_SORTS)}'})
    return models.get_products(q=q, roast_id=roast_id, sort=sort)


# ------------------------------------------------------------------ товари

@api_v1.route('/products')
def list_products():
    """Список товарів із пошуком, фільтром і сортуванням
    ---
    tags:
      - v1 · Товари
    parameters:
      - {name: q, in: query, type: string, description: "Пошук за назвою й описом (без урахування регістру)"}
      - {name: roast, in: query, type: integer, description: "id обсмаження"}
      - name: sort
        in: query
        type: string
        enum: [new, price_asc, price_desc, name]
        default: new
    responses:
      200:
        description: Масив товарів
        schema:
          type: array
          items:
            $ref: '#/definitions/Product'
      400:
        description: Некоректний параметр запиту
        schema:
          $ref: '#/definitions/Error'
    """
    return jsonify([product_v1(p) for p in query_products()])


@api_v1.route('/products/<int:product_id>')
def get_product(product_id):
    """Один товар
    ---
    tags:
      - v1 · Товари
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
    responses:
      200:
        description: Товар
        schema:
          $ref: '#/definitions/Product'
      404:
        description: Товару не існує
        schema:
          $ref: '#/definitions/Error'
    """
    product = models.get_product(product_id)
    if product is None:
        raise not_found('Товар')
    return jsonify(product_v1(product))


@api_v1.route('/products', methods=['POST'])
@admin_required
def create_product():
    """Створити товар (адміністратор)
    ---
    tags:
      - v1 · Товари
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/ProductInput'
    responses:
      201:
        description: Товар створено (заголовок Location вказує на новий ресурс)
        schema:
          $ref: '#/definitions/Product'
      400:
        description: Помилка валідації
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Немає токена
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Не адміністратор
        schema:
          $ref: '#/definitions/Error'
    """
    data = validate(json_body(), PRODUCT_SPEC)
    check_roast_exists(data['roast_id'])
    product_id = models.add_product(**data)
    return created(product_v1(models.get_product(product_id)), f'/api/v1/products/{product_id}')


@api_v1.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def replace_product(product_id):
    """Повністю замінити товар (адміністратор)
    ---
    tags:
      - v1 · Товари
    security:
      - Bearer: []
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/ProductInput'
    responses:
      200:
        description: Товар оновлено
        schema:
          $ref: '#/definitions/Product'
      400:
        description: Помилка валідації
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Товару не існує
        schema:
          $ref: '#/definitions/Error'
    """
    if models.get_product(product_id) is None:
        raise not_found('Товар')
    data = validate(json_body(), PRODUCT_SPEC)
    check_roast_exists(data['roast_id'])
    models.update_product(product_id, **data)
    return jsonify(product_v1(models.get_product(product_id)))


@api_v1.route('/products/<int:product_id>', methods=['PATCH'])
@admin_required
def patch_product(product_id):
    """Частково оновити товар (адміністратор)
    ---
    tags:
      - v1 · Товари
    description: |
      Передайте лише ті поля, які треба змінити, наприклад `{"price": 399}`.
    security:
      - Bearer: []
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            price: {type: number, example: 399}
    responses:
      200:
        description: Товар оновлено
        schema:
          $ref: '#/definitions/Product'
      400:
        description: Помилка валідації
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Товару не існує
        schema:
          $ref: '#/definitions/Error'
    """
    product = models.get_product(product_id)
    if product is None:
        raise not_found('Товар')
    changes = validate(json_body(), PRODUCT_SPEC, partial=True)
    if 'roast_id' in changes:
        check_roast_exists(changes['roast_id'])
    merged = {k: product[k] for k in PRODUCT_SPEC} | changes
    models.update_product(product_id, **merged)
    return jsonify(product_v1(models.get_product(product_id)))


@api_v1.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    """Видалити товар (адміністратор)
    ---
    tags:
      - v1 · Товари
    security:
      - Bearer: []
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
    responses:
      204:
        description: Товар видалено (тіла відповіді немає)
      404:
        description: Товару не існує
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Товар є в замовленнях, видалити не можна
        schema:
          $ref: '#/definitions/Error'
    """
    if models.get_product(product_id) is None:
        raise not_found('Товар')
    try:
        models.delete_product(product_id)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'in_use', 'Товар є в замовленнях, його не можна видалити')
    return '', 204


# --------------------------------------------------------------- обсмаження

@api_v1.route('/roasts')
def list_roasts():
    """Ступені обсмаження
    ---
    tags:
      - v1 · Обсмаження
    responses:
      200:
        description: Масив обсмажень із кількістю товарів
        schema:
          type: array
          items:
            $ref: '#/definitions/Roast'
    """
    return jsonify([roast_dict(r) for r in models.get_roasts()])


@api_v1.route('/roasts/<int:roast_id>')
def get_roast(roast_id):
    """Одне обсмаження
    ---
    tags:
      - v1 · Обсмаження
    parameters:
      - {name: roast_id, in: path, type: integer, required: true}
    responses:
      200:
        description: Обсмаження
        schema:
          $ref: '#/definitions/Roast'
      404:
        description: Не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    roast = next((r for r in models.get_roasts() if r['id'] == roast_id), None)
    if roast is None:
        raise not_found('Обсмаження')
    return jsonify(roast_dict(roast))


@api_v1.route('/roasts', methods=['POST'])
@admin_required
def create_roast():
    """Створити обсмаження (адміністратор)
    ---
    tags:
      - v1 · Обсмаження
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/RoastInput'
    responses:
      201:
        description: Створено
        schema:
          $ref: '#/definitions/Roast'
      400:
        description: Помилка валідації
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Таке обсмаження вже існує
        schema:
          $ref: '#/definitions/Error'
    """
    data = validate(json_body(), ROAST_SPEC)
    try:
        roast_id = models.add_roast(**data)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'duplicate', 'Таке обсмаження вже існує')
    roast = next(r for r in models.get_roasts() if r['id'] == roast_id)
    return created(roast_dict(roast), f'/api/v1/roasts/{roast_id}')


@api_v1.route('/roasts/<int:roast_id>', methods=['PUT'])
@admin_required
def replace_roast(roast_id):
    """Оновити обсмаження (адміністратор)
    ---
    tags:
      - v1 · Обсмаження
    security:
      - Bearer: []
    parameters:
      - {name: roast_id, in: path, type: integer, required: true}
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/RoastInput'
    responses:
      200:
        description: Оновлено
        schema:
          $ref: '#/definitions/Roast'
      400:
        description: Помилка валідації
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Не знайдено
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Назва вже зайнята
        schema:
          $ref: '#/definitions/Error'
    """
    if models.get_roast(roast_id) is None:
        raise not_found('Обсмаження')
    data = validate(json_body(), ROAST_SPEC)
    try:
        models.update_roast(roast_id, **data)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'duplicate', 'Таке обсмаження вже існує')
    roast = next(r for r in models.get_roasts() if r['id'] == roast_id)
    return jsonify(roast_dict(roast))


@api_v1.route('/roasts/<int:roast_id>', methods=['DELETE'])
@admin_required
def delete_roast(roast_id):
    """Видалити обсмаження (адміністратор)
    ---
    tags:
      - v1 · Обсмаження
    security:
      - Bearer: []
    parameters:
      - {name: roast_id, in: path, type: integer, required: true}
    responses:
      204:
        description: Видалено
      404:
        description: Не знайдено
        schema:
          $ref: '#/definitions/Error'
      409:
        description: До обсмаження прив'язані товари
        schema:
          $ref: '#/definitions/Error'
    """
    if models.get_roast(roast_id) is None:
        raise not_found('Обсмаження')
    try:
        models.delete_roast(roast_id)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'in_use', "До обсмаження прив'язані товари, його не можна видалити")
    return '', 204
