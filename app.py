import os
import re
from datetime import datetime

from flasgger import Swagger
from flask import Flask, render_template, request, session
from werkzeug.exceptions import HTTPException

import models
from routes import admin_bp, api_v1, api_v2, auth_bp, feedback_bp, shop_bp
from routes.api.common import ApiError, handle_api_error, handle_http_error
from routes.api.docs import SWAGGER_CONFIG, SWAGGER_TEMPLATE

app = Flask(__name__)
app.json.ensure_ascii = False  # кирилиця в JSON-відповідях читається як є, а не як \uXXXX
# Шлях до файлу БД зберігаємо в конфігурації (поруч з app.py, незалежно від поточної теки)
app.config['DATABASE'] = os.environ.get('DATABASE', os.path.join(app.root_path, 'db.sqlite'))
# Ключ підписує сесію (кошик, вхід). Для реального сайту задайте власний через змінну середовища SECRET_KEY.
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-me')
# Адміністратор, який створюється при першому запуску
app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Закриваємо з'єднання з БД після кожного запиту
app.teardown_appcontext(models.close_db)

# Створюємо таблиці під час запуску (якщо їх ще немає)
with app.app_context():
    models.init_db()

app.register_blueprint(auth_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(shop_bp)
app.register_blueprint(api_v1)  # REST API, версія 1: /api/v1/...
app.register_blueprint(api_v2)  # REST API, версія 2: /api/v2/...

# Документація API (Swagger UI): http://127.0.0.1:5000/apidocs/
Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)

# Помилки API віддаємо у форматі JSON
app.register_error_handler(ApiError, handle_api_error)


@app.template_filter('money')
def money(value):
    """Форматує суму: 1299.9 -> '1299.90 грн'."""
    return f'{value:.2f} грн'


@app.template_filter('ink_on')
def ink_on(color):
    """Колір тексту (темний або білий), який читається на фоні `color` формату #rrggbb."""
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color or ''):
        return '#ffffff'
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return '#1d1a16' if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else '#ffffff'


@app.context_processor
def inject_globals():
    """Змінні, доступні в усіх шаблонах."""
    return {
        'current_year': datetime.now().year,
        'cart_count': sum(session.get('cart', {}).values()),
        'is_admin': session.get('role') == 'admin',
        'username': session.get('username'),
    }


@app.route('/')
def home():
    return render_template(
        'home.html',
        roasts=models.get_roasts(),
        products=models.get_products(sort='new')[:3],
        reviews=models.get_feedback(limit=3),
    )


@app.errorhandler(HTTPException)
def error_page(error):
    """Для адрес /api/... — JSON, для сайту — HTML-сторінка помилки."""
    if request.path.startswith('/api/'):
        return handle_http_error(error)
    if error.code in (403, 404):
        return render_template('error.html', error=error), error.code
    return error


if __name__ == '__main__':
    app.run(debug=True)
