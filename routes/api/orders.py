"""Замовлення (версія 1): створення з кошика-JSON, перегляд, керування статусом."""
from flask import g, jsonify, request

import models
from . import api_v1
from .common import (ApiError, admin_required, created, json_body, not_found, order_full,
                     order_summary, token_required, validate)

ORDER_SPEC = {
    'address': {'type': 'str', 'min': 5, 'max': 300},
    'promo_code': {'type': 'str', 'max': 20, 'required': False, 'default': None},
}
ITEM_SPEC = {
    'product_id': {'type': 'int', 'min': 1},
    'quantity': {'type': 'int', 'min': 1, 'max': 99},
}


def parse_order_body():
    """Перевіряє тіло замовлення. Повертає (адреса, промокод, кошик {id: кількість})."""
    raw = json_body()
    data = validate(raw, ORDER_SPEC)

    items = raw.get('items')
    if not isinstance(items, list) or not items:
        raise ApiError(400, 'validation_error', 'Помилка валідації вхідних даних',
                       {'items': 'Потрібен непорожній масив позицій'})

    errors, cart = {}, {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors[f'items[{index}]'] = 'Має бути об\'єктом {product_id, quantity}'
            continue
        try:
            clean = validate(item, ITEM_SPEC)
        except ApiError as error:
            errors.update({f'items[{index}].{k}': v for k, v in error.details.items()})
            continue
        cart[clean['product_id']] = min(cart.get(clean['product_id'], 0) + clean['quantity'], 99)

    existing = {p['id'] for p in models.get_products_by_ids(cart.keys())}
    for product_id in cart:
        if product_id not in existing:
            errors[f'product_id={product_id}'] = 'Такого товару не існує'
    if errors:
        raise ApiError(400, 'validation_error', 'Помилка валідації вхідних даних', errors)

    promo_code = data['promo_code']
    if promo_code and models.get_active_promo(promo_code) is None:
        raise ApiError(400, 'validation_error', 'Помилка валідації вхідних даних',
                       {'promo_code': 'Промокод не існує або не діє'})
    return data['address'], promo_code, cart


def load_order_for_user(order_id):
    """Замовлення, яке має право бачити поточний користувач (інакше 404, як і на сайті)."""
    order, items = models.get_order_details(order_id)
    if order is None or (order['user_id'] != g.api_user['id'] and g.api_user['role'] != 'admin'):
        raise not_found('Замовлення')
    return order, items


@api_v1.route('/orders')
@token_required
def list_orders():
    """Список замовлень
    ---
    tags:
      - v1 · Замовлення
    description: Клієнт бачить свої замовлення, адміністратор — усі (можна фільтрувати за статусом).
    security:
      - Bearer: []
    parameters:
      - {name: status, in: query, type: string, description: "Лише для адміністратора"}
    responses:
      200:
        description: Масив замовлень (без позицій)
        schema:
          type: array
          items:
            $ref: '#/definitions/OrderSummary'
      401:
        description: Немає токена
        schema:
          $ref: '#/definitions/Error'
    """
    status = request.args.get('status')
    if status and status not in models.ORDER_STATUSES:
        raise ApiError(400, 'validation_error', 'Некоректні параметри',
                       {'status': f'Допустимі значення: {", ".join(models.ORDER_STATUSES)}'})
    if g.api_user['role'] == 'admin':
        orders = models.get_orders(status or None)
    else:
        orders = [o for o in models.get_user_orders(g.api_user['id']) if not status or o['status'] == status]
    return jsonify([order_summary(o) for o in orders])


@api_v1.route('/orders/<int:order_id>')
@token_required
def get_order(order_id):
    """Одне замовлення з позиціями
    ---
    tags:
      - v1 · Замовлення
    security:
      - Bearer: []
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
    responses:
      200:
        description: Замовлення
        schema:
          $ref: '#/definitions/Order'
      404:
        description: Немає такого замовлення (або воно чуже)
        schema:
          $ref: '#/definitions/Error'
    """
    return jsonify(order_full(*load_order_for_user(order_id)))


@api_v1.route('/orders', methods=['POST'])
@token_required
def create_order():
    """Оформити замовлення
    ---
    tags:
      - v1 · Замовлення
    description: |
      Ціни беруться з бази, а не з запиту. Знижка рахується за промокодом.
      Дублікати товарів у `items` об'єднуються.
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/OrderInput'
    responses:
      201:
        description: Замовлення створено
        schema:
          $ref: '#/definitions/Order'
      400:
        description: Помилка валідації (порожній кошик, невідомий товар, невірний промокод)
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Немає токена
        schema:
          $ref: '#/definitions/Error'
    """
    address, promo_code, cart = parse_order_body()
    order_id = models.create_order(g.api_user['id'], address, cart, promo_code)
    return created(order_full(*models.get_order_details(order_id)), f'/api/v1/orders/{order_id}')


@api_v1.route('/orders/<int:order_id>/status', methods=['PATCH'])
@admin_required
def update_status(order_id):
    """Змінити статус замовлення (адміністратор)
    ---
    tags:
      - v1 · Замовлення
    security:
      - Bearer: []
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/StatusInput'
    responses:
      200:
        description: Статус оновлено
        schema:
          $ref: '#/definitions/Order'
      400:
        description: Невідомий статус
        schema:
          $ref: '#/definitions/Error'
      403:
        description: Не адміністратор
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Замовлення не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    order, _ = models.get_order_details(order_id)
    if order is None:
        raise not_found('Замовлення')
    status = json_body().get('status')
    if status not in models.ORDER_STATUSES:
        raise ApiError(400, 'validation_error', 'Помилка валідації вхідних даних',
                       {'status': f'Допустимі значення: {", ".join(models.ORDER_STATUSES)}'})
    models.update_order_status(order_id, status)
    return jsonify(order_full(*models.get_order_details(order_id)))


@api_v1.route('/orders/<int:order_id>', methods=['DELETE'])
@admin_required
def delete_order(order_id):
    """Видалити замовлення (адміністратор)
    ---
    tags:
      - v1 · Замовлення
    security:
      - Bearer: []
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
    responses:
      204:
        description: Видалено
      404:
        description: Не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    order, _ = models.get_order_details(order_id)
    if order is None:
        raise not_found('Замовлення')
    models.delete_order(order_id)
    return '', 204
