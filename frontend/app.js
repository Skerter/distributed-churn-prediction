/* ======================================================
   Distributed Churn Prediction — Dashboard JS
   Vanilla JavaScript, без зависимостей.
   URL сервисов приходят из окружения контейнера; localhost используется локально.
   ====================================================== */

// ====================== КОНФИГУРАЦИЯ ======================

// В Docker placeholders заменяются entrypoint-скриптом. При прямом локальном
// открытии фронтенда используем сервисы на стандартных локальных портах.
const API_URL_TEMPLATE = '__API_BASE_URL__';
const MLFLOW_URL_TEMPLATE = '__MLFLOW_URL__';

function resolveServiceUrl(template, fallback) {
    const isPlaceholder = template.startsWith('__') && template.endsWith('__');
    return isPlaceholder ? fallback : template.replace(/\/$/, '');
}

const API_BASE_URL = resolveServiceUrl(API_URL_TEMPLATE, 'http://127.0.0.1:8000');
const MLFLOW_BASE_URL = resolveServiceUrl(MLFLOW_URL_TEMPLATE, 'http://127.0.0.1:5000');

// Интервал автополлинга статуса (миллисекунды)
const POLL_INTERVAL_MS = 3000;

// Статусы, при достижении которых поллинг останавливается
const TERMINAL_STATUSES = ['succeeded', 'failed'];

// Ключи в localStorage
const LS_THEME = 'dcp-theme';
const LS_HISTORY = 'dcp-history';

// Максимум записей в истории
const HISTORY_LIMIT = 10;


// ====================== ГЛОБАЛЬНОЕ СОСТОЯНИЕ ======================

// Текущий run_id запущенного пайплайна. null, если ничего не запускалось.
let currentRunId = null;

// Идентификатор активного setInterval для поллинга. null, если поллинг не активен.
let pollIntervalId = null;

// Не допускаем наложения запросов одного run, но разрешаем мгновенно
// переключиться на другой элемент истории.
let activeStatusRunId = null;

// Таймер длительности текущего запуска
let durationTimerId = null;
let runStartTime = null;

// История запусков сессии: [{ run_id, status, startedAt, finishedAt, durationMs, payload }]
let history = [];

// Состояние статистики (показываемые значения, чтобы плавно анимировать)
const statsState = { total: 0, success: 0, failed: 0 };


// ====================== ССЫЛКИ НА DOM-ЭЛЕМЕНТЫ ======================

// Получаем все нужные элементы один раз при загрузке скрипта.
const els = {
    // Health Check
    healthBtn:      document.getElementById('healthBtn'),
    healthOutput:   document.getElementById('healthOutput'),
    healthDot:      document.getElementById('healthDot'),
    liveDot:        document.getElementById('liveDot'),
    mlflowLink:     document.getElementById('mlflowLink'),
    appVersion:     document.getElementById('appVersion'),

    // Run Pipeline
    runBtn:         document.getElementById('runBtn'),
    runOutput:      document.getElementById('runOutput'),
    runIdDisplay:   document.getElementById('runIdDisplay'),
    runIdValue:     document.getElementById('runIdValue'),
    copyRunId:      document.getElementById('copyRunId'),

    // Чекбоксы параметров
    execute:        document.getElementById('execute'),
    skipLoad:       document.getElementById('skip_load'),
    skipFeatures:   document.getElementById('skip_features'),
    skipTrain:      document.getElementById('skip_train'),
    skipEval:       document.getElementById('skip_eval'),

    // Status
    statusBtn:      document.getElementById('statusBtn'),
    statusOutput:   document.getElementById('statusOutput'),
    statusBadge:    document.getElementById('statusBadge'),
    statusInfo:     document.getElementById('statusInfo'),
    statusInfoText: document.getElementById('statusInfoText'),
    autoPoll:       document.getElementById('autoPoll'),
    durationTimer:  document.getElementById('durationTimer'),
    progressBar:    document.getElementById('progressBar'),
    progressSteps:  document.getElementById('progressSteps'),
    planValue:      document.getElementById('planValue'),

    // Тема
    themeToggle:    document.getElementById('themeToggle'),

    // Статистика
    statTotal:        document.getElementById('statTotal'),
    statSuccess:      document.getElementById('statSuccess'),
    statSuccessRate:  document.getElementById('statSuccessRate'),
    statFailed:       document.getElementById('statFailed'),
    statAvgTime:      document.getElementById('statAvgTime'),

    // История
    historyList:    document.getElementById('historyList'),
    clearHistory:   document.getElementById('clearHistory'),

    // Toast
    toastContainer: document.getElementById('toastContainer'),
};


// ====================== TOAST УВЕДОМЛЕНИЯ ======================

/**
 * Показывает плавающее уведомление в правом нижнем углу.
 * Уведомление сам себя убирает через timeout миллисекунд.
 */
