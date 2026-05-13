/* ======================================================
   Distributed Churn Prediction — Dashboard JS
   Vanilla JavaScript, без зависимостей.
   Работает с FastAPI бэкендом на http://127.0.0.1:8000
   ====================================================== */

// ====================== КОНФИГУРАЦИЯ ======================

// Базовый URL бэкенда. Меняется в одном месте, если адрес поменяется.
const API_BASE_URL = 'http://127.0.0.1:8000';

// Интервал автополлинга статуса (миллисекунды)
const POLL_INTERVAL_MS = 3000;

// Статусы, при достижении которых поллинг останавливается
const TERMINAL_STATUSES = ['succeeded', 'failed'];


// ====================== ГЛОБАЛЬНОЕ СОСТОЯНИЕ ======================

// Текущий run_id запущенного пайплайна. null, если ничего не запускалось.
let currentRunId = null;

// Идентификатор активного setInterval для поллинга. null, если поллинг не активен.
let pollIntervalId = null;


// ====================== ССЫЛКИ НА DOM-ЭЛЕМЕНТЫ ======================

// Получаем все нужные элементы один раз при загрузке скрипта.
const els = {
    // Health Check
    healthBtn:      document.getElementById('healthBtn'),
    healthOutput:   document.getElementById('healthOutput'),
    healthDot:      document.getElementById('healthDot'),

    // Run Pipeline
    runBtn:         document.getElementById('runBtn'),
    runOutput:      document.getElementById('runOutput'),
    runIdDisplay:   document.getElementById('runIdDisplay'),
    runIdValue:     document.getElementById('runIdValue'),

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
    autoPoll:       document.getElementById('autoPoll'),
};


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
        renderJSON(els.healthOutput, data);
    } catch (error) {
        els.healthDot.dataset.status = 'error';

        // Если сервер недоступен — fetch бросает TypeError
        const errorPayload = error.body || {
            error: error.message,
            hint: 'Проверьте, что FastAPI сервер запущен на ' + API_BASE_URL,
        };
        renderJSON(els.healthOutput, errorPayload, true);
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
            els.statusInfo.textContent = `Отслеживается запуск: ${currentRunId}`;

            // Сбрасываем бейдж статуса в стартовое состояние
            updateStatusBadge('queued');

            // Сразу делаем первый запрос статуса и (если включено) запускаем поллинг
            await fetchStatus();
            if (els.autoPoll.checked) {
                startPolling();
            }
        }

        renderJSON(els.runOutput, data);
    } catch (error) {
        const errorPayload = error.body || {
            error: error.message,
            hint: 'Не удалось запустить пайплайн. Проверьте доступность ' + API_BASE_URL,
        };
        renderJSON(els.runOutput, errorPayload, true);
    } finally {
        setButtonLoading(els.runBtn, false);
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
            updateStatusBadge(data.status);

            // Если достигнут терминальный статус — глушим автополлинг
            if (TERMINAL_STATUSES.includes(data.status.toLowerCase())) {
                stopPolling();
                els.statusInfo.textContent =
                    `Запуск ${currentRunId} завершён со статусом: ${data.status}`;
            }
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
        }
    } else {
        stopPolling();
    }
}


// ====================== ИНИЦИАЛИЗАЦИЯ ======================

// Вешаем обработчики событий после загрузки скрипта.
els.healthBtn.addEventListener('click', checkHealth);
els.runBtn.addEventListener('click', runPipeline);
// Передаём true, чтобы fetchStatus знал, что это ручной вызов и показал спиннер
els.statusBtn.addEventListener('click', () => fetchStatus(true));
els.autoPoll.addEventListener('change', handleAutoPollToggle);

// На случай закрытия вкладки — корректно останавливаем интервал
window.addEventListener('beforeunload', stopPolling);

// Сообщаем пользователю в консоль, что фронт готов к работе
console.log('%c[Distributed Churn Prediction] Dashboard initialized', 'color: #4f46e5; font-weight: bold');
console.log('API base URL:', API_BASE_URL);
