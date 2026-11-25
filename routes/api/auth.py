"""Автентифікація API: реєстрація, вхід (видача токена), поточний користувач."""
import sqlite3

from flask import g, jsonify

import models
from . import api_v1
from .common import (TOKEN_MAX_AGE, ApiError, created, json_body, make_token,
                     token_required, user_dict, validate)

CREDENTIALS_SPEC = {
    'username': {'type': 'str', 'min': 3, 'max': 30, 'pattern': r'[\w.\-]+',
                 'message': 'Лише літери, цифри, крапка, дефіс і підкреслення'},
    'password': {'type': 'str', 'min': 6, 'max': 128, 'strip': False},
}


@api_v1.route('/auth/register', methods=['POST'])
def register():
    """Реєстрація клієнта
    ---
    tags:
      - v1 · Автентифікація
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/Credentials'
    responses:
      201:
        description: Акаунт створено; у відповіді токен для наступних запитів
        schema:
          $ref: '#/definitions/TokenResponse'
      400:
        description: Помилка валідації (короткий пароль, недопустимі символи в логіні)
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Логін уже зайнятий
        schema:
          $ref: '#/definitions/Error'
    """
    data = validate(json_body(), CREDENTIALS_SPEC)
    try:
        user_id = models.create_user(data['username'], data['password'])
    except sqlite3.IntegrityError:
        raise ApiError(409, 'username_taken', 'Цей логін уже зайнятий')
    user = models.get_user(user_id)
    body = {'token': make_token(user_id), 'token_type': 'Bearer', 'expires_in': TOKEN_MAX_AGE, 'user': user_dict(user)}
    return created(body, '/api/v1/me')


@api_v1.route('/auth/login', methods=['POST'])
def login():
    """Вхід: отримати токен
    ---
    tags:
      - v1 · Автентифікація
    description: |
      Повертає токен. Далі його передають у заголовку `Authorization: Bearer <token>`.
      У Swagger UI натисніть **Authorize** і вставте `Bearer <token>`.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/Credentials'
    responses:
      200:
        description: Токен видано
        schema:
          $ref: '#/definitions/TokenResponse'
      400:
        description: Не передано логін або пароль
        schema:
          $ref: '#/definitions/Error'
      401:
        description: Невірний логін або пароль
        schema:
          $ref: '#/definitions/Error'
    """
    raw = json_body()
    data = validate(raw, {'username': {'type': 'str', 'min': 1}, 'password': {'type': 'str', 'min': 1, 'strip': False}})
    user = models.authenticate(data['username'], data['password'])
    if user is None:
        raise ApiError(401, 'invalid_credentials', 'Невірний логін або пароль')
    return jsonify({'token': make_token(user['id']), 'token_type': 'Bearer',
                    'expires_in': TOKEN_MAX_AGE, 'user': user_dict(user)})


@api_v1.route('/me')
@token_required
def me():
    """Поточний користувач
    ---
    tags:
      - v1 · Автентифікація
    security:
      - Bearer: []
    responses:
      200:
        description: Дані користувача, якому належить токен
        schema:
          $ref: '#/definitions/User'
      401:
        description: Немає токена або він недійсний
        schema:
          $ref: '#/definitions/Error'
    """
    return jsonify(user_dict(g.api_user))
