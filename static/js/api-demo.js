const API_URL = '/api/v1/products'; 

function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

function showMessage(text, type) {
    const msg = document.getElementById('message');
    msg.textContent = text;
    msg.className = `alert alert-${type}`;
    msg.style.display = 'block';
    setTimeout(() => msg.style.display = 'none', 5000);
}

async function getErrorText(response) {
    try {
        const body = await response.json();
        let text = body.error || body.message || `HTTP помилка: ${response.status}`;
        if (body.details) {
            text += ' (' + Object.entries(body.details)
                .map(([field, msg]) => `${field}: ${msg}`).join('; ') + ')';
        }
        return text;
    } catch {
        return `HTTP помилка: ${response.status}`;
    }
}

async function loadRoasts() {
    try {
        const response = await fetch('/api/v1/roasts');
        if (!response.ok) throw new Error(await getErrorText(response));
        const roasts = await response.json();
        const select = document.getElementById('productRoast');
        roasts.forEach(r => select.add(new Option(r.name, r.id)));
    } catch (error) {
        showMessage('❌ Не вдалося завантажити обсмаження: ' + error.message, 'danger');
    }
}

async function loadData() {
    try {
        showLoading(true);
        const response = await fetch(API_URL);

        if (!response.ok) throw new Error(await getErrorText(response));

        const data = await response.json();
        displayData(data.products || data); 
    } catch (error) {
        showMessage('❌ Помилка завантаження: ' + error.message, 'danger');
    } finally {
        showLoading(false);
    }
}

async function addItem(itemData) {
    if (!window.API_TOKEN) {
        showMessage('❌ Щоб додавати товари, увійдіть як адміністратор', 'warning');
        return;
    }
    try {
        showLoading(true);
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(window.API_TOKEN ? { 'Authorization': 'Bearer ' + window.API_TOKEN } : {})
            },
            body: JSON.stringify(itemData)
        });

        if (!response.ok) throw new Error(await getErrorText(response));

        showMessage('✅ Продукт успішно додано!', 'success');
        await loadData();
    } catch (error) {
        showMessage('❌ Помилка додавання: ' + error.message, 'danger');
    } finally {
        showLoading(false);
    }
}

function displayData(items) {
    const container = document.getElementById('dataList');
    container.innerHTML = '';

    if (!items || items.length === 0) {
        container.innerHTML = '<div class="col-12"><p class="text-muted">📭 Кави поки немає. Додайте перший сорт!</p></div>';
        return;
    }

    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'col-md-4';
        
        div.innerHTML = `
            <div class="item-card shadow-sm">
                <h5 class="title-text"></h5>
                <p class="item-price"></p>
                <p class="desc-text text-muted small"></p>
            </div>
        `;
        
        div.querySelector('.title-text').textContent = item.name || 'Без назви';
        div.querySelector('.item-price').textContent = (item.price || 0) + ' ₴';
        div.querySelector('.desc-text').textContent = item.description || 'Опис відсутній';

        container.appendChild(div);
    });
}

document.getElementById('addForm').addEventListener('submit', async (event) => {
    event.preventDefault();

    const name = document.getElementById('productName').value.trim();
    const price = parseFloat(document.getElementById('productPrice').value);
    const description = document.getElementById('productDescription').value.trim();

    if (name.length < 2) {
        showMessage('❌ Назва повинна містити мінімум 2 символи', 'warning');
        return;
    }

    const roast_id = parseInt(document.getElementById('productRoast').value);
    const itemData = { name, price, description, roast_id };
    await addItem(itemData);
    event.target.reset();
});

loadRoasts();
loadData();
