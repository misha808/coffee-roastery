"""Відгуки клієнтів: читати можуть усі, писати — лише авторизовані."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

import models
from .auth import login_required

feedback_bp = Blueprint('feedback', __name__)


@feedback_bp.route('/feedback')
def feedback():
    return render_template('feedback.html', reviews=models.get_feedback())


@feedback_bp.route('/feedback', methods=['POST'])
@login_required
def add_feedback():
    message = request.form.get('message', '').strip()
    # Перевірка на сервері обов'язкова: HTML-атрибут required легко обійти
    if not 3 <= len(message) <= 1000:
        flash('Відгук має містити від 3 до 1000 символів.', 'error')
    else:
        models.add_feedback(session['user_id'], message)
        flash('Дякуємо за відгук!', 'success')
    return redirect(url_for('feedback.feedback'))