function toast({ title, message = '', kind = 'info', timeout = 4000 }) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.dataset.kind = kind;

    const iconChar = { success: '✓', error: '!', warning: '!', info: 'i' }[kind] || 'i';

    el.innerHTML = `
        <span class="toast-icon">${iconChar}</span>
        <div class="toast-body">
            <div class="toast-title"></div>
            <div class="toast-message"></div>
        </div>
        <button class="toast-close" aria-label="Закрыть">×</button>
    `;
    // Используем textContent, чтобы избежать XSS, если title/message приходят извне
    el.querySelector('.toast-title').textContent = title;
    el.querySelector('.toast-message').textContent = message;

    let dismissed = false;
    const dismiss = () => {
        if (dismissed) return;
        dismissed = true;
        el.classList.add('toast-out');
        setTimeout(() => el.remove(), 250);
    };

    el.querySelector('.toast-close').addEventListener('click', dismiss);
    els.toastContainer.appendChild(el);

    if (timeout > 0) setTimeout(dismiss, timeout);
}


// ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================

/**
 * Красиво форматирует JSON-объект для вывода в <pre>.
 * Также добавляет короткую анимацию подсветки на элемент.
 */
function renderJSON(element, data, isError = false) {
    element.textContent = JSON.stringify(data, null, 2);
    element.classList.toggle('error', isError);

    // Рестартим CSS-анимацию (убираем и добавляем класс)
    element.classList.remove('updated');
    void element.offsetWidth;  // принудительный reflow, чтобы анимация перезапустилась
    element.classList.add('updated');
}

/**
 * Переключает кнопку в состояние загрузки (показывает спиннер).
 */
function setButtonLoading(button, isLoading) {
    button.classList.toggle('loading', isLoading);
    button.disabled = isLoading;
}

/**
 * Форматирует миллисекунды в "MM:SS" для таймера длительности.
 */
