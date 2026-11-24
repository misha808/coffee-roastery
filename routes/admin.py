"""Адмін-панель: замовлення, товари, ступені обсмаження (рівень 2), промокоди, відгуки, користувачі."""
import re
import sqlite3

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, session, url_for)

import models
from .auth import require_admin

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
# Усі маршрути Blueprint доступні лише адміністраторам
admin_bp.before_request(require_admin)


# ------------------------------------------------------------ головна

@admin_bp.route('/')
def dashboard():
    return render_template('admin/dashboard.html', stats=models.get_stats(), orders=models.get_orders()[:5])


# ------------------------------------------------------------ замовлення

@admin_bp.route('/orders')
def orders():
    status = request.args.get('status', '')
    if status not in models.ORDER_STATUSES:
        status = ''
    return render_template('admin/orders.html', orders=models.get_orders(status or None),
                           statuses=models.ORDER_STATUSES, current=status)


@admin_bp.route('/orders/<int:order_id>')
def order_details(order_id):
    order, items = models.get_order_details(order_id)
    if order is None:
        abort(404)
    return render_template('admin/order.html', order=order, items=items, statuses=models.ORDER_STATUSES)


@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
def update_order(order_id):
    try:
        models.update_order_status(order_id, request.form.get('status', ''))
        flash(f'Статус замовлення №{order_id} оновлено.', 'success')
    except ValueError:
        flash('Невідомий статус замовлення.', 'error')
    return redirect(request.form.get('back') or url_for('admin.order_details', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
def delete_order(order_id):
    models.delete_order(order_id)
    flash(f'Замовлення №{order_id} видалено.', 'success')
    return redirect(url_for('admin.orders'))


# --------------------------------------------------------------- товари

def read_product_form():
    """Читає й перевіряє форму товару. Повертає (дані, помилка)."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    roast_id = request.form.get('roast_id', type=int)
    try:
        price = round(float(request.form.get('price', '').replace(',', '.')), 2)
    except ValueError:
        return None, 'Ціна має бути числом.'
    if not name:
        return None, 'Вкажіть назву товару.'
    if price < 0:
        return None, 'Ціна не може бути від\'ємною.'
    if models.get_roast(roast_id) is None:
        return None, 'Оберіть ступінь обсмаження.'
    return {'name': name, 'description': description, 'price': price, 'roast_id': roast_id}, None


@admin_bp.route('/products')
def products():
    return render_template('admin/products.html', products=models.get_products())


@admin_bp.route('/products/new', methods=['GET', 'POST'])
def new_product():
    if request.method == 'POST':
        data, error = read_product_form()
        if error is None:
            models.add_product(**data)
            flash(f'Товар «{data["name"]}» додано.', 'success')
            return redirect(url_for('admin.products'))
        flash(error, 'error')
    return render_template('admin/product_form.html', product=request.form.to_dict(),
                           roasts=models.get_roasts(), is_new=True)


@admin_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    product = models.get_product(product_id)
    if product is None:
        abort(404)
    if request.method == 'POST':
        data, error = read_product_form()
        if error is None:
            models.update_product(product_id, **data)
            flash(f'Товар «{data["name"]}» оновлено.', 'success')
            return redirect(url_for('admin.products'))
        flash(error, 'error')
        product = request.form.to_dict()  # показуємо форму з тим, що ввів користувач
    return render_template('admin/product_form.html', product=product,
                           roasts=models.get_roasts(), is_new=False)


@admin_bp.route('/products/<int:product_id>/delete', methods=['POST'])
def delete_product(product_id):
    try:
        models.delete_product(product_id)
        flash('Товар видалено.', 'success')
    except sqlite3.IntegrityError:
        # Спрацював зовнішній ключ: товар є в існуючих замовленнях
        flash('Не можна видалити товар, який є в замовленнях.', 'error')
    return redirect(url_for('admin.products'))


# ---------------------------------------------- ступені обсмаження (рівень 2)

def read_roast_form():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    color = request.form.get('color', '').strip()
    if not name:
        return None, 'Вкажіть назву обсмаження.'
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        return None, 'Колір має бути у форматі #rrggbb.'
    return {'name': name, 'description': description, 'color': color}, None


@admin_bp.route('/roasts')
def roasts():
    return render_template('admin/roasts.html', roasts=models.get_roasts())


@admin_bp.route('/roasts/new', methods=['GET', 'POST'])
def new_roast():
    if request.method == 'POST':
        data, error = read_roast_form()
        if error is None:
            try:
                models.add_roast(**data)
                flash(f'Обсмаження «{data["name"]}» додано.', 'success')
                return redirect(url_for('admin.roasts'))
            except sqlite3.IntegrityError:
                error = 'Таке обсмаження вже існує.'
        flash(error, 'error')
    return render_template('admin/roast_form.html', roast=request.form.to_dict() or {'color': '#8a6a4f'}, is_new=True)


@admin_bp.route('/roasts/<int:roast_id>/edit', methods=['GET', 'POST'])
def edit_roast(roast_id):
    roast = models.get_roast(roast_id)
    if roast is None:
        abort(404)
    if request.method == 'POST':
        data, error = read_roast_form()
        if error is None:
            try:
                models.update_roast(roast_id, **data)
                flash(f'Обсмаження «{data["name"]}» оновлено.', 'success')
                return redirect(url_for('admin.roasts'))
            except sqlite3.IntegrityError:
                error = 'Таке обсмаження вже існує.'
        flash(error, 'error')
        roast = request.form.to_dict()
    return render_template('admin/roast_form.html', roast=roast, is_new=False)


@admin_bp.route('/roasts/<int:roast_id>/delete', methods=['POST'])
def delete_roast(roast_id):
    try:
        models.delete_roast(roast_id)
        flash('Обсмаження видалено.', 'success')
    except sqlite3.IntegrityError:
        flash('Не можна видалити обсмаження, до якого прив\'язані товари.', 'error')
    return redirect(url_for('admin.roasts'))


# ------------------------------------------------------------- промокоди

@admin_bp.route('/promos')
def promos():
    return render_template('admin/promos.html', promos=models.get_promos())


@admin_bp.route('/promos/new', methods=['POST'])
def new_promo():
    code = request.form.get('code', '').strip()
    percent = request.form.get('discount_percent', type=int)
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,20}', code):
        flash('Код: 3–20 символів, лише латиниця, цифри, «-» та «_».', 'error')
    elif percent is None or not 1 <= percent <= 90:
        flash('Знижка має бути від 1 до 90%.', 'error')
    else:
        try:
            models.add_promo(code, percent)
            flash(f'Промокод {code.upper()} створено.', 'success')
        except sqlite3.IntegrityError:
            flash('Такий промокод уже існує.', 'error')
    return redirect(url_for('admin.promos'))


@admin_bp.route('/promos/<int:promo_id>/toggle', methods=['POST'])
def toggle_promo(promo_id):
    models.toggle_promo(promo_id)
    return redirect(url_for('admin.promos'))


@admin_bp.route('/promos/<int:promo_id>/delete', methods=['POST'])
def delete_promo(promo_id):
    models.delete_promo(promo_id)
    flash('Промокод видалено.', 'success')
    return redirect(url_for('admin.promos'))


# ---------------------------------------------------------------- відгуки

@admin_bp.route('/feedback')
def feedback():
    return render_template('admin/feedback.html', reviews=models.get_feedback())


@admin_bp.route('/feedback/<int:feedback_id>/delete', methods=['POST'])
def delete_feedback(feedback_id):
    models.delete_feedback(feedback_id)
    flash('Відгук видалено.', 'success')
    return redirect(url_for('admin.feedback'))


# ---------------------------------------------------------- користувачі

@admin_bp.route('/users')
def users():
    return render_template('admin/users.html', users=models.get_users())


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
def set_role(user_id):
    if user_id == session['user_id']:
        flash('Не можна змінити роль самому собі.', 'error')
    elif models.get_user(user_id) is None:
        abort(404)
    else:
        try:
            models.set_user_role(user_id, request.form.get('role', ''))
            flash('Роль оновлено.', 'success')
        except ValueError:
            flash('Невідома роль.', 'error')
    return redirect(url_for('admin.users'))
