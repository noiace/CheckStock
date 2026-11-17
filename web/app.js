/* CheckStock: лёгкий интерфейс без клиентских библиотек.
   Все изменения выполняются только через существующий FastAPI API. */
'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const state = {
  view: 'overview', warehouses: [], products: [], stocks: [], transit: [],
  movements: [], historyEntries: [], historyPage: 0, pageSize: 50,
};
const viewTitles = {
  overview: 'Обзор', stocks: 'Остатки', transit: 'В пути',
  operations: 'Операции', warehouses: 'Склады', history: 'История',
};
const movementNames = {
  RECEIPT: 'Приход', FBS_RESERVED: 'FBS: резерв', FBS_CANCELLED: 'FBS: отмена',
  FBS_SHIPPED: 'FBS: отправка', FBS_DELIVERED: 'FBS: доставка',
  FBO_SHIPPED: 'FBO: отправка', FBO_RECEIVED: 'FBO: приёмка',
  TRANSFER_SHIPPED: 'Перемещение: отправка', TRANSFER_RECEIVED: 'Перемещение: приёмка',
};
const actionPaths = {
  'fbs-cancel': id => `/fbs/reservations/${id}/cancel`,
  'fbs-ship': id => `/fbs/reservations/${id}/ship`,
  'fbs-deliver': id => `/fbs/reservations/${id}/deliver`,
  'fbo-receive': id => `/fbo/shipments/${id}/receive`,
  'transfer-receive': id => `/transfers/${id}/receive`,
};
const actionLabels = {
  'fbs-cancel': 'Резерв отменён', 'fbs-ship': 'Товар отправлен покупателю',
  'fbs-deliver': 'Доставка подтверждена', 'fbo-receive': 'FBO принят маркетплейсом',
  'transfer-receive': 'Перемещение принято',
};

function safe(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
function number(value) { return new Intl.NumberFormat('ru-RU').format(Number(value) || 0); }
function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(date);
}
function emptyRow(columns, text) { return `<tr><td colspan="${columns}" class="empty-cell">${safe(text)}</td></tr>`; }
function warehouseName(id) {
  if (id == null) return '—';
  const w = state.warehouses.find(w => Number(w.id) === Number(id));
  return w ? w.name : `Склад №${id}`;
}
function productInfo(id) {
  const product = state.products.find(p => Number(p.id) === Number(id));
  return product || { id, sku: `ID ${id}`, name: 'Товар' };
}
function movementDestination(item) {
  if (item.to_warehouse_id != null) return warehouseName(item.to_warehouse_id);
  if (item.movement_type.startsWith('FBO_')) return 'Маркетплейс';
  if (['FBS_SHIPPED', 'FBS_DELIVERED'].includes(item.movement_type)) return 'Покупатель';
  return '—';
}
function getErrorMessage(data, status) {
  const detail = data?.detail;
  if (Array.isArray(detail)) return detail.map(item => {
    const location = Array.isArray(item.loc) ? item.loc.filter(x => x !== 'body').join('.') : '';
    return [location, item.msg].filter(Boolean).join(': ');
  }).join('; ');
  if (typeof detail === 'string') return detail;
  if (typeof data?.message === 'string') return data.message;
  return `Ошибка запроса (HTTP ${status})`;
}
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      method: options.method || 'GET',
      headers: options.body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: 'no-store',
    });
  } catch (_) {
    throw new Error('Нет связи с FastAPI. Проверь запуск Docker и доступность сервера.');
  }
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('json') ? await response.json() : null;
  if (!response.ok) throw new Error(getErrorMessage(data, response.status));
  return data;
}
function notify(message, type = '') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  $('#toast-root').append(toast);
  window.setTimeout(() => toast.remove(), 4500);
}
function showConnection(connected) {
  $('#connection-state').className = `connection ${connected ? 'ok' : 'error'}`;
  $('#connection-text').textContent = connected ? 'API подключён' : 'Нет соединения';
}
function errorBanner(message) {
  const element = $('#global-error');
  element.textContent = message || '';
  element.classList.toggle('hidden', !message);
}