function formatDuration(ms) {
    if (ms == null || isNaN(ms)) return '—';
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

/**
 * Универсальная обёртка над fetch с обработкой ошибок.
 * Возвращает разобранный JSON или бросает исключение с понятным сообщением.
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            ...(options.headers || {}),
        },
    });

    // Пытаемся разобрать тело ответа в JSON независимо от статуса.
    // Если ответ не JSON (например, HTML с ошибкой) — возвращаем текст.
    let body;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        body = await response.json();
    } else {
        body = { raw: await response.text() };
    }

    if (!response.ok) {
        // Прокидываем структурированную ошибку наверх
        const err = new Error(`HTTP ${response.status} ${response.statusText}`);
        err.status = response.status;
        err.body = body;
        throw err;
    }

    return body;
}


// ====================== ТЕМА ======================

/**
 * Переключает тему и сохраняет выбор в localStorage.
 */
function toggleTheme() {
    const current = document.documentElement.dataset.theme || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try {
        localStorage.setItem(LS_THEME, next);
    } catch (_) {
        // Тема всё равно меняется для текущей вкладки.
    }
    syncThemeUI();

    toast({
        kind: 'info',
        title: `Тема: ${next === 'dark' ? 'тёмная' : 'светлая'}`,
        message: 'Можно переключить клавишей T',
        timeout: 1800,
    });
}

function syncThemeUI() {
    const isDark = document.documentElement.dataset.theme === 'dark';
    els.themeToggle.setAttribute('aria-pressed', String(isDark));
    els.themeToggle.setAttribute('aria-label', isDark ? 'Включить светлую тему' : 'Включить тёмную тему');
    document.querySelector('meta[name="theme-color"]')
        ?.setAttribute('content', isDark ? '#0d1210' : '#f2f3ed');
}


// ====================== СТАТИСТИКА ======================

/**
 * Плавно анимирует число от текущего к целевому за указанное время.
 */
function animateNumber(element, from, to, durationMs = 600) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        element.textContent = to;
        return;
    }

    const start = performance.now();
    const delta = to - from;

    function step(now) {
        const t = Math.min(1, (now - start) / durationMs);
        // ease-out cubic
        const eased = 1 - Math.pow(1 - t, 3);
        const value = Math.round(from + delta * eased);
        element.textContent = value;
        if (t < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
}

/**
 * Пересчитывает и отрисовывает все статистические показатели на основе history.
 */
function refreshStats() {
    const total = history.length;
    const success = history.filter(h => h.status === 'succeeded').length;
    const failed = history.filter(h => h.status === 'failed').length;

    if (total !== statsState.total)     animateNumber(els.statTotal,   statsState.total,   total);
    if (success !== statsState.success) animateNumber(els.statSuccess, statsState.success, success);
    if (failed !== statsState.failed)   animateNumber(els.statFailed,  statsState.failed,  failed);

    statsState.total = total;
    statsState.success = success;
    statsState.failed = failed;

    // Процент успешности (или прочерк, если запусков ещё не было)
    const completed = success + failed;
    const successRate = completed > 0 ? Math.round((success / completed) * 100) : 0;
    els.statSuccessRate.textContent = completed > 0 ? `${successRate}% успеха` : '0% успеха';

    // Среднее время завершённых запусков
    const withDuration = history.filter(h => h.durationMs != null && TERMINAL_STATUSES.includes(h.status));
    if (withDuration.length > 0) {
        const avg = withDuration.reduce((sum, h) => sum + h.durationMs, 0) / withDuration.length;
        els.statAvgTime.textContent = formatDuration(avg);
    } else {
        els.statAvgTime.textContent = '—';
    }
}


// ====================== ИСТОРИЯ ЗАПУСКОВ ======================

/**
 * Сохраняет историю в localStorage (с защитой от переполнения квоты).
 */
function persistHistory() {
    try {
        localStorage.setItem(LS_HISTORY, JSON.stringify(history));
    } catch (e) {
        console.warn('Не удалось сохранить историю в localStorage:', e);
    }
}

/**
 * Загружает историю из localStorage при старте.
 */
function loadHistory() {
    try {
        const raw = localStorage.getItem(LS_HISTORY);
        const stored = raw ? JSON.parse(raw) : [];
        history = Array.isArray(stored)
            ? stored.filter(item => item && typeof item.run_id === 'string').slice(0, HISTORY_LIMIT)
            : [];
    } catch (e) {
        history = [];
    }
}

/**
 * Добавляет новый запуск в начало истории.
 */
function addToHistory(entry) {
    history.unshift(entry);
    if (history.length > HISTORY_LIMIT) history = history.slice(0, HISTORY_LIMIT);
    persistHistory();
    renderHistory();
    refreshStats();
}

/**
 * Обновляет существующую запись истории по run_id (например, при смене статуса).
 */
function updateHistoryEntry(runId, patch) {
    const entry = history.find(h => h.run_id === runId);
    if (!entry) return;
    Object.assign(entry, patch);
    persistHistory();
    renderHistory();
    refreshStats();
}

/**
 * Отрисовывает список истории в DOM.
 */
function renderHistory() {
    if (history.length === 0) {
        els.historyList.innerHTML = `
            <div class="history-empty">
                <span class="empty-mark" aria-hidden="true">↳</span>
                <span>Здесь появятся ваши запуски</span>
            </div>
        `;
        return;
    }

    els.historyList.innerHTML = '';
    history.forEach(entry => {
        const normalizedStatus = typeof entry.status === 'string'
            ? entry.status.toLowerCase()
            : 'unknown';
        const safeStatus = ['queued', 'running', 'succeeded', 'failed'].includes(normalizedStatus)
            ? normalizedStatus
            : 'unknown';
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'history-item';
        if (entry.run_id === currentRunId) item.classList.add('active');
        item.dataset.runId = entry.run_id;

        const startedAt = entry.startedAt == null ? null : new Date(entry.startedAt);
        const time = !startedAt || Number.isNaN(startedAt.getTime())
            ? 'время неизвестно'
            : startedAt.toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false,
            });
        const shortId = entry.run_id.length > 18 ? entry.run_id.slice(0, 16) + '…' : entry.run_id;
        item.setAttribute('aria-label', `Открыть запуск ${entry.run_id}, статус ${safeStatus}`);

        const dot = document.createElement('span');
        dot.className = 'history-status-dot';
        dot.dataset.status = safeStatus;

        const id = document.createElement('span');
        id.className = 'history-id';
        id.title = entry.run_id;
        id.textContent = shortId;

        const timestamp = document.createElement('span');
        timestamp.className = 'history-time';
        timestamp.textContent = time;

        const status = document.createElement('span');
        status.className = 'history-status';
        status.textContent = safeStatus;

        item.append(dot, id, timestamp, status);

        // Клик по элементу истории — переключиться на этот run для отслеживания
        item.addEventListener('click', () => switchToHistoricalRun(entry.run_id));

        els.historyList.appendChild(item);
    });
}

/**
 * Делает указанный run_id из истории "текущим" — позволяет посмотреть его статус.
 */
