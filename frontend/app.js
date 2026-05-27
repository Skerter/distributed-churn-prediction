/* ======================================================
   Distributed Churn Prediction — Dashboard JS
   Vanilla JavaScript, без зависимостей.
   Работает с FastAPI бэкендом на http://127.0.0.1:8000
   ====================================================== */

// ====================== КОНФИГУРАЦИЯ ======================

// Базовый URL бэкенда. Меняется в одном месте, если адрес поменяется.
const API_BASE_URL = '__API_BASE_URL__';

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

    const dismiss = () => {
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
    localStorage.setItem(LS_THEME, next);

    toast({
        kind: 'info',
        title: `Тема: ${next === 'dark' ? 'тёмная' : 'светлая'}`,
        message: 'Можно переключить клавишей T',
        timeout: 1800,
    });
}


// ====================== СТАТИСТИКА ======================

/**
 * Плавно анимирует число от текущего к целевому за указанное время.
 */
function animateNumber(element, from, to, durationMs = 600) {
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
        if (raw) history = JSON.parse(raw) || [];
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
        els.historyList.innerHTML = '<div class="history-empty">История пуста — запустите первый пайплайн</div>';
        return;
    }

    els.historyList.innerHTML = '';
    history.forEach(entry => {
        const item = document.createElement('div');
        item.className = 'history-item';
        if (entry.run_id === currentRunId) item.classList.add('active');
        item.dataset.runId = entry.run_id;

        const time = new Date(entry.startedAt).toLocaleTimeString('ru-RU', { hour12: false });
        const shortId = entry.run_id.length > 18 ? entry.run_id.slice(0, 16) + '…' : entry.run_id;

        item.innerHTML = `
            <span class="history-status-dot" data-status="${entry.status}"></span>
            <span class="history-id" title="${entry.run_id}"></span>
            <span class="history-time">${time}</span>
            <span class="history-status">${entry.status}</span>
        `;
        item.querySelector('.history-id').textContent = shortId;

        // Клик по элементу истории — переключиться на этот run для отслеживания
        item.addEventListener('click', () => switchToHistoricalRun(entry.run_id));

        els.historyList.appendChild(item);
    });
}

/**
 * Делает указанный run_id из истории "текущим" — позволяет посмотреть его статус.
 */
function switchToHistoricalRun(runId) {
    currentRunId = runId;
    els.runIdValue.textContent = runId;
    els.runIdDisplay.hidden = false;
    els.statusBtn.disabled = false;

    const entry = history.find(h => h.run_id === runId);
    if (entry) {
        updateStatusBadge(entry.status);
        els.statusInfoText.textContent = `Просмотр запуска: ${runId}`;
        els.statusInfo.classList.add('active');
    }

    renderHistory();
    fetchStatus(true);

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
function startDurationTimer() {
    stopDurationTimer();
    runStartTime = Date.now();
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
        return;
    }

    if (lowerStatus === 'queued') {
        els.progressBar.classList.add('indeterminate');
        return;
    }

    if (lowerStatus === 'succeeded') {
        els.progressBar.style.width = '100%';
        els.progressBar.classList.add('success');
        els.progressSteps.querySelectorAll('.step').forEach(s => s.classList.add('done'));
        return;
    }

    if (lowerStatus === 'failed') {
        // Бэр идёт до того места, где упало (если известно)
        els.progressBar.classList.add('failed');
        const stage = (data && (data.stage || data.current_step || data.step)) || null;
        const idx = STEP_ORDER.indexOf(stage);
        const pct = idx >= 0 ? ((idx + 1) / STEP_ORDER.length) * 100 : 50;
        els.progressBar.style.width = `${pct}%`;
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
        const stage = (data && (data.stage || data.current_step || data.step)) || null;
        const idx = STEP_ORDER.indexOf(stage);

        if (idx >= 0) {
            const pct = ((idx + 0.5) / STEP_ORDER.length) * 100;
            els.progressBar.style.width = `${pct}%`;
            STEP_ORDER.slice(0, idx).forEach(name => {
                els.progressSteps.querySelector(`[data-step="${name}"]`)?.classList.add('done');
            });
            els.progressSteps.querySelector(`[data-step="${stage}"]`)?.classList.add('active');
        } else {
            // Нет точной информации о шаге — показываем неопределённую анимацию
            els.progressBar.classList.add('indeterminate');
        }
    }
}


