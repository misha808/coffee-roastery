"""Робота з базою даних SQLite: підключення, схема таблиць і функції доступу до даних.

З'єднання створюється один раз на запит, зберігається в об'єкті `g`
і закривається автоматично функцією `close_db` (див. app.py).
Усі SQL-запити параметризовані: значення передаються через `?`,
а не підставляються в рядок, тому SQL-ін'єкції неможливі.
"""
import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import check_password_hash, generate_password_hash

# Допустимі статуси замовлення. Перший використовується для нових замовлень.
ORDER_STATUSES = ['Нове', 'Оплачено', 'В обробці', 'Відправлено', 'Доставлено', 'Скасовано']
ROLES = ['client', 'admin']

# Дозволені варіанти сортування каталогу. У SQL підставляється лише значення з цього
# словника (ключ приходить від користувача, але сам текст SQL — наш), тому це безпечно.
PRODUCT_SORTS = {
    'new': 'p.id DESC',
    'price_asc': 'p.price ASC',
    'price_desc': 'p.price DESC',
    'name': 'p.name COLLATE NOCASE ASC',
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'client' CHECK (role IN ('client', 'admin')),
    created_at    TEXT NOT NULL
);

-- Рівень 2: додаткова таблиця предметної області (ступені обсмаження кави).
-- color потрібен для візуального відображення шкали обсмаження на сайті.
CREATE TABLE IF NOT EXISTS roast_levels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    color       TEXT NOT NULL DEFAULT '#8a6a4f'
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price       REAL NOT NULL CHECK (price >= 0),
    roast_id    INTEGER NOT NULL,
    -- Ступінь обсмаження, до якого прив'язані товари, видалити не можна
    FOREIGN KEY (roast_id) REFERENCES roast_levels (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Рівень 3: промокоди зі знижкою у відсотках
CREATE TABLE IF NOT EXISTS promo_codes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT NOT NULL UNIQUE,
    discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 90),
    active           INTEGER NOT NULL DEFAULT 1
);

-- Код і відсоток знижки копіюються в замовлення: історія не зміниться,
-- навіть якщо промокод потім вимкнуть або видалять.
CREATE TABLE IF NOT EXISTS orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    address          TEXT NOT NULL,
    promo_code       TEXT,
    discount_percent INTEGER NOT NULL DEFAULT 0,
    total_price      REAL NOT NULL,
    status           TEXT NOT NULL,
    date             TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT
);

-- Проміжна таблиця зв'язку «багато-до-багатьох» між замовленнями й товарами.
-- unit_price зберігає ціну на момент замовлення.
CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id)   REFERENCES orders (id)   ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT
);
"""

DEFAULT_ROASTS = [
    ('Світле', 'Яскрава кислотність, фруктові й квіткові ноти', '#d8a94a'),
    ('Середнє', 'Баланс солодкості й кислотності, горіхові ноти', '#9b5f30'),
    ('Темне', 'Насичений смак, гіркуватість, ноти шоколаду', '#3a2118'),
]


# Демо-каталог: додається автоматично, коли база створюється з нуля
DEFAULT_PRODUCTS = [
    ('Ефіопія Іргачефф', 'Бергамот, жасмин, лимонна цедра', 420, 'Світле'),
    ('Кенія AA', 'Чорна смородина, томатна кислинка', 460, 'Світле'),
    ('Руанда Мусаса', 'Червоні ягоди, цукрова тростина, чай', 410, 'Світле'),
    ('Панама Гейша', 'Персик, квіти, мед', 690, 'Світле'),
    ('Колумбія Уїла', 'Карамель, червоне яблуко, какао', 380, 'Середнє'),
    ('Гватемала Антигуа', 'Молочний шоколад, горіхи, спеції', 400, 'Середнє'),
    ('Коста-Рика Тарразу', 'Мед, апельсин, мигдаль', 430, 'Середнє'),
    ('Сальвадор Пакамара', 'Шоколад, фундук, дика вишня', 395, 'Середнє'),
    ('Бразилія Сантос', 'Темний шоколад, арахіс, тютюн', 340, 'Темне'),
    ('Еспресо-бленд', 'Густе тіло, гірка карамель, димні ноти', 360, 'Темне'),
    ('Індія Мансун Малабар', 'Спеції, кедр, землистий шоколад', 375, 'Темне'),
    ('Суматра Мандхелінг', 'Тютюн, какао, суха деревина', 385, 'Темне'),
]


def ensure_default_products():
    """Додає демо-каву, якої ще немає в базі (порівняння за назвою). Повертає кількість доданих."""
    db = get_db()
    with db:
        before = db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        db.executemany(
            'INSERT INTO products (name, description, price, roast_id) '
            'SELECT ?, ?, ?, (SELECT id FROM roast_levels WHERE name = ?) '
            'WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = ?)',
            [(n, d, p, r, n) for n, d, p, r in DEFAULT_PRODUCTS],
        )
        return db.execute('SELECT COUNT(*) FROM products').fetchone()[0] - before


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------- з'єднання

def get_db():
    """Повертає з'єднання для поточного запиту (створює, якщо його ще немає)."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row            # рядки читаються як row['name']
        g.db.execute('PRAGMA foreign_keys = ON')  # SQLite за замовчуванням ігнорує FOREIGN KEY
        # LIKE у SQLite не розрізняє регістр лише для латиниці. Для пошуку кирилицею
        # реєструємо власну функцію нижнього регістру.
        g.db.create_function('py_lower', 1, lambda s: s.lower() if s else s)
    return g.db