async function switchToHistoricalRun(runId) {
    stopPolling();
    stopDurationTimer();
    els.durationTimer.hidden = true;
    currentRunId = runId;
    els.runIdValue.textContent = runId;
    els.runIdDisplay.hidden = false;
    els.statusBtn.disabled = false;

    const entry = history.find(h => h.run_id === runId);
    if (entry) {
        const entryStatus = typeof entry.status === 'string' ? entry.status.toLowerCase() : 'idle';
        updateStatusBadge(entryStatus);
        els.statusInfoText.textContent = `Просмотр запуска: ${runId}`;
        els.statusInfo.classList.add('active');
        if (!TERMINAL_STATUSES.includes(entryStatus)) {
            startDurationTimer(entry.startedAt);
        } else if (entry.durationMs != null) {
            els.durationTimer.hidden = false;
            els.durationTimer.textContent = formatDuration(entry.durationMs);
        }
    }

    renderHistory();
    await fetchStatus(true);
    if (
        els.autoPoll.checked
        && !TERMINAL_STATUSES.includes(els.statusBadge.dataset.status)
    ) {
        startPolling();
    }

    toast({
        kind: 'info',
        title: 'Переключено',
        message: `Отслеживается ${runId.slice(0, 18)}…`,
        timeout: 2200,
    });
}

/**
 * Чистит историю по запросу пользователя (с подтверждением через toast).
 */
function clearHistoryRequest() {
    if (history.length === 0) {
        toast({ kind: 'info', title: 'История уже пуста' });
        return;
    }
    if (!confirm('Очистить всю историю запусков этой сессии?')) return;
    history = [];
    persistHistory();
    renderHistory();
    refreshStats();
    toast({ kind: 'success', title: 'История очищена' });
}


// ====================== ТАЙМЕР ДЛИТЕЛЬНОСТИ ======================

/**
 * Запускает таймер длительности (тикает раз в секунду).
 */
function startDurationTimer(startedAt = Date.now()) {
    stopDurationTimer();
    const parsedStart = startedAt == null ? NaN : new Date(startedAt).getTime();
    runStartTime = Number.isNaN(parsedStart) ? Date.now() : parsedStart;
    els.durationTimer.hidden = false;
    els.durationTimer.textContent = '00:00';

    durationTimerId = setInterval(() => {
        els.durationTimer.textContent = formatDuration(Date.now() - runStartTime);
    }, 1000);
}

function stopDurationTimer() {
    if (durationTimerId) {
        clearInterval(durationTimerId);
        durationTimerId = null;
    }
}

function getPipelineStage(data) {
    return data?.stage
        || data?.current_step
        || data?.step
        || data?.metadata?.stage
        || data?.metadata?.current_step
        || data?.metadata?.step
        || null;
}

function setProgressValue(value) {
    const progress = els.progressBar.parentElement;
    progress?.setAttribute('aria-valuenow', String(Math.round(value)));
}


// ====================== ПРОГРЕСС-БАР ПО ШАГАМ ======================

const STEP_ORDER = ['load', 'features', 'train', 'eval', 'done'];

/**
 * Обновляет прогресс-бар и подсветку шагов на основе данных запуска.
 * Использует поле stage/current_step из ответа API, если оно есть;
 * иначе подбирает прогресс по статусу.
 */
function updateProgress(status, data) {
    const lowerStatus = (status || '').toLowerCase();

    // Сбрасываем классы шагов
    els.progressSteps.querySelectorAll('.step').forEach(s => {
        s.classList.remove('active', 'done');
    });

    els.progressBar.classList.remove('indeterminate', 'success', 'failed');

    if (lowerStatus === 'idle' || !status) {
        els.progressBar.style.width = '0%';
        setProgressValue(0);
        return;
    }

    if (lowerStatus === 'queued') {
        els.progressBar.style.width = '';
        els.progressBar.classList.add('indeterminate');
        setProgressValue(0);
        return;
    }

    if (lowerStatus === 'succeeded') {
        els.progressBar.style.width = '100%';
        setProgressValue(100);
        els.progressBar.classList.add('success');
        els.progressSteps.querySelectorAll('.step').forEach(s => s.classList.add('done'));
        return;
    }

    if (lowerStatus === 'failed') {
        // Бэр идёт до того места, где упало (если известно)
        els.progressBar.classList.add('failed');
        const stage = getPipelineStage(data);
        const idx = STEP_ORDER.indexOf(stage);
        const pct = idx >= 0 ? ((idx + 1) / STEP_ORDER.length) * 100 : 50;
        els.progressBar.style.width = `${pct}%`;
        setProgressValue(pct);
        if (idx >= 0) {
            STEP_ORDER.slice(0, idx).forEach(name => {
                els.progressSteps.querySelector(`[data-step="${name}"]`)?.classList.add('done');
            });
            els.progressSteps.querySelector(`[data-step="${stage}"]`)?.classList.add('active');
        }
        return;
    }

    // running — пытаемся определить шаг
    if (lowerStatus === 'running') {
        const stage = getPipelineStage(data);
        const idx = STEP_ORDER.indexOf(stage);

        if (idx >= 0) {
            const pct = ((idx + 0.5) / STEP_ORDER.length) * 100;
            els.progressBar.style.width = `${pct}%`;
            setProgressValue(pct);
            STEP_ORDER.slice(0, idx).forEach(name => {
                els.progressSteps.querySelector(`[data-step="${name}"]`)?.classList.add('done');
            });
            els.progressSteps.querySelector(`[data-step="${stage}"]`)?.classList.add('active');
        } else {
            // Нет точной информации о шаге — показываем неопределённую анимацию
            els.progressBar.style.width = '';
            els.progressBar.classList.add('indeterminate');
            setProgressValue(0);
        }
    }
}


