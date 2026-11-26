# Розподіл роботи в команді

| Учасник | Роль | Файли |
|---------|------|-------|
| **Наконечний Михайло** | Архітектор БД, авторизація й ролі (рівень 3: ролі) | `app.py`, `models.py` (схема, users, функції доступу), `init_db.py`, `seed_data.py`, `routes/auth.py`, `templates/base.html`, `login.html`, `register.html`, `error.html`, `static/style.css`, `README.md` |
| **Бондар Роман** | Клієнтська частина: каталог, кошик, замовлення (рівень 1 + рівень 3: пошук/фільтр, промокоди в кошику, історія замовлень) | `routes/shop.py`, `routes/feedback.py`, `templates/home.html`, `shop.html`, `cart.html`, `orders.html`, `order_details.html`, `feedback.html`, `_macros.html` |
| **Данильчук Олександр** | Адмін-панель (рівень 1 + рівень 2: CRUD обсмажень + промокоди й користувачі) | `routes/admin.py`, `templates/admin/*` |

## Порядок комітів у Git

1. Наконечний Михайло: репозиторій, `app.py`, `models.py`, `routes/auth.py`, базові шаблони → `git push`.
2. Бондар Роман: гілка `shop` → `routes/shop.py`, `routes/feedback.py` і свої шаблони → pull request.
3. Данильчук Олександр: гілка `admin` → `routes/admin.py`, `templates/admin/` → pull request.
4. Кожен пише звіт у `lab-reports/` і пушить його у свою гілку.

Приклад повідомлень комітів: `Додано кошик у сесії`, `Додано CRUD обсмажень в адмінці`, `Хешування паролів і ролі`.


# Лабораторна 05: REST API

| Учасник | Файли |
|---------|-------|
| **Наконечний Михайло** | `routes/api/__init__.py`, `routes/api/common.py`, `routes/api/auth.py`, `routes/api/docs.py`, `app.py`, `requirements.txt`, `README.md` |
| **Бондар Роман** | `routes/api/catalog.py`, `routes/api/v2.py`, `tests/` |
| **Данильчук Олександр** | `routes/api/orders.py`, `routes/api/extras.py`, `postman/`, `docs/postman-run-results.txt` |

Порядок: Наконечний Михайло першим пушить `common.py`, `__init__.py`, `auth.py`, `docs.py` і `app.py`, потім Бондар Роман і Данильчук Олександр роблять `git pull` і додають свої файли в окремих комітах.


# Лабораторна 06: інтеграція клієнтської частини з API

| Учасник | Файли |
|---------|-------|
| **Наконечний Михайло** | `app.py` (маршрут `/api-demo` передає токен API), `TEAM.md`, `lab-reports/lab06-report.md` (звіт), перевірка й злиття pull request |
| **Бондар Роман** | `static/js/api-demo.js` (fetch, заголовок Authorization, обробка помилок, валідація) |
| **Данильчук Олександр** | `templates/api-demo.html` (форма, вибір обсмаження, передача токена в JS), скріншоти `lab-reports/img/api-demo-*.png` |

Порядок: Наконечний пушить `TEAM.md` і звіт; Бондар і Данильчук роблять `git pull`, кожен у своїй гілці додає свої файли й відкриває pull request.
