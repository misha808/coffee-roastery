"""Каталог, кошик, промокоди, оформлення замовлення та історія замовлень."""
from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, session, url_for)

import models
from .auth import login_required

shop_bp = Blueprint('shop', __name__)

MAX_QUANTITY = 99


# ------------------------------------------------------------ допоміжне

def get_cart():
    """Кошик у сесії: {id товару: кількість}. У сесії ключі зберігаються рядками."""
    return {int(pid): qty for pid, qty in session.get('cart', {}).items()}


def save_cart(cart):
    session['cart'] = {str(pid): qty for pid, qty in cart.items()}


def get_quantity():
    """Кількість із форми, обмежена діапазоном 0..MAX_QUANTITY."""
    try:
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        quantity = 1
    return max(0, min(quantity, MAX_QUANTITY))


def build_cart():
    """Рядки кошика й підсумки. Назви та ціни беруться з бази, а не з сесії."""
    cart = get_cart()
    lines = [
        {'product': p, 'quantity': cart[p['id']], 'subtotal': round(p['price'] * cart[p['id']], 2)}
        for p in models.get_products_by_ids(cart.keys())
    ]
    # Якщо товар видалили з магазину, прибираємо його й з кошика
    if len(lines) != len(cart):
        save_cart({line['product']['id']: line['quantity'] for line in lines})

    subtotal = round(sum(line['subtotal'] for line in lines), 2)
    # Промокод перевіряємо щоразу: адмін міг його вимкнути
    promo = models.get_active_promo(session.get('promo'))
    if session.get('promo') and promo is None:
        session.pop('promo')
    discount, total = models.calc_totals(subtotal, promo)
    return {'lines': lines, 'subtotal': subtotal, 'promo': promo, 'discount': discount, 'total': total}


# --------------------------------------------------------------- каталог

@shop_bp.route('/shop')
def shop():
    q = request.args.get('q', '').strip()
    roast_id = request.args.get('roast', type=int)
    sort = request.args.get('sort', 'new')
    return render_template(
        'shop.html',
        products=models.get_products(q=q, roast_id=roast_id, sort=sort),
        roasts=models.get_roasts(),
        q=q, roast_id=roast_id, sort=sort,
    )


# ----------------------------------------------------------------- кошик

@shop_bp.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = models.get_product(product_id)
    if product is None:
        flash('Такого товару не існує.', 'error')
        return redirect(url_for('shop.shop'))

    cart = get_cart()
    cart[product_id] = min(cart.get(product_id, 0) + 1, MAX_QUANTITY)
    save_cart(cart)
    flash(f'«{product["name"]}» додано до кошика.', 'success')
    # Повертаємо користувача туди, звідки він додавав (з фільтрами), але лише на свій сайт
    target = request.form.get('next', '')
    return redirect(target if target.startswith('/') and not target.startswith('//') else url_for('shop.shop'))


@shop_bp.route('/cart')
def cart():
    return render_template('cart.html', max_quantity=MAX_QUANTITY, **build_cart())


@shop_bp.route('/cart/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    cart = get_cart()
    if product_id in cart:
        quantity = get_quantity()
        if quantity == 0:
            del cart[product_id]
        else:
            cart[product_id] = quantity
        save_cart(cart)
    return redirect(url_for('shop.cart'))


@shop_bp.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = get_cart()
    cart.pop(product_id, None)
    save_cart(cart)
    return redirect(url_for('shop.cart'))


@shop_bp.route('/cart/promo', methods=['POST'])
def apply_promo():
    code = request.form.get('code', '').strip()
    promo = models.get_active_promo(code)
    if promo is None:
        flash('Такого промокоду немає або він не діє.', 'error')
    else:
        session['promo'] = promo['code']
        flash(f'Промокод {promo["code"]} застосовано: знижка {promo["discount_percent"]}%.', 'success')
    return redirect(url_for('shop.cart'))


@shop_bp.route('/cart/promo/remove', methods=['POST'])
def remove_promo():
    session.pop('promo', None)
    return redirect(url_for('shop.cart'))


@shop_bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    address = request.form.get('address', '').strip()
    if len(address) < 5:
        flash('Вкажіть адресу доставки.', 'error')
        return redirect(url_for('shop.cart'))

    try:
        order_id = models.create_order(session['user_id'], address, get_cart(), session.get('promo'))
    except ValueError:
        flash('Кошик порожній.', 'error')
        return redirect(url_for('shop.cart'))

    save_cart({})
    session.pop('promo', None)
    flash(f'Замовлення №{order_id} оформлено. Дякуємо!', 'success')
    return redirect(url_for('shop.order_details', order_id=order_id))


# ------------------------------------------------------ історія замовлень

@shop_bp.route('/orders')
@login_required
def orders():
    return render_template('orders.html', orders=models.get_user_orders(session['user_id']))


@shop_bp.route('/orders/<int:order_id>')
@login_required
def order_details(order_id):
    order, items = models.get_order_details(order_id)
    # Клієнт бачить лише свої замовлення; чужі — 404, щоб не розкривати їхнє існування
    if order is None or (order['user_id'] != session['user_id'] and session.get('role') != 'admin'):
        abort(404)
    return render_template('order_details.html', order=order, items=items)