// ====================== БЛОК 1: HEALTH CHECK ======================

/**
 * Обновляет метаданные интерфейса значениями, которые backend прочитал из configs/base.yaml.
 */
function syncAppMetadata(data) {
    const version = typeof data?.app_version === 'string' ? data.app_version.trim() : '';
    if (version && els.appVersion) {
        els.appVersion.textContent = version;
        els.appVersion.title = `Версия из configs/base.yaml: ${version}`;
    }
}

/**
 * Делает GET /health и отображает ответ.
 */
async function checkHealth() {
    setButtonLoading(els.healthBtn, true);

    try {
        const data = await apiRequest('/health', { method: 'GET' });
        syncAppMetadata(data);

        // Считаем сервер живым, если ответ пришёл со статусом 200
        els.healthDot.dataset.status = 'ok';
        els.healthDot.setAttribute('aria-label', 'API доступен');
        els.liveDot.dataset.status = 'ok';
        renderJSON(els.healthOutput, data);

        toast({ kind: 'success', title: 'API доступен', message: API_BASE_URL, timeout: 2000 });
    } catch (error) {
        els.healthDot.dataset.status = 'error';
        els.healthDot.setAttribute('aria-label', 'API недоступен');
        els.liveDot.dataset.status = 'error';

        // Если сервер недоступен — fetch бросает TypeError
        const errorPayload = error.body || {
            error: error.message,
            hint: 'Проверьте, что FastAPI сервер запущен на ' + API_BASE_URL,
        };
        renderJSON(els.healthOutput, errorPayload, true);

        toast({
            kind: 'error',
            title: 'API недоступен',
            message: error.message || 'Сервер не отвечает',
        });
    } finally {
        setButtonLoading(els.healthBtn, false);
    }
}


// ====================== БЛОК 2: ЗАПУСК PIPELINE ======================

/**
 * Собирает payload из чекбоксов и шлёт POST /pipeline/runs.
 * Сохраняет run_id в глобальную переменную и в интерфейсе.
 */
async function runPipeline() {
    // Собираем тело запроса из значений чекбоксов
    const payload = {
        execute:        els.execute.checked,
        skip_load:      els.skipLoad.checked,
        skip_features:  els.skipFeatures.checked,
        skip_train:     els.skipTrain.checked,
        skip_eval:      els.skipEval.checked,
    };

    stopPolling();
    stopDurationTimer();
    els.durationTimer.hidden = true;
    setButtonLoading(els.runBtn, true);

    try {
        const data = await apiRequest('/pipeline/runs', {
            method: 'POST',
            body: JSON.stringify(payload),
        });

        // Извлекаем run_id из ответа и сохраняем
        if (data && data.run_id) {
            currentRunId = data.run_id;

            // Показываем блок с run_id
            els.runIdValue.textContent = currentRunId;
            els.runIdDisplay.hidden = false;

            // Активируем кнопку проверки статуса
            els.statusBtn.disabled = false;

            // Обновляем информационную строку в блоке статуса
            els.statusInfo.classList.add('active');
            els.statusInfoText.textContent = `Отслеживается запуск: ${currentRunId}`;

            // Сбрасываем бейдж и прогресс в стартовое состояние
            updateStatusBadge('queued');
            updateProgress('queued', null);

            // Запускаем таймер длительности
            startDurationTimer();

            // Добавляем запись в историю
            addToHistory({
                run_id: currentRunId,
                status: 'queued',
                startedAt: Date.now(),
                finishedAt: null,
                durationMs: null,
                payload,
            });

            // Сразу делаем первый запрос статуса и (если включено) запускаем поллинг
            await fetchStatus(false);
            if (
                els.autoPoll.checked
                && !TERMINAL_STATUSES.includes(els.statusBadge.dataset.status)
            ) {
                startPolling();
            }

            toast({
                kind: 'success',
                title: 'Pipeline запущен',
                message: `run_id: ${currentRunId.slice(0, 20)}…`,
            });
        }

        renderJSON(els.runOutput, data);
    } catch (error) {
        const errorPayload = error.body || {
            error: error.message,
            hint: 'Не удалось запустить пайплайн. Проверьте доступность ' + API_BASE_URL,
        };
        renderJSON(els.runOutput, errorPayload, true);

        toast({
            kind: 'error',
            title: 'Не удалось запустить',
            message: error.message || 'Ошибка POST /pipeline/runs',
        });
    } finally {
        setButtonLoading(els.runBtn, false);
    }
}

