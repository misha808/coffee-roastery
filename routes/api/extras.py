"""Промокоди, відгуки та користувачі (версія 1)."""
import sqlite3

from flask import g, jsonify, request

import models
from . import api_v1
from .common import (ApiError, admin_required, created, feedback_dict, json_body, not_found,
                     promo_dict, token_required, user_dict, validate)

PROMO_SPEC = {
    'code': {'type': 'str', 'min': 3, 'max': 20, 'pattern': r'[A-Za-z0-9_\-]+',
             'message': 'Лише латиниця, цифри, «-» та «_»'},
    'discount_percent': {'type': 'int', 'min': 1, 'max': 90},
}
FEEDBACK_SPEC = {'message': {'type': 'str', 'min': 3, 'max': 1000}}


# --------------------------------------------------------------- промокоди

@api_v1.route('/promos/validate')
def validate_promo():
    """Перевірити промокод
    ---
    tags:
      - v1 · Промокоди
    parameters:
      - {name: code, in: query, type: string, required: true, example: COFFEE10}
    responses:
      200:
        description: Промокод діє
        schema:
          $ref: '#/definitions/Promo'
      404:
        description: Промокоду немає або він вимкнений
        schema:
          $ref: '#/definitions/Error'
    """
    promo = models.get_active_promo(request.args.get('code', ''))
    if promo is None:
        raise not_found('Промокод')
    return jsonify(promo_dict(promo))


@api_v1.route('/promos')
@admin_required
def list_promos():
    """Усі промокоди (адміністратор)
    ---
    tags:
      - v1 · Промокоди
    security:
      - Bearer: []
    responses:
      200:
        description: Масив промокодів
        schema:
          type: array
          items:
            $ref: '#/definitions/Promo'
      403:
        description: Не адміністратор
        schema:
          $ref: '#/definitions/Error'
    """
    return jsonify([promo_dict(p) for p in models.get_promos()])


@api_v1.route('/promos', methods=['POST'])
@admin_required
def create_promo():
    """Створити промокод (адміністратор)
    ---
    tags:
      - v1 · Промокоди
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/PromoInput'
    responses:
      201:
        description: Створено
        schema:
          $ref: '#/definitions/Promo'
      400:
        description: Помилка валідації
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Такий код уже є
        schema:
          $ref: '#/definitions/Error'
    """
    data = validate(json_body(), PROMO_SPEC)
    try:
        promo_id = models.add_promo(**data)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'duplicate', 'Такий промокод уже існує')
    promo = next(p for p in models.get_promos() if p['id'] == promo_id)
    return created(promo_dict(promo), '/api/v1/promos')


@api_v1.route('/promos/<int:promo_id>', methods=['DELETE'])
@admin_required
def delete_promo(promo_id):
    """Видалити промокод (адміністратор)
    ---
    tags:
      - v1 · Промокоди
    security:
      - Bearer: []
    parameters:
      - {name: promo_id, in: path, type: integer, required: true}
    responses:
      204:
        description: Видалено
      404:
        description: Не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    if not any(p['id'] == promo_id for p in models.get_promos()):
        raise not_found('Промокод')
    models.delete_promo(promo_id)
    return '', 204


# ------------------------------------------------------------------ відгуки

@api_v1.route('/feedback')
def list_feedback():
    """Відгуки клієнтів
    ---
    tags:
      - v1 · Відгуки
    responses:
      200:
        description: Масив відгуків, нові першими
        schema:
          type: array
          items:
            $ref: '#/definitions/Feedback'
    """
    return jsonify([feedback_dict(f) for f in models.get_feedback()])


@api_v1.route('/feedback', methods=['POST'])
@token_required
def create_feedback():
    """Залишити відгук
    ---
    tags:
      - v1 · Відгуки
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/FeedbackInput'
    responses:
      201:
        description: Відгук додано
        schema:
          $ref: '#/definitions/Feedback'
      400:
        description: Помилка валідації (від 3 до 1000 символів)
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Немає токена
        schema:
          $ref: '#/definitions/Error'
    """
    data = validate(json_body(), FEEDBACK_SPEC)
    feedback_id = models.add_feedback(g.api_user['id'], data['message'])
    review = next(f for f in models.get_feedback() if f['id'] == feedback_id)
    return created(feedback_dict(review), '/api/v1/feedback')


@api_v1.route('/feedback/<int:feedback_id>', methods=['DELETE'])
@admin_required
def delete_feedback(feedback_id):
    """Видалити відгук (адміністратор)
    ---
    tags:
      - v1 · Відгуки
    security:
      - Bearer: []
    parameters:
      - {name: feedback_id, in: path, type: integer, required: true}
    responses:
      204:
        description: Видалено
      404:
        description: Не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    if not any(f['id'] == feedback_id for f in models.get_feedback()):
        raise not_found('Відгук')
    models.delete_feedback(feedback_id)
    return '', 204


# ------------------------------------------------------------- користувачі

@api_v1.route('/users')
@admin_required
def list_users():
    """Користувачі (адміністратор)
    ---
    tags:
      - v1 · Користувачі
    security:
      - Bearer: []
    responses:
      200:
        description: Масив користувачів (без паролів)
        schema:
          type: array
          items:
            $ref: '#/definitions/User'
      403:
        description: Не адміністратор
        schema:
          $ref: '#/definitions/Error'
    """
    return jsonify([user_dict(u) for u in models.get_users()])


@api_v1.route('/users/<int:user_id>/role', methods=['PATCH'])
@admin_required
def set_role(user_id):
    """Змінити роль користувача (адміністратор)
    ---
    tags:
      - v1 · Користувачі
    security:
      - Bearer: []
    parameters:
      - {name: user_id, in: path, type: integer, required: true}
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [role]
          properties:
            role: {type: string, enum: [client, admin], example: admin}
    responses:
      200:
        description: Роль змінено
        schema:
          $ref: '#/definitions/User'
      400:
        description: Невідома роль
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Користувача не знайдено
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Не можна змінити власну роль
        schema:
          $ref: '#/definitions/Error'
    """
    if models.get_user(user_id) is None:
        raise not_found('Користувача')
    if user_id == g.api_user['id']:
        raise ApiError(409, 'conflict', 'Не можна змінити власну роль')
    role = json_body().get('role')
    if role not in models.ROLES:
        raise ApiError(400, 'validation_error', 'Помилка валідації вхідних даних',
                       {'role': f'Допустимі значення: {", ".join(models.ROLES)}'})
    models.set_user_role(user_id, role)
    return jsonify(user_dict(models.get_user(user_id)))