def close_db(exception=None):
    """Закриває з'єднання наприкінці запиту (реєструється через teardown_appcontext)."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Створює таблиці, якщо їх ще немає, і початкові дані (обсмаження, адмін). Безпечно викликати повторно."""
    db = get_db()
    db.executescript(SCHEMA)
    with db:
        if db.execute('SELECT COUNT(*) FROM roast_levels').fetchone()[0] == 0:
            db.executemany('INSERT INTO roast_levels (name, description, color) VALUES (?, ?, ?)', DEFAULT_ROASTS)
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            db.execute(
                'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
                (current_app.config['ADMIN_USERNAME'],
                 generate_password_hash(current_app.config['ADMIN_PASSWORD'], method='pbkdf2:sha256'),
                 'admin', now()),
            )
            # Нова база: одразу додаємо демо-каву й промокод, щоб каталог не був порожнім
            db.execute("INSERT OR IGNORE INTO promo_codes (code, discount_percent) VALUES ('COFFEE10', 10)")
    if db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
        ensure_default_products()


# ------------------------------------------------------------- користувачі

def create_user(username, password, role='client'):
    """Створює користувача. Пароль зберігається лише у вигляді хешу.
    Якщо логін зайнятий, кидає sqlite3.IntegrityError."""
    db = get_db()
    with db:
        cur = db.execute(
            'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
            (username, generate_password_hash(password, method='pbkdf2:sha256'), role, now()),
        )
    return cur.lastrowid


def get_user(user_id):
    return get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()


def authenticate(username, password):
    """Повертає користувача, якщо логін і пароль вірні, інакше None."""
    user = get_db().execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if user is not None and check_password_hash(user['password_hash'], password):
        return user
    return None


def get_users():
    return get_db().execute(
        'SELECT u.*, (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS orders_count '
        'FROM users u ORDER BY u.id'
    ).fetchall()


def set_user_role(user_id, role):
    if role not in ROLES:
        raise ValueError(f'Невідома роль: {role}')
    db = get_db()
    with db:
        db.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))


# ------------------------------------------------------ ступені обсмаження

def get_roasts():
    """Усі ступені обсмаження разом із кількістю товарів (LEFT JOIN + GROUP BY)."""
    return get_db().execute(
        'SELECT r.*, COUNT(p.id) AS products_count '
        'FROM roast_levels r LEFT JOIN products p ON p.roast_id = r.id '
        'GROUP BY r.id ORDER BY r.id'
    ).fetchall()


def get_roast(roast_id):
    return get_db().execute('SELECT * FROM roast_levels WHERE id = ?', (roast_id,)).fetchone()


def add_roast(name, description, color):
    db = get_db()
    with db:
        cur = db.execute('INSERT INTO roast_levels (name, description, color) VALUES (?, ?, ?)',
                   (name, description, color))
    return cur.lastrowid