/**
 * Копирует текущий run_id в буфер обмена.
 */
async function copyRunIdToClipboard() {
    if (!currentRunId) {
        toast({ kind: 'warning', title: 'Нет активного run_id' });
        return;
    }
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(currentRunId);
        } else {
            const input = document.createElement('textarea');
            input.value = currentRunId;
            input.setAttribute('readonly', '');
            input.style.position = 'fixed';
            input.style.opacity = '0';
            document.body.appendChild(input);
            input.select();
            const copied = document.execCommand('copy');
            input.remove();
            if (!copied) throw new Error('Clipboard API недоступен');
        }
        toast({ kind: 'success', title: 'run_id скопирован', message: currentRunId.slice(0, 24) + '…', timeout: 1800 });
    } catch (e) {
        toast({ kind: 'error', title: 'Не удалось скопировать', message: 'Возможно, нет доступа к clipboard' });
    }
}


// ====================== БЛОК 3: СТАТУС ПАЙПЛАЙНА ======================

/**
 * Применяет CSS-стилизацию бейджа в зависимости от статуса.
 */
function updateStatusBadge(status) {
    const safeStatus = (status || 'idle').toLowerCase();
    const labels = {
        idle: 'Ожидание',
        queued: 'В очереди',
        running: 'Выполняется',
        succeeded: 'Успешно',
        failed: 'Ошибка',
    };
    els.statusBadge.dataset.status = safeStatus;
    els.statusBadge.textContent = labels[safeStatus] || safeStatus;
}

/**
 * GET /pipeline/runs/{run_id} — получает свежий статус.
 * Если статус терминальный (succeeded/failed) — автоматически останавливает поллинг.
 */
async function fetchStatus(manual = false) {
    if (!currentRunId) {
        renderJSON(els.statusOutput, {
            error: 'Нет активного run_id',
            hint: 'Запустите Pipeline в блоке выше',
        }, true);
        return null;
    }

    const requestedRunId = currentRunId;
    if (activeStatusRunId === requestedRunId) return null;
    activeStatusRunId = requestedRunId;

    // Не показываем спиннер во время автополлинга, чтобы не моргала кнопка.
    // Спиннер ставим только если запрос инициирован вручную.
    const isManual = manual;
    if (isManual) setButtonLoading(els.statusBtn, true);

    try {
        const data = await apiRequest(`/pipeline/runs/${requestedRunId}`, { method: 'GET' });
        if (requestedRunId !== currentRunId) return data;
        els.liveDot.dataset.status = 'ok';

        // Обновляем бейдж и вывод
        if (data && data.status) {
            const lowerStatus = data.status.toLowerCase();
            updateStatusBadge(data.status);
            updateProgress(data.status, data);
            els.statusInfo.classList.add('active');

            // Обновляем запись истории на актуальный статус
            const entryPatch = { status: lowerStatus };
            const entry = history.find(item => item.run_id === requestedRunId);
            const wasTerminal = Boolean(entry && TERMINAL_STATUSES.includes(entry.status));

            // Если достигнут терминальный статус — глушим поллинг и таймер
            if (TERMINAL_STATUSES.includes(lowerStatus)) {
                stopPolling();
                stopDurationTimer();

                const apiStartedAt = data.started_at ? new Date(data.started_at).getTime() : NaN;
                const apiFinishedAt = data.finished_at ? new Date(data.finished_at).getTime() : NaN;
                const finishedAt = Number.isNaN(apiFinishedAt) ? Date.now() : apiFinishedAt;
                const startedAt = Number.isNaN(apiStartedAt) ? runStartTime : apiStartedAt;
                entryPatch.finishedAt = finishedAt;
                entryPatch.durationMs = entry?.durationMs
                    ?? (startedAt ? Math.max(0, finishedAt - startedAt) : null);

                els.statusInfoText.textContent =
                    `Запуск ${requestedRunId} завершён со статусом: ${data.status}`;
                els.durationTimer.hidden = entryPatch.durationMs == null;
                els.durationTimer.textContent = formatDuration(entryPatch.durationMs);

                if (!wasTerminal) {
                    toast({
                        kind: lowerStatus === 'succeeded' ? 'success' : 'error',
                        title: lowerStatus === 'succeeded' ? 'Pipeline завершён успешно' : 'Pipeline упал',
                        message: `Длительность: ${formatDuration(entryPatch.durationMs)}`,
                    });
                }
            } else {
                els.statusInfoText.textContent = `Отслеживается запуск: ${requestedRunId}`;
                if (!durationTimerId) {
                    startDurationTimer(data.started_at || entry?.startedAt || Date.now());
                }
            }

            updateHistoryEntry(requestedRunId, entryPatch);
        }

        renderJSON(els.statusOutput, data);
        return data;
    } catch (error) {
        if (requestedRunId !== currentRunId) return null;
        const errorPayload = error.body || {
            error: error.message,
            hint: 'Не удалось получить статус. Проверьте доступность ' + API_BASE_URL,
        };
        renderJSON(els.statusOutput, errorPayload, true);

        // При сетевой ошибке тоже останавливаем поллинг,
        // чтобы не спамить запросами в недоступный сервер.
        if (!error.status) {
            stopPolling();
            els.liveDot.dataset.status = 'error';
        }
        return null;
    } finally {
        if (isManual) setButtonLoading(els.statusBtn, false);
        if (activeStatusRunId === requestedRunId) activeStatusRunId = null;
    }
}

