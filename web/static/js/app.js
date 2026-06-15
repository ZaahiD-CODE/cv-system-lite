const API_BASE = '/api';

class Auth {
    static getToken() { return localStorage.getItem('token'); }
    static setToken(token, role, username) {
        localStorage.setItem('token', token);
        localStorage.setItem('role', role);
        localStorage.setItem('username', username);
    }
    static clear() {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('username');
    }
    static getRole() { return localStorage.getItem('role'); }
    static getUsername() { return localStorage.getItem('username'); }
    static isAdmin() { return this.getRole() === 'admin'; }
    static isAuthenticated() { return !!this.getToken(); }
    static requireAuth() {
        if (!this.isAuthenticated()) { window.location.href = '/login'; return false; }
        return true;
    }
    static requireAdmin() {
        if (!this.requireAuth()) return false;
        if (!this.isAdmin()) { window.location.href = '/dashboard'; return false; }
        return true;
    }
}

class API {
    static async request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        const token = Auth.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const options = { method, headers };
        if (body) options.body = JSON.stringify(body);
        const response = await fetch(`${API_BASE}${path}`, options);
        if (response.status === 401) { Auth.clear(); window.location.href = '/login'; throw new Error('Не авторизован'); }
        if (!response.ok) { const error = await response.json().catch(() => ({ detail: 'Ошибка запроса' })); throw new Error(error.detail || 'Ошибка запроса'); }
        return response.json();
    }
    static get(path) { return this.request('GET', path); }
    static post(path, body) { return this.request('POST', path, body); }
    static put(path, body) { return this.request('PUT', path, body); }
    static delete(path) { return this.request('DELETE', path); }
}

