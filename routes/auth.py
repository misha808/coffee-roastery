"""Реєстрація, вхід, вихід і захист маршрутів за ролями (рівень 3)."""
import sqlite3
from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, session, url_for)

import models

auth_bp = Blueprint('auth', __name__)


def login_required(view):
    """Пускає лише авторизованих користувачів; інших відправляє на сторінку входу."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Спочатку увійдіть в акаунт.', 'error')
            return redirect(url_for('auth.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def require_admin():
    """Перевірка ролі. Використовується як before_request у Blueprint адмін-панелі."""
    if 'user_id' not in session:
        flash('Спочатку увійдіть в акаунт.', 'error')
        return redirect(url_for('auth.login', next=request.path))
    if session.get('role') != 'admin':
        abort(403)


def safe_next(target):
    """Дозволяє перенаправлення лише на внутрішні адреси (захист від open redirect)."""
    if target and target.startswith('/') and not target.startswith('//'):
        return target
    return url_for('home')


def start_session(user):
    # Кошик зберігаємо, решту очищаємо, щоб не змішувати старі дані з новим входом
    cart = session.get('cart')
    session.clear()
    if cart:
        session['cart'] = cart
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        error = None
        if not 3 <= len(username) <= 30:
            error = 'Логін має містити від 3 до 30 символів.'
        elif len(password) < 6:
            error = 'Пароль має містити щонайменше 6 символів.'
        elif password != confirm:
            error = 'Паролі не збігаються.'

        if error is None:
            try:
                user_id = models.create_user(username, password)  # роль за замовчуванням — client
            except sqlite3.IntegrityError:
                error = 'Цей логін уже зайнятий.'
            else:
                start_session(models.get_user(user_id))
                flash('Акаунт створено. Ласкаво просимо!', 'success')
                return redirect(url_for('home'))
        flash(error, 'error')
    return render_template('register.html', username=request.form.get('username', ''))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = models.authenticate(request.form.get('username', '').strip(), request.form.get('password', ''))
        if user is None:
            flash('Невірний логін або пароль.', 'error')
        else:
            start_session(user)
            return redirect(safe_next(request.args.get('next')))
    return render_template('login.html', username=request.form.get('username', ''))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Ви вийшли з акаунта.', 'success')
    return redirect(url_for('home'))
