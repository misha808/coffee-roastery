"""REST API (лабораторна робота 05).

Два Blueprint-и — дві версії API:
  /api/v1/...  базова версія: «плоскі» відповіді (список або об'єкт), помилка: {"error": "текст"}
  /api/v2/...  розширена: відповідь у конверті {"data": ..., "meta": ...}, пагінація,
               вкладені об'єкти, структурована помилка {"error": {"code", "message", "details"}}
"""
from flask import Blueprint

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')
api_v2 = Blueprint('api_v2', __name__, url_prefix='/api/v2')


@api_v1.after_request
def mark_v1(response):
    response.headers['X-API-Version'] = '1'
    return response


@api_v2.after_request
def mark_v2(response):
    response.headers['X-API-Version'] = '2'
    return response


# Імпорт модулів наприкінці: вони реєструють свої маршрути в api_v1 / api_v2 (див. вище)
from . import auth, catalog, orders, extras, v2  # noqa: E402,F401
