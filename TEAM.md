# Розподіл роботи в команді

| Учасник | Роль | Файли |
|---------|------|-------|
| **Михайло** | Архітектор БД, авторизація й ролі (рівень 3: ролі) | `app.py`, `models.py` (схема, users, функції доступу), `init_db.py`, `seed_data.py`, `routes/auth.py`, `templates/base.html`, `login.html`, `register.html`, `error.html`, `static/style.css`, `README.md` |
| **Ромка** | Клієнтська частина: каталог, кошик, замовлення (рівень 1 + рівень 3: пошук/фільтр, промокоди в кошику, історія замовлень) | `routes/shop.py`, `routes/feedback.py`, `templates/home.html`, `shop.html`, `cart.html`, `orders.html`, `order_details.html`, `feedback.html`, `_macros.html` |
| **Сашко** | Адмін-панель (рівень 1 + рівень 2: CRUD обсмажень + промокоди й користувачі) | `routes/admin.py`, `templates/admin/*` |

## Порядок комітів у Git

1. Михайло: репозиторій, `app.py`, `models.py`, `routes/auth.py`, базові шаблони → `git push`.
2. Ромка: гілка `shop` → `routes/shop.py`, `routes/feedback.py` і свої шаблони → pull request.
3. Сашко: гілка `admin` → `routes/admin.py`, `templates/admin/` → pull request.
4. Кожен пише звіт у `lab-reports/` і пушить його у свою гілку.

Приклад повідомлень комітів: `Додано кошик у сесії`, `Додано CRUD обсмажень в адмінці`, `Хешування паролів і ролі`.