/**
 * Запускает автополлинг статуса каждые POLL_INTERVAL_MS миллисекунд.
 */
function startPolling() {
    // Защита от двойного запуска — гарантируем единственный активный интервал
    if (pollIntervalId) return;
    if (!currentRunId) return;
    if (TERMINAL_STATUSES.includes(els.statusBadge.dataset.status)) return;

    pollIntervalId = setInterval(() => fetchStatus(false), POLL_INTERVAL_MS);
    console.log(`[polling] started for run_id=${currentRunId}`);
}

/**
 * Останавливает автополлинг, если он был активен.
 */
function stopPolling() {
    if (pollIntervalId) {
        clearInterval(pollIntervalId);
        pollIntervalId = null;
        console.log('[polling] stopped');
    }
}

/**
 * Реакция на переключение тоггла "Автообновление".
 * Включает или выключает поллинг немедленно, без перезапуска пайплайна.
 */
function handleAutoPollToggle() {
    if (els.autoPoll.checked) {
        // Включаем только если есть активный run и он ещё не завершён
        const currentStatus = els.statusBadge.dataset.status;
        if (currentRunId && !TERMINAL_STATUSES.includes(currentStatus)) {
            startPolling();
            toast({ kind: 'info', title: 'Автообновление включено', timeout: 1500 });
        }
    } else {
        stopPolling();
        toast({ kind: 'info', title: 'Автообновление выключено', timeout: 1500 });
    }
}


// ====================== ПРЕСЕТЫ КОНФИГУРАЦИИ ======================

const PRESETS = {
    'full':       { execute: true,  skip_load: false, skip_features: false, skip_train: false, skip_eval: false },
    'train-only': { execute: true,  skip_load: true,  skip_features: true,  skip_train: false, skip_eval: true  },
    'dry-run':    { execute: false, skip_load: false, skip_features: false, skip_train: false, skip_eval: false },
    'reset':      { execute: true,  skip_load: false, skip_features: false, skip_train: false, skip_eval: false },
};

function getPipelineOptions() {
    return {
        execute: els.execute.checked,
        skip_load: els.skipLoad.checked,
        skip_features: els.skipFeatures.checked,
        skip_train: els.skipTrain.checked,
        skip_eval: els.skipEval.checked,
    };
}

function updatePlanSummary() {
    const options = getPipelineOptions();
    const skipped = [
        options.skip_load,
        options.skip_features,
        options.skip_train,
        options.skip_eval,
    ].filter(Boolean).length;
    const activeStages = 4 - skipped;
    const stageWord = activeStages === 1
        ? 'этап'
        : activeStages >= 2 && activeStages <= 4
            ? 'этапа'
            : 'этапов';
    const mode = options.execute ? 'реальный запуск' : 'dry-run';
    els.planValue.textContent = `${activeStages} ${stageWord} · ${mode}`;

    const comparablePresets = Object.entries(PRESETS).filter(([name]) => name !== 'reset');
    const activePreset = comparablePresets.find(([, preset]) =>
        Object.keys(options).every(key => options[key] === preset[key])
    )?.[0];

    document.querySelectorAll('.preset-btn').forEach(button => {
        button.classList.toggle('active', button.dataset.preset === activePreset);
        button.setAttribute('aria-pressed', String(button.dataset.preset === activePreset));
    });
}

function applyPreset(name) {
    const preset = PRESETS[name];
    if (!preset) return;
    els.execute.checked      = preset.execute;
    els.skipLoad.checked     = preset.skip_load;
    els.skipFeatures.checked = preset.skip_features;
    els.skipTrain.checked    = preset.skip_train;
    els.skipEval.checked     = preset.skip_eval;
    updatePlanSummary();

    toast({ kind: 'info', title: 'Пресет применён', message: name, timeout: 1500 });
}


// ====================== RIPPLE EFFECT ДЛЯ КНОПОК ======================

/**
 * Добавляет круговую "волну" в точке клика — лёгкий material-эффект.
 */