// ====================== БЛОК 1: HEALTH CHECK ======================

/**
 * Делает GET /health и отображает ответ.
 */
async function checkHealth() {
    setButtonLoading(els.healthBtn, true);

    try {
        const data = await apiRequest('/health', { method: 'GET' });

        // Считаем сервер живым, если ответ пришёл со статусом 200
        els.healthDot.dataset.status = 'ok';
        els.liveDot.dataset.status = 'ok';
        renderJSON(els.healthOutput, data);

        toast({ kind: 'success', title: 'API доступен', message: API_BASE_URL, timeout: 2000 });
    } catch (error) {
        els.healthDot.dataset.status = 'error';
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
            await fetchStatus();
            if (els.autoPoll.checked) {
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
        await navigator.clipboard.writeText(currentRunId);
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
    els.statusBadge.dataset.status = safeStatus;
    els.statusBadge.textContent = safeStatus;
}

/**
 * GET /pipeline/runs/{run_id} — получает свежий статус.
 * Если статус терминальный (succeeded/failed) — автоматически останавливает поллинг.
 */
async function fetchStatus() {
    if (!currentRunId) {
        renderJSON(els.statusOutput, {
            error: 'Нет активного run_id',
            hint: 'Запустите Pipeline в блоке выше',
        }, true);
        return;
    }

    // Не показываем спиннер во время автополлинга, чтобы не моргала кнопка.
    // Спиннер ставим только если запрос инициирован вручную.
    const isManual = !pollIntervalId || arguments[0] === true;
    if (isManual) setButtonLoading(els.statusBtn, true);

    try {
        const data = await apiRequest(`/pipeline/runs/${currentRunId}`, { method: 'GET' });

        // Обновляем бейдж и вывод
        if (data && data.status) {
            const lowerStatus = data.status.toLowerCase();
            updateStatusBadge(data.status);
            updateProgress(data.status, data);

            // Обновляем запись истории на актуальный статус
            const entryPatch = { status: lowerStatus };

            // Если достигнут терминальный статус — глушим поллинг и таймер
            if (TERMINAL_STATUSES.includes(lowerStatus)) {
                stopPolling();
                stopDurationTimer();

                const finishedAt = Date.now();
                entryPatch.finishedAt = finishedAt;
                entryPatch.durationMs = runStartTime ? finishedAt - runStartTime : null;

                els.statusInfoText.textContent =
                    `Запуск ${currentRunId} завершён со статусом: ${data.status}`;

                toast({
                    kind: lowerStatus === 'succeeded' ? 'success' : 'error',
                    title: lowerStatus === 'succeeded' ? 'Pipeline завершён успешно' : 'Pipeline упал',
                    message: `Длительность: ${formatDuration(entryPatch.durationMs)}`,
                });
            }

            updateHistoryEntry(currentRunId, entryPatch);
        }

        renderJSON(els.statusOutput, data);
    } catch (error) {
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
    } finally {
        if (isManual) setButtonLoading(els.statusBtn, false);
    }
}

/**
 * Запускает автополлинг статуса каждые POLL_INTERVAL_MS миллисекунд.
 */
function startPolling() {
    // Защита от двойного запуска — гарантируем единственный активный интервал
    if (pollIntervalId) return;
    if (!currentRunId) return;

    pollIntervalId = setInterval(fetchStatus, POLL_INTERVAL_MS);
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
    'reset':      { execute: false, skip_load: false, skip_features: false, skip_train: false, skip_eval: false },
};

function applyPreset(name) {
    const preset = PRESETS[name];
    if (!preset) return;
    els.execute.checked      = preset.execute;
    els.skipLoad.checked     = preset.skip_load;
    els.skipFeatures.checked = preset.skip_features;
    els.skipTrain.checked    = preset.skip_train;
    els.skipEval.checked     = preset.skip_eval;

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
        await apiRequest('/health', { method: 'GET' });
        els.liveDot.dataset.status = 'ok';
    } catch {
        els.liveDot.dataset.status = 'error';
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

// На случай закрытия вкладки — корректно останавливаем интервал
window.addEventListener('beforeunload', () => {
    stopPolling();
    stopDurationTimer();
});

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
console.log('Нажмите ? для списка горячих клавиш');