async function refreshAll() {
  $('#refresh-btn').disabled = true;
  const paths = ['/warehouses', '/stocks', '/movements/in-transit', '/movements?limit=100', '/products'];
  const results = await Promise.allSettled(paths.map(path => api(path)));
  const labels = ['склады', 'остатки', 'товары в пути', 'история', 'товары'];
  const errors = [];
  for (let i = 0; i < paths.length; i++) {
    if (results[i].status === 'rejected') errors.push(`${labels[i]}: ${results[i].reason.message}`);
  }
  state.warehouses = results[0].status === 'fulfilled' ? results[0].value : [];
  state.stocks = results[1].status === 'fulfilled' ? results[1].value : [];
  state.transit = results[2].status === 'fulfilled' ? results[2].value : [];
  state.movements = results[3].status === 'fulfilled' ? results[3].value : [];
  state.products = results[4].status === 'fulfilled' ? results[4].value : [];
  showConnection(results[1].status === 'fulfilled' && results[0].status === 'fulfilled');
  errorBanner(errors.length ? `Часть данных не загрузилась. ${errors.join(' | ')}` : '');
  $('#last-updated').textContent = `Обновлено: ${formatDate(new Date().toISOString())}`;
  renderSelectors();
  renderEverything();
  if (state.view === 'history') await loadHistory();
  $('#refresh-btn').disabled = false;
}
function renderSelectors() {
  const allWarehouseOptions = state.warehouses.map(w => ({ id: w.id, title: `${w.name}${w.is_active ? '' : ' (архив)'}` }));
  const activeWarehouseOptions = state.warehouses.filter(w => w.is_active).map(w => ({ id: w.id, title: w.name }));
  const productOptions = [...state.products].sort((a, b) => String(a.sku).localeCompare(String(b.sku), 'ru')).map(p => ({ id: p.id, title: `${p.sku} — ${p.name}` }));
  $$('[data-products]').forEach(select => fillSelect(select, productOptions, 'Сначала добавьте товар'));
  $$('[data-warehouses]').forEach(select => fillSelect(select, activeWarehouseOptions, 'Сначала создайте склад'));
  fillSelect($('#stocks-warehouse'), [{ id: '', title: 'Все склады' }, ...allWarehouseOptions]);
  fillSelect($('#history-product'), [{ id: '', title: 'Все товары' }, ...productOptions]);
  fillSelect($('#history-warehouse'), [{ id: '', title: 'Все склады' }, ...allWarehouseOptions]);
}
function fillSelect(select, values, emptyPlaceholder = '') {
  const previous = select.value;
  select.replaceChildren();
  if (!values.length) {
    const option = new Option(emptyPlaceholder || 'Нет данных', '');
    option.disabled = true;
    select.add(option);
    select.value = '';
    return;
  }
  for (const item of values) select.add(new Option(item.title, String(item.id)));
  if (values.some(item => String(item.id) === previous)) select.value = previous;
}
function renderEverything() {
  renderMetrics(); renderOverview(); renderStocks(); renderTransit(); renderWarehouses();
  renderHistoryRows(state.historyEntries.length ? state.historyEntries : state.movements.slice(0, state.pageSize));
}
function renderMetrics() {
  const sum = key => state.stocks.reduce((total, row) => total + (Number(row[key]) || 0), 0);
  const transitSum = kind => state.transit.filter(row => row.kind === kind).reduce((total, row) => total + (Number(row.quantity) || 0), 0);
  $('#metric-sku').textContent = number(state.products.length);
  $('#metric-physical').textContent = number(sum('physical_quantity'));
  $('#metric-reserved').textContent = number(sum('reserved_quantity'));
  $('#metric-available').textContent = number(sum('available_quantity'));
  $('#metric-transit').textContent = number(state.transit.reduce((total, row) => total + Number(row.quantity || 0), 0));
  $('#summary-transfer').textContent = number(transitSum('TRANSFER'));
  $('#summary-fbo').textContent = number(transitSum('FBO'));
  $('#summary-fbs').textContent = number(transitSum('FBS'));
}
function renderOverview() {
  const tbody = $('#overview-stock-rows');
  const rows = state.stocks.filter(row => row.warehouse_is_active).slice(0, 8);
  tbody.innerHTML = rows.length ? rows.map(row => `<tr><td><strong>${safe(row.sku)}</strong><span class="subtext">${safe(row.product_name)}</span></td><td>${safe(row.warehouse_name)}</td><td class="num">${number(row.physical_quantity)}</td><td class="num">${number(row.reserved_quantity)}</td><td class="num"><strong>${number(row.available_quantity)}</strong></td></tr>`).join('') : emptyRow(5, 'Пока нет товаров и остатков');
  const history = state.movements.slice(0, 6);
  $('#overview-history-rows').innerHTML = history.length ? history.map(item => `<tr><td class="no-wrap">${formatDate(item.created_at)}</td><td>${safe(movementNames[item.movement_type] || item.movement_type)}</td><td>${safe(productInfo(item.product_id).sku)}</td><td>${safe(warehouseName(item.from_warehouse_id))} / ${safe(movementDestination(item))}</td><td class="num">${number(item.quantity)}</td></tr>`).join('') : emptyRow(5, 'История пока пуста');
}
function renderStocks() {
  const search = $('#stocks-search').value.trim().toLocaleLowerCase('ru');
  const warehouseId = $('#stocks-warehouse').value;
  const showArchived = $('#stocks-show-archived').checked;
  const rows = state.stocks.filter(row => (!search || `${row.sku} ${row.product_name}`.toLocaleLowerCase('ru').includes(search)) && (!warehouseId || String(row.warehouse_id) === warehouseId) && (showArchived || row.warehouse_is_active));
  $('#stocks-rows').innerHTML = rows.length ? rows.map(row => `<tr><td><strong>${safe(row.sku)}</strong></td><td>${safe(row.product_name)}</td><td>${safe(row.warehouse_name)}</td><td class="num">${number(row.physical_quantity)}</td><td class="num">${number(row.reserved_quantity)}</td><td class="num"><strong>${number(row.available_quantity)}</strong></td><td><span class="status-chip ${row.warehouse_is_active ? (Number(row.available_quantity) > 0 ? 'positive' : 'zero') : 'archived'}">${row.warehouse_is_active ? (Number(row.available_quantity) > 0 ? 'Доступен' : 'Нет в наличии') : 'Архив'}</span></td></tr>`).join('') : emptyRow(7, 'По выбранным условиям товаров нет');
  $('#stocks-total').textContent = `Показано строк: ${rows.length}`;
}
function renderTransit() {
  const filter = $('#transit-filter').value;
  const rows = state.transit.filter(item => !filter || item.kind === filter);
  const kind = { TRANSFER: 'Между ФФ', FBO: 'FBO', FBS: 'FBS' };
  const destinations = { FBO: 'Маркетплейс', FBS: 'Покупатель' };
  const actions = { TRANSFER: 'transfer-receive', FBO: 'fbo-receive', FBS: 'fbs-deliver' };
  $('#transit-rows').innerHTML = rows.length ? rows.map(item => {
    const action = actions[item.kind];
    return `<tr><td><strong>${safe(kind[item.kind] || item.kind)}</strong><span class="subtext">№ ${number(item.operation_id)}</span></td><td><strong>${safe(productInfo(item.product_id).sku)}</strong><span class="subtext">${safe(productInfo(item.product_id).name)}</span></td><td class="num"><strong>${number(item.quantity)}</strong></td><td>${safe(warehouseName(item.from_warehouse_id))}</td><td>${safe(item.kind === 'TRANSFER' ? warehouseName(item.to_warehouse_id) : (destinations[item.kind] || '—'))}</td><td class="no-wrap">${formatDate(item.created_at)}</td><td><button type="button" class="button button-outline small" data-quick-action="${safe(action)}" data-operation-id="${Number(item.operation_id)}">Подтвердить</button></td></tr>`;
  }).join('') : emptyRow(7, 'Незавершённых отправок нет');
}
function renderWarehouses() {
  const rows = state.warehouses;
  $('#warehouse-rows').innerHTML = rows.length ? rows.map(item => `<tr><td class="warehouse-id">${number(item.id)}</td><td><strong>${safe(item.name)}</strong></td><td><span class="status-chip ${item.is_active ? 'positive' : 'archived'}">${item.is_active ? 'Активен' : 'Архив'}</span></td><td><div class="action-cell">${item.is_active ? `<button type="button" class="button button-quiet small" data-warehouse-op="rename" data-id="${Number(item.id)}">Переименовать</button><button type="button" class="button button-danger small" data-warehouse-op="archive" data-id="${Number(item.id)}">В архив</button>` : '<span class="muted">—</span>'}</div></td></tr>`).join('') : emptyRow(4, 'Склады ещё не созданы');
}
function associatedOperation(item) {
  if (item.fbs_reservation_id != null) return `FBS №${item.fbs_reservation_id}`;
  if (item.fbo_shipment_id != null) return `FBO №${item.fbo_shipment_id}`;
  if (item.transfer_id != null) return `Transfer №${item.transfer_id}`;
  return '—';
}
function renderHistoryRows(rows) {
  $('#history-rows').innerHTML = rows.length ? rows.map(item => `<tr><td class="no-wrap">${formatDate(item.created_at)}</td><td><span class="status-chip transit">${safe(movementNames[item.movement_type] || item.movement_type)}</span></td><td><strong>${safe(productInfo(item.product_id).sku)}</strong></td><td>${safe(warehouseName(item.from_warehouse_id))}</td><td>${safe(movementDestination(item))}</td><td class="num">${number(item.quantity)}</td><td class="no-wrap">${safe(associatedOperation(item))}</td></tr>`).join('') : emptyRow(7, 'По выбранным фильтрам операций нет');
  $('#history-total').textContent = `Записей на странице: ${rows.length}`;
  $('#history-page').textContent = String(state.historyPage + 1);
  $('#history-prev').disabled = state.historyPage === 0;
  $('#history-next').disabled = rows.length < state.pageSize;
}
async function loadHistory() {
  const params = new URLSearchParams({ limit: String(state.pageSize), offset: String(state.historyPage * state.pageSize) });
  if ($('#history-product').value) params.set('product_id', $('#history-product').value);
  if ($('#history-warehouse').value) params.set('warehouse_id', $('#history-warehouse').value);
  if ($('#history-type').value) params.set('movement_type', $('#history-type').value);
  try {
    const rows = await api(`/movements?${params.toString()}`);
    state.historyEntries = rows;
    renderHistoryRows(rows);
  } catch (error) {
    state.historyEntries = [];
    renderHistoryRows([]);
    notify(`Не удалось получить историю: ${error.message}`, 'error');
  }
}
async function changeView(view) {
  if (!Object.hasOwn(viewTitles, view)) return;
  state.view = view;
  $$('[data-panel]').forEach(section => section.classList.toggle('hidden', section.dataset.panel !== view));
  $$('[data-view]').forEach(button => {
    button.classList.toggle('active', button.dataset.view === view);
    if (button.dataset.view === view) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  $('#breadcrumb').textContent = viewTitles[view];
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (view === 'history') await loadHistory();
}
function readData(form) {
  const result = {};
  for (const [key, value] of new FormData(form).entries()) {
    if (['quantity', 'product_id', 'warehouse_id', 'from_warehouse_id', 'to_warehouse_id', 'id'].includes(key)) {
      const numberValue = Number(value);
      if (!Number.isSafeInteger(numberValue) || numberValue <= 0) throw new Error(`Поле «${key}» должно содержать положительное целое число`);
      result[key] = numberValue;
    } else result[key] = String(value).trim();
  }
  return result;
}
function showResult(title, result, error = false) {
  const panel = $('#operation-result');
  panel.classList.toggle('error', error);
  panel.classList.remove('hidden');
  const id = Number(result?.id);
  const rows = [];
  if (Number.isSafeInteger(id) && id > 0) rows.push(`ID операции: <strong>${id}</strong>`);
  if (result?.status) rows.push(`Статус: <strong>${safe(result.status)}</strong>`);
  if (result?.quantity) rows.push(`Количество: <strong>${number(result.quantity)}</strong>`);
  if (result?.sku) rows.push(`Артикул: <strong>${safe(result.sku)}</strong>`);
  const buttons = [];
  if (!error && Number.isSafeInteger(id) && id > 0) {
    if (result.status === 'RESERVED') buttons.push(['fbs-ship', 'Отправить FBS'], ['fbs-cancel', 'Отменить резерв']);
    if (result.status === 'SHIPPED') buttons.push(['fbs-deliver', 'Подтвердить доставку']);
    if (result.status === 'IN_TRANSIT') {
      if (Object.hasOwn(result, 'to_warehouse_id')) buttons.push(['transfer-receive', 'Подтвердить приёмку на ФФ']);
      else buttons.push(['fbo-receive', 'Подтвердить FBO']);
    }
  }
  panel.innerHTML = `<strong>${safe(title)}</strong>${rows.length ? `<div>${rows.join(' · ')}</div>` : ''}${buttons.length ? `<div class="result-actions">${buttons.map(([action, label]) => `<button class="button button-outline small" type="button" data-quick-action="${action}" data-operation-id="${id}">${safe(label)}</button>`).join('')}</div>` : ''}`;
}
async function mutate({ method = 'POST', path, body, title, form = null }) {
  const submit = form?.querySelector('button[type="submit"]');
  const oldText = submit?.textContent;
  if (submit) { submit.disabled = true; submit.textContent = 'Отправляем...'; }
  try {
    const result = await api(path, { method, body });
    if (form?.id === 'form-product' || form?.id === 'form-warehouse') form.reset();
    showResult(title, result);
    notify(title, 'success');
    await refreshAll();
    return result;
  } catch (error) {
    showResult(error.message, null, true);
    notify(error.message, 'error');
    return null;
  } finally {
    if (submit) { submit.disabled = false; submit.textContent = oldText; }
  }
}
async function performAction(action, id) {
  const route = actionPaths[action];
  if (!route || !Number.isSafeInteger(Number(id)) || Number(id) <= 0) return notify('Неверный тип операции или ID', 'error');
  const result = await mutate({ path: route(id), title: actionLabels[action] });
  if (result && state.view !== 'operations') {
    // Пользователь может продолжить операцию из блока результата в разделе «Операции».
    notify(`Операция №${id}: ${actionLabels[action]}`, 'success');
  }
}
async function warehouseOperation(operation, id) {
  const current = state.warehouses.find(w => Number(w.id) === Number(id));
  if (!current) return;
  if (operation === 'rename') {
    const name = window.prompt('Новое название склада:', current.name);
    if (name == null) return;
    if (!name.trim()) return notify('Название не должно быть пустым', 'error');
    await mutate({ path: `/warehouses/${id}`, method: 'PATCH', body: { name: name.trim() }, title: `Склад переименован: ${name.trim()}` });
  } else if (operation === 'archive') {
    if (!window.confirm(`Архивировать склад «${current.name}»?\nОстатки и история сохранятся, но новые операции с ним будут запрещены.`)) return;
    await mutate({ path: `/warehouses/${id}`, method: 'DELETE', title: `Склад «${current.name}» переведён в архив` });
  }
}

function initEvents() {
  $('#main-nav').addEventListener('click', event => {
    const nav = event.target.closest('[data-view]');
    if (nav) changeView(nav.dataset.view);
  });
  document.addEventListener('click', event => {
    const go = event.target.closest('[data-go]');
    if (go) changeView(go.dataset.go);
    const quick = event.target.closest('[data-quick-action]');
    if (quick) performAction(quick.dataset.quickAction, Number(quick.dataset.operationId));
    const warehouse = event.target.closest('[data-warehouse-op]');
    if (warehouse) warehouseOperation(warehouse.dataset.warehouseOp, Number(warehouse.dataset.id));
  });
  $('#refresh-btn').addEventListener('click', refreshAll);
  $('#stocks-search').addEventListener('input', renderStocks);
  $('#stocks-warehouse').addEventListener('change', renderStocks);
  $('#stocks-show-archived').addEventListener('change', renderStocks);
  $('#transit-filter').addEventListener('change', renderTransit);
  $('#history-filter-btn').addEventListener('click', () => { state.historyPage = 0; loadHistory(); });
  $('#history-prev').addEventListener('click', () => { if (state.historyPage > 0) { state.historyPage--; loadHistory(); } });
  $('#history-next').addEventListener('click', () => { if (state.historyEntries.length === state.pageSize) { state.historyPage++; loadHistory(); } });
  const forms = [
    ['form-product', '/products', 'Товар создан'],
    ['form-warehouse', '/warehouses', 'Склад создан'],
    ['form-receipt', '/receipts', 'Приход оформлен'],
    ['form-fbs', '/fbs/reservations', 'Резерв FBS создан'],
    ['form-fbo', '/fbo/shipments', 'Отправка FBO создана'],
    ['form-transfer', '/transfers', 'Перемещение создано'],
  ];
  for (const [formId, path, title] of forms) {
    const form = $(`#${formId}`);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const body = readData(form);
        if (formId === 'form-transfer' && body.from_warehouse_id === body.to_warehouse_id) {
          throw new Error('Склады отправления и назначения должны различаться');
        }
        await mutate({ path, body, title, form });
      } catch (error) { showResult(error.message, null, true); notify(error.message, 'error'); }
    });
  }
  $('#form-action').addEventListener('submit', async event => {
    event.preventDefault();
    try {
      const data = readData(event.currentTarget);
      await performAction(data.action, data.id);
    } catch (error) { notify(error.message, 'error'); }
  });
}
initEvents();
refreshAll();