def update_roast(roast_id, name, description, color):
    db = get_db()
    with db:
        db.execute('UPDATE roast_levels SET name = ?, description = ?, color = ? WHERE id = ?',
                   (name, description, color, roast_id))


def delete_roast(roast_id):
    """Кидає sqlite3.IntegrityError, якщо до обсмаження прив'язані товари (ON DELETE RESTRICT)."""
    db = get_db()
    with db:
        db.execute('DELETE FROM roast_levels WHERE id = ?', (roast_id,))


# ------------------------------------------------------------------- товари

PRODUCT_SELECT = (
    'SELECT p.*, r.name AS roast_name, r.color AS roast_color '
    'FROM products p JOIN roast_levels r ON r.id = p.roast_id '
)


def get_products(q=None, roast_id=None, sort='new'):
    """Каталог із пошуком за назвою/описом, фільтром за обсмаженням і сортуванням."""
    sql = PRODUCT_SELECT
    where, params = [], []
    if q:
        where.append('(py_lower(p.name) LIKE ? OR py_lower(p.description) LIKE ?)')
        params += [f'%{q.lower()}%'] * 2
    if roast_id:
        where.append('p.roast_id = ?')
        params.append(roast_id)
    if where:
        sql += 'WHERE ' + ' AND '.join(where) + ' '
    sql += 'ORDER BY ' + PRODUCT_SORTS.get(sort, PRODUCT_SORTS['new'])
    return get_db().execute(sql, params).fetchall()


def get_product(product_id):
    return get_db().execute(PRODUCT_SELECT + 'WHERE p.id = ?', (product_id,)).fetchone()


def get_products_by_ids(ids):
    """Товари за списком id. Кількість `?` будуємо за довжиною списку, самі значення — параметри."""
    ids = list(ids)
    if not ids:
        return []
    placeholders = ','.join('?' * len(ids))
    return get_db().execute(PRODUCT_SELECT + f'WHERE p.id IN ({placeholders}) ORDER BY p.id', ids).fetchall()


def add_product(name, description, price, roast_id):
    db = get_db()
    with db:
        cur = db.execute('INSERT INTO products (name, description, price, roast_id) VALUES (?, ?, ?, ?)',
                   (name, description, price, roast_id))
    return cur.lastrowid


def update_product(product_id, name, description, price, roast_id):
    db = get_db()
    with db:
        db.execute('UPDATE products SET name = ?, description = ?, price = ?, roast_id = ? WHERE id = ?',
                   (name, description, price, roast_id, product_id))


def delete_product(product_id):
    """Кидає sqlite3.IntegrityError, якщо товар є в замовленнях (ON DELETE RESTRICT)."""
    db = get_db()
    with db:
        db.execute('DELETE FROM products WHERE id = ?', (product_id,))


# ------------------------------------------------------------------ відгуки

def add_feedback(user_id, message):
    db = get_db()
    with db:
        cur = db.execute('INSERT INTO feedback (user_id, message, created_at) VALUES (?, ?, ?)',
                   (user_id, message, now()))
    return cur.lastrowid


def get_feedback(limit=None):
    sql = ('SELECT f.*, u.username FROM feedback f JOIN users u ON u.id = f.user_id '
           'ORDER BY f.id DESC')
    if limit:
        return get_db().execute(sql + ' LIMIT ?', (limit,)).fetchall()
    return get_db().execute(sql).fetchall()


def delete_feedback(feedback_id):
    db = get_db()
    with db:
        db.execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))


# --------------------------------------------------------------- промокоди

def get_promos():
    return get_db().execute('SELECT * FROM promo_codes ORDER BY id DESC').fetchall()


def get_active_promo(code):
    """Активний промокод за текстом (регістр не важливий) або None."""
    if not code:
        return None
    return get_db().execute(
        'SELECT * FROM promo_codes WHERE code = ? COLLATE NOCASE AND active = 1', (code.strip(),)
    ).fetchone()


def add_promo(code, discount_percent):
    """Кидає sqlite3.IntegrityError, якщо такий код уже є."""
    db = get_db()
    with db:
        cur = db.execute('INSERT INTO promo_codes (code, discount_percent) VALUES (?, ?)',
                   (code.upper(), discount_percent))
    return cur.lastrowid