function attachRipple(button) {
    button.addEventListener('click', (event) => {
        if (button.disabled) return;
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const ripple = document.createElement('span');
        ripple.className = 'ripple';
        ripple.style.width = ripple.style.height = `${size}px`;
        ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
        ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
        button.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
    });
}


// ====================== ГОРЯЧИЕ КЛАВИШИ ======================

/**
 * Обрабатывает однобуквенные хоткеи: H, R, S, T, C.
 * Игнорирует, если фокус на input/textarea, чтобы не ломать ввод.
 */
function handleHotkey(event) {
    // Не перехватываем хоткеи, если пользователь печатает в поле ввода
    const tag = (event.target.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;

    const key = event.key.toLowerCase();
    switch (key) {
        case 'h':
            event.preventDefault();
            els.healthBtn.click();
            break;
        case 'r':
            event.preventDefault();
            els.runBtn.click();
            break;
        case 's':
            event.preventDefault();
            if (!els.statusBtn.disabled) els.statusBtn.click();
            break;
        case 't':
            event.preventDefault();
            toggleTheme();
            break;
        case 'c':
            // Не перехватываем Ctrl+C — это уже отсечено выше.
            // Просто C копирует текущий run_id.
            if (currentRunId) {
                event.preventDefault();
                copyRunIdToClipboard();
            }
            break;
        case '?':
            event.preventDefault();
            console.log('%cГорячие клавиши:', 'color:#4f46e5;font-weight:bold');
            console.log('H — health check\nR — run pipeline\nS — статус\nT — тема\nC — копировать run_id');
            toast({ kind: 'info', title: 'Подсказка', message: 'См. консоль (F12)' });
            break;
    }
}


// ====================== ПЕРИОДИЧЕСКИЙ HEALTH CHECK (тихий) ======================

/**
 * Раз в 30 секунд тихо пингует /health, чтобы держать индикатор подключения актуальным.
 * Без toast-уведомлений и без изменения JSON-вывода, только обновляет live-dot.
 */
async function silentHealthPing() {
    try {
        const data = await apiRequest('/health', { method: 'GET' });
        syncAppMetadata(data);
        els.liveDot.dataset.status = 'ok';
        document.getElementById('apiInfo').setAttribute('aria-label', `API доступен: ${API_BASE_URL}`);
    } catch {
        els.liveDot.dataset.status = 'error';
        document.getElementById('apiInfo').setAttribute('aria-label', `API недоступен: ${API_BASE_URL}`);
    }
}


// ====================== ИНИЦИАЛИЗАЦИЯ ======================

// Вешаем обработчики событий после загрузки скрипта.
els.healthBtn.addEventListener('click', checkHealth);
els.runBtn.addEventListener('click', runPipeline);
// Передаём true, чтобы fetchStatus знал, что это ручной вызов и показал спиннер
els.statusBtn.addEventListener('click', () => fetchStatus(true));
els.autoPoll.addEventListener('change', handleAutoPollToggle);
els.themeToggle.addEventListener('click', toggleTheme);
els.copyRunId.addEventListener('click', copyRunIdToClipboard);
els.clearHistory.addEventListener('click', clearHistoryRequest);

// Хоткеи
document.addEventListener('keydown', handleHotkey);

// Ripple-эффект для всех основных кнопок
[els.healthBtn, els.runBtn, els.statusBtn].forEach(attachRipple);

// Пресеты конфигурации
document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => applyPreset(btn.dataset.preset));
});

[els.execute, els.skipLoad, els.skipFeatures, els.skipTrain, els.skipEval].forEach(input => {
    input.addEventListener('change', updatePlanSummary);
});

// На случай закрытия вкладки — корректно останавливаем интервал
window.addEventListener('beforeunload', () => {
    stopPolling();
    stopDurationTimer();
});

// Показываем реальный адрес бэкенда в заголовке
document.getElementById('apiUrl').textContent = API_BASE_URL.replace(/^https?:\/\//, '');
document.getElementById('apiInfo').title = API_BASE_URL;
els.mlflowLink.href = MLFLOW_BASE_URL;
els.mlflowLink.title = `Открыть MLflow: ${MLFLOW_BASE_URL}`;

syncThemeUI();
updatePlanSummary();

// Восстанавливаем историю и отрисовываем
loadHistory();
renderHistory();
refreshStats();

// Тихий пинг сервера на старте и каждые 30 сек
silentHealthPing();
setInterval(silentHealthPing, 30000);

// Сообщаем пользователю в консоль, что фронт готов к работе
console.log('%c[Distributed Churn Prediction] Dashboard initialized', 'color: #4f46e5; font-weight: bold');
console.log('API base URL:', API_BASE_URL);
console.log('MLflow URL:', MLFLOW_BASE_URL);
console.log('Нажмите ? для списка горячих клавиш');
