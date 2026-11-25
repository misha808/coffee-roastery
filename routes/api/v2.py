"""Версія 2 API: відповіді в конверті {"data", "meta"}, пагінація, вкладені об'єкти,
структурована помилка. Записувальні операції (POST/PUT/PATCH/DELETE) лишаються у v1."""
from flask import g, jsonify, request

import models
from . import api_v2
from .catalog import query_products
from .common import (ApiError, not_found, order_full, order_summary, paginate, product_v2,
                     roast_dict, token_required)
from .orders import load_order_for_user


@api_v2.route('/products')
def list_products():
    """Товари з пагінацією (v2)
    ---
    tags:
      - v2 · Каталог і замовлення
    description: |
      Відмінності від v1: відповідь у конверті `{data, meta}`, обсмаження — вкладений об'єкт,
      пагінація `page` / `per_page`, помилки у форматі `{error: {code, message, details}}`.
    parameters:
      - {name: q, in: query, type: string}
      - {name: roast, in: query, type: integer}
      - {name: sort, in: query, type: string, enum: [new, price_asc, price_desc, name]}
      - {name: page, in: query, type: integer, default: 1}
      - {name: per_page, in: query, type: integer, default: 10}
    responses:
      200:
        description: Сторінка товарів
        schema:
          $ref: '#/definitions/ProductPageV2'
      400:
        description: Некоректні параметри
        schema:
          $ref: '#/definitions/ErrorV2'
    """
    data, meta = paginate(query_products(), product_v2)
    return jsonify({'data': data, 'meta': meta})


@api_v2.route('/products/<int:product_id>')
def get_product(product_id):
    """Один товар (v2)
    ---
    tags:
      - v2 · Каталог і замовлення
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
    responses:
      200:
        description: Товар у конверті
        schema:
          type: object
          properties:
            data:
              $ref: '#/definitions/ProductV2'
      404:
        description: Не знайдено
        schema:
          $ref: '#/definitions/ErrorV2'
    """
    product = models.get_product(product_id)
    if product is None:
        raise not_found('Товар')
    return jsonify({'data': product_v2(product)})


@api_v2.route('/roasts')
def list_roasts():
    """Ступені обсмаження (v2)
    ---
    tags:
      - v2 · Каталог і замовлення
    responses:
      200:
        description: Масив у конверті з кількістю елементів
        schema:
          type: object
          properties:
            data:
              type: array
              items:
                $ref: '#/definitions/Roast'
            meta:
              type: object
              properties:
                total: {type: integer, example: 3}
    """
    roasts = [roast_dict(r) for r in models.get_roasts()]
    return jsonify({'data': roasts, 'meta': {'total': len(roasts)}})


@api_v2.route('/orders')
@token_required
def list_orders():
    """Замовлення з пагінацією (v2)
    ---
    tags:
      - v2 · Каталог і замовлення
    security:
      - Bearer: []
    parameters:
      - {name: page, in: query, type: integer, default: 1}
      - {name: per_page, in: query, type: integer, default: 10}
    responses:
      200:
        description: Сторінка замовлень (клієнт — свої, адміністратор — усі)
        schema:
          type: object
          properties:
            data:
              type: array
              items:
                $ref: '#/definitions/OrderSummary'
            meta:
              type: object
      401:
        description: Немає токена
        schema:
          $ref: '#/definitions/ErrorV2'
    """
    orders = models.get_orders() if g.api_user['role'] == 'admin' else models.get_user_orders(g.api_user['id'])
    data, meta = paginate(orders, order_summary)
    return jsonify({'data': data, 'meta': meta})


@api_v2.route('/orders/<int:order_id>')
@token_required
def get_order(order_id):
    """Одне замовлення (v2)
    ---
    tags:
      - v2 · Каталог і замовлення
    security:
      - Bearer: []
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
    responses:
      200:
        description: Замовлення з позиціями у конверті
        schema:
          type: object
          properties:
            data:
              $ref: '#/definitions/Order'
      404:
        description: Немає такого замовлення (або воно чуже)
        schema:
          $ref: '#/definitions/ErrorV2'
    """
    return jsonify({'data': order_full(*load_order_for_user(order_id))})