def toggle_promo(promo_id):
    db = get_db()
    with db:
        db.execute('UPDATE promo_codes SET active = 1 - active WHERE id = ?', (promo_id,))


def delete_promo(promo_id):
    db = get_db()
    with db:
        db.execute('DELETE FROM promo_codes WHERE id = ?', (promo_id,))


# --------------------------------------------------------------- замовлення

def calc_totals(subtotal, promo):
    """Повертає (знижка в грн, підсумок). `promo` — рядок промокоду з БД або None."""
    percent = promo['discount_percent'] if promo else 0
    discount = round(subtotal * percent / 100, 2)
    return discount, round(subtotal - discount, 2)


def create_order(user_id, address, cart, promo_code=None):
    """Створює замовлення з кошика `{id товару: кількість}`.

    Ціни й знижка беруться з бази, а не з даних браузера, а замовлення та його позиції
    зберігаються однією транзакцією: або запишеться все, або нічого.
    Повертає id нового замовлення.
    """
    products = get_products_by_ids(cart.keys())
    if not products:
        raise ValueError('Кошик порожній')

    promo = get_active_promo(promo_code)
    subtotal = round(sum(p['price'] * cart[p['id']] for p in products), 2)
    _, total = calc_totals(subtotal, promo)

    db = get_db()
    with db:
        cur = db.execute(
            'INSERT INTO orders (user_id, address, promo_code, discount_percent, total_price, status, date) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (user_id, address, promo['code'] if promo else None,
             promo['discount_percent'] if promo else 0, total, ORDER_STATUSES[0], now()),
        )
        order_id = cur.lastrowid
        db.executemany(
            'INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)',
            [(order_id, p['id'], cart[p['id']], p['price']) for p in products],
        )
    return order_id


ORDER_SELECT = (
    'SELECT o.*, u.username, '
    '(SELECT GROUP_CONCAT(p.name, \', \') FROM order_items oi JOIN products p ON p.id = oi.product_id '
    ' WHERE oi.order_id = o.id) AS items '
    'FROM orders o JOIN users u ON u.id = o.user_id '
)


def get_orders(status=None):
    if status:
        return get_db().execute(ORDER_SELECT + 'WHERE o.status = ? ORDER BY o.id DESC', (status,)).fetchall()
    return get_db().execute(ORDER_SELECT + 'ORDER BY o.id DESC').fetchall()


def get_user_orders(user_id):
    """Історія замовлень одного користувача."""
    return get_db().execute(ORDER_SELECT + 'WHERE o.user_id = ? ORDER BY o.id DESC', (user_id,)).fetchall()


def get_order_details(order_id):
    """Повертає замовлення та його позиції (JOIN з таблицею товарів)."""
    db = get_db()
    order = db.execute(ORDER_SELECT + 'WHERE o.id = ?', (order_id,)).fetchone()
    items = db.execute(
        'SELECT oi.product_id, p.name, oi.quantity, oi.unit_price '
        'FROM order_items oi JOIN products p ON oi.product_id = p.id '
        'WHERE oi.order_id = ? ORDER BY oi.id',
        (order_id,),
    ).fetchall()
    return order, items


def update_order_status(order_id, status):
    if status not in ORDER_STATUSES:
        raise ValueError(f'Невідомий статус: {status}')
    db = get_db()
    with db:
        db.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))


def delete_order(order_id):
    """Позиції замовлення видаляються самою базою (ON DELETE CASCADE)."""
    db = get_db()
    with db:
        db.execute('DELETE FROM orders WHERE id = ?', (order_id,))


def get_stats():
    """Лічильники для головної сторінки адмін-панелі."""
    db = get_db()
    return {
        'products': db.execute('SELECT COUNT(*) FROM products').fetchone()[0],
        'orders': db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],
        'new_orders': db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Нове'").fetchone()[0],
        'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'feedback': db.execute('SELECT COUNT(*) FROM feedback').fetchone()[0],
        'revenue': db.execute(
            "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status != 'Скасовано'"
        ).fetchone()[0],
    }
