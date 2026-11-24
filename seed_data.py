"""Додає тестового клієнта, ще один промокод, замовлення й відгук.
Каву, адміна й COFFEE10 застосунок створює сам при першому запуску.
Запуск: python seed_data.py (необов'язково).
"""
import sqlite3

from app import app
import models

def seed():
    models.init_db()  # на новій базі це вже додає каву, адміна й промокод COFFEE10
    added = models.ensure_default_products()  # додає відсутню каву (для вже створеної бази)
    if added:
        print(f'Додано сортів кави: {added}')
    if models.get_user_orders(1) or models.get_feedback():
        print('Тестові замовлення й відгуки вже є — пропускаю.')
        return

    try:
        client_id = models.create_user('client', 'client123')
    except sqlite3.IntegrityError:
        client_id = models.authenticate('client', 'client123')['id']
    for code, percent in (('COFFEE10', 10), ('WELCOME20', 20)):
        try:
            models.add_promo(code, percent)
        except sqlite3.IntegrityError:
            pass

    first, second = sorted(models.get_products(), key=lambda p: p["id"])[:2]
    models.create_order(client_id, 'м. Луцьк, вул. Володимирська, 1', {first['id']: 2, second['id']: 1}, 'COFFEE10')
    models.add_feedback(client_id, 'Ефіопія просто неймовірна, ніжна й ароматна!')
    print('Тестові дані додано. Клієнт: client / client123')


if __name__ == '__main__':
    with app.app_context():
        seed()