class Toast {
    static show(message, type = 'info') {
        let container = document.querySelector('.toast-container');
        if (!container) { container = document.createElement('div'); container.className = 'toast-container'; document.body.appendChild(container); }
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
    static success(msg) { this.show(msg, 'success'); }
    static error(msg) { this.show(msg, 'error'); }
    static info(msg) { this.show(msg, 'info'); }
}

function initLayout() {
    const username = Auth.getUsername();
    const role = Auth.getRole();
    const sidebarHTML = `
        <div class="sidebar-header">
            <h2>CV System</h2>
            <div class="user-info">${sanitize(username)} (${role === 'admin' ? t('adminRole') : t('operatorRole')})</div>
        </div>
        <nav class="sidebar-nav">
            <div class="nav-section">${t('main')}</div>
            <a href="/dashboard" class="nav-item ${location.pathname === '/dashboard' ? 'active' : ''}">
                <span class="nav-icon">📊</span> ${t('dashboard')}
            </a>
            <a href="/streams" class="nav-item ${location.pathname === '/streams' ? 'active' : ''}">
                <span class="nav-icon">🎥</span> ${t('streams')}
            </a>
            <a href="/counters" class="nav-item ${location.pathname === '/counters' ? 'active' : ''}">
                <span class="nav-icon">🔢</span> ${t('counters')}
            </a>
            ${role === 'admin' ? `
                <div class="nav-section">${t('admin')}</div>
                <a href="/users" class="nav-item ${location.pathname === '/users' ? 'active' : ''}">
                    <span class="nav-icon">👥</span> ${t('users')}
                </a>
                <a href="/training" class="nav-item ${location.pathname === '/training' ? 'active' : ''}">
                    <span class="nav-icon">🧠</span> ${t('training')}
                </a>
                <a href="/system" class="nav-item ${location.pathname === '/system' ? 'active' : ''}">
                    <span class="nav-icon">⚙️</span> ${t('system')}
                </a>
            ` : ''}
        </nav>
        <div class="sidebar-footer">
            <button class="btn btn-secondary" style="width:100%" onclick="logout()">${t('logout')}</button>
        </div>
    `;
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.innerHTML = sidebarHTML;
}

function logout() { Auth.clear(); window.location.href = '/login'; }
function showModal(id) { document.getElementById(id).classList.add('active'); }
function hideModal(id) { document.getElementById(id).classList.remove('active'); }
function formatDate(iso) { return new Date(iso).toLocaleString('ru-RU'); }

function applyTheme(theme) {
    const r = document.documentElement;
    if (theme === 'system') theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    if (theme === 'light') {
        r.style.setProperty('--bg-primary','#f5f5f5'); r.style.setProperty('--bg-secondary','#ffffff');
        r.style.setProperty('--bg-card','#ffffff'); r.style.setProperty('--bg-hover','#e8e8e8');
        r.style.setProperty('--border','#ddd'); r.style.setProperty('--text-primary','#1a1a1a');
        r.style.setProperty('--text-secondary','#666');
    } else {
        r.style.setProperty('--bg-primary','#0f1117'); r.style.setProperty('--bg-secondary','#1a1d27');
        r.style.setProperty('--bg-card','#212430'); r.style.setProperty('--bg-hover','#2a2d3a');
        r.style.setProperty('--border','#2e3240'); r.style.setProperty('--text-primary','#e8eaed');
        r.style.setProperty('--text-secondary','#9aa0a6');
    }
}

const _savedTheme = localStorage.getItem('theme') || 'dark';
applyTheme(_savedTheme);

const i18n = {
    ru: {
        dashboard: 'Панель управления', streams: 'Потоки', counters: 'Счётчики',
        users: 'Пользователи', training: 'Обучение', system: 'Система',
        main: 'Основное', admin: 'Администрирование', logout: 'Выйти',
        adminRole: 'админ', operatorRole: 'оператор',
        addStream: '+ Добавить поток', noStreams: 'Нет потоков', addStreamHint: 'Добавьте поток для начала работы',
        active: 'Активен', inactive: 'Неактивен', edit: 'Изменить', zonesAndLines: 'Зоны и линии',
        delete: 'Удалить', cancel: 'Отмена', save: 'Сохранить', create: 'Создать',
        totalStreams: 'Потоков', activeStreams: 'Активных', totalCounters: 'Счётчиков',
        todayDetections: 'Детекций сегодня', noData: 'Нет данных',
        name: 'Название', sourceType: 'Тип источника', sourcePath: 'Адрес источника',
        model: 'Модель', confidence: 'Порог уверенности', type: 'Тип',
        zone: 'Зона', line: 'Линия', addZone: 'Добавить зону', addLine: 'Добавить линию',
        zoneName: 'Название зоны', lineName: 'Название линии', direction: 'Направление',
        up: 'Вверх ↑', down: 'Вниз ↓', loadFrame: 'Загрузить кадр', clear: 'Очистить',
        saveZone: 'Сохранить зону', saveLine: 'Сохранить линию', noZones: 'Нет зон',
        noLines: 'Нет линий', counterName: 'Название', addCounter: 'Добавить счётчик',
        noCounters: 'Нет счётчиков', classes: 'Классы объектов', allClasses: 'Все классы',
        search: 'Поиск...', standard: 'Стандартные (YOLO)', custom: 'Кастомные',
        username: 'Логин', email: 'Email', password: 'Пароль', role: 'Роль',
        operator: 'Оператор', status: 'Статус', streams2: 'Потоки', actions: 'Действия',
        addUser: '+ Добавить пользователя', newPassword: 'Новый пароль',
        assignedStreams: 'Назначенные потоки', enterLogin: 'Введите логин',
        enterPassword: 'Введите пароль', signIn: 'Войти',
        platform: 'Платформа детекции и подсчёта объектов',
        general: 'Основные', metrics: 'Метрики', logs: 'Логи',
        server: 'Сервер', restartServer: 'Перезапустить сервер', restartConfirm: 'Перезапустить сервер?',
        appearance: 'Внешний вид', theme: 'Тема', dark: 'Тёмная', light: 'Светлая', sysTheme: 'Системная',
        language: 'Язык', customModels: 'Кастомные модели', cleanup: 'Очистить артефакты',
        noCustomModels: 'Нет кастомных моделей', deleteModelConfirm: 'Удалить',
        cpuCores: 'CPU по ядрам', netTraffic: 'Сетевой трафик (реальное время)',
        recv: 'Приём', send: 'Отдача', gpu: 'GPU', systemLogs: 'Логи системы (24ч)',
        refresh: 'Обновить', logsNotFound: 'Логи не найдены',
        topObjects: 'Популярные объекты', streamCounters: 'Счётчики потоков',
        noCountersConfig: 'Нет счётчиков',
        objectTraining: 'Обучение кастомных объектов', newObject: 'Новый объект',
        objectName: 'Название объекта', annotation: 'Разметка', captureFrame: 'Захватить кадр',
        resetFrame: 'Сбросить кадр', clearBbox: 'Очистить bbox', saveAnnotation: 'Сохранить разметку',
        frames: 'Кадры', training2: 'Обучение', epochs: 'Эпохи', baseModel: 'Базовая модель',
        startTraining: 'Начать обучение', noObjects: 'Нет объектов', open: 'Открыть',
        selectStream: 'Выберите поток', liveStream: 'Живое видео', capturedFrame: 'Кадр захвачен',
        drawBbox: 'Нарисуйте bbox на объекте', enterObjectName: 'Введите название объекта',
        needMoreFrames: 'Нужно минимум 5 кадров', ready: 'Готово', collecting: 'Сбор данных',
        pending: 'Новый', failed: 'Ошибка', trainingStatus: 'Обучение',
        newCounter: 'Новый счётчик', target: 'Цель', allClassFilter: 'Все классы',
        zoneType: 'Зона', lineType: 'Линия', withoutBinding: 'Без привязки',
    },
    en: {
        dashboard: 'Dashboard', streams: 'Streams', counters: 'Counters',
        users: 'Users', training: 'Training', system: 'System',
        main: 'Main', admin: 'Administration', logout: 'Logout',
        adminRole: 'admin', operatorRole: 'operator',
        addStream: '+ Add Stream', noStreams: 'No streams', addStreamHint: 'Add a stream to get started',
        active: 'Active', inactive: 'Inactive', edit: 'Edit', zonesAndLines: 'Zones & Lines',
        delete: 'Delete', cancel: 'Cancel', save: 'Save', create: 'Create',
        totalStreams: 'Streams', activeStreams: 'Active', totalCounters: 'Counters',
        todayDetections: 'Today Detections', noData: 'No data',
        name: 'Name', sourceType: 'Source Type', sourcePath: 'Source Path',
        model: 'Model', confidence: 'Confidence', type: 'Type',
        zone: 'Zone', line: 'Line', addZone: 'Add Zone', addLine: 'Add Line',
        zoneName: 'Zone Name', lineName: 'Line Name', direction: 'Direction',
        up: 'Up ↑', down: 'Down ↓', loadFrame: 'Capture Frame', clear: 'Clear',
        saveZone: 'Save Zone', saveLine: 'Save Line', noZones: 'No zones',
        noLines: 'No lines', counterName: 'Name', addCounter: 'Add Counter',
        noCounters: 'No counters', classes: 'Object Classes', allClasses: 'All classes',
        search: 'Search...', standard: 'Standard (YOLO)', custom: 'Custom',
        username: 'Username', email: 'Email', password: 'Password', role: 'Role',
        operator: 'Operator', status: 'Status', streams2: 'Streams', actions: 'Actions',
        addUser: '+ Add User', newPassword: 'New Password',
        assignedStreams: 'Assigned Streams', enterLogin: 'Enter username',
        enterPassword: 'Enter password', signIn: 'Sign In',
        platform: 'Object Detection & Counting Platform',
        general: 'General', metrics: 'Metrics', logs: 'Logs',
        server: 'Server', restartServer: 'Restart Server', restartConfirm: 'Restart server?',
        appearance: 'Appearance', theme: 'Theme', dark: 'Dark', light: 'Light', sysTheme: 'System',
        language: 'Language', customModels: 'Custom Models', cleanup: 'Cleanup artifacts',
        noCustomModels: 'No custom models', deleteModelConfirm: 'Delete',
        cpuCores: 'CPU Cores', netTraffic: 'Network Traffic (real-time)',
        recv: 'Download', send: 'Upload', gpu: 'GPU', systemLogs: 'System Logs (24h)',
        refresh: 'Refresh', logsNotFound: 'No logs found',
        topObjects: 'Top Objects', streamCounters: 'Stream Counters',
        noCountersConfig: 'No counters',
        objectTraining: 'Custom Object Training', newObject: 'New Object',
        objectName: 'Object Name', annotation: 'Annotation', captureFrame: 'Capture Frame',
        resetFrame: 'Reset Frame', clearBbox: 'Clear BBox', saveAnnotation: 'Save Annotation',
        frames: 'Frames', training2: 'Training', epochs: 'Epochs', baseModel: 'Base Model',
        startTraining: 'Start Training', noObjects: 'No objects', open: 'Open',
        selectStream: 'Select stream', liveStream: 'Live video', capturedFrame: 'Frame captured',
        drawBbox: 'Draw bbox on object', enterObjectName: 'Enter object name',
        needMoreFrames: 'Need at least 5 frames', ready: 'Ready', collecting: 'Collecting',
        pending: 'New', failed: 'Failed', trainingStatus: 'Training',
        newCounter: 'New Counter', target: 'Target', allClassFilter: 'All classes',
        zoneType: 'Zone', lineType: 'Line', withoutBinding: 'Without binding',
    }
};

function t(key) {
    const lang = localStorage.getItem('lang') || 'ru';
    return (i18n[lang] && i18n[lang][key]) || (i18n.ru[key]) || key;
}

function getLang() { return localStorage.getItem('lang') || 'ru'; }

function sanitize(str) {
    if (str == null) return '';
    const s = String(str);
    const el = document.createElement('span');
    el.textContent = s;
    return el.innerHTML;
}
