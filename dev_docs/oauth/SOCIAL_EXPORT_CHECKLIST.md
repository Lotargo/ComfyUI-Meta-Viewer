# Чеклист: социальный экспорт (Telegram / VK / Instagram) и ИИ-студия персонажей

Статус документа: рабочий. Обновляется после каждого выполненного/проваленного пункта.

## Как пользоваться (для человека и ИИ-агентов)

1. Сначала прочитай план: `dev_docs/oauth/SOCIAL_EXPORT_PLAN.md` (цели, подходы, архитектура, порядок реализации).
2. Потом открой этот чеклист, найди первый незаполненный `- [ ]` пункт — с него продолжать работу.
3. Отмечай `- [x]` только после фактического выполнения и проверки (не «сделал», а «работает»).
4. Спорные/неожиданные решения в обход плана фиксируй в `dev_docs/oauth/SOCIAL_EXPORT_DECISIONS.md` и добавляй ссылку на запись в соответствующем пункте чеклиста.
5. Если пункт требует корректировки плана — помечай `[x]` нельзя; сначала поправь план и укажи это в комментарии к пункту.

## Текущее состояние

- Текущая позиция: **этапы 1–3 завершены; Telegram переведён в опциональный адаптер за флагом (D-012); этап 5 (VK) — auth-часть готова**.
- Продолжить с: этап 2, пункт «Практическая проверка: вход на реальном аккаунте» (ждём `api_id`/`api_hash` от пользователя; Telegram теперь опционален — проверится при `SOCIAL_TELEGRAM_ENABLED=1`).
- Последнее обновление: 2026-08-06 (флаг Telegram, см. D-012).

## Этап 1. Каркас интеграций

- [x] Определить контракт `publish` (сигнатура, модель ошибок `ok/partial/failed`) — см. план, раздел «Публикация: общий контракт»; реализовано в `app/integrations/social/contract.py` (см. D-011 про конструктор `failure`)
- [x] Добавить `telethon = "^1.44"` в `pyproject.toml`
- [x] Создать blueprint `app/integrations/social/` (`telegram.py`, `vk.py`, `instagram.py`, `routes.py`)
- [x] Резолвер секретов: keyring (`SystemSecretStore`, service `comfyui-meta-viewer`, username `social:<provider>`) — `app/integrations/social/secrets.py`

## Этап 2. Telegram: авторизация (backend) — ныне опциональный адаптер (см. D-012)

- [x] `POST /api/social/telegram/auth/start` — запуск QR или phone+code потока
- [x] Сохранение зашифрованной сессии Telethon в keyring (StringSession)
- [x] `GET /api/social/telegram/status` — «Подключено: @user» / «Не подключено»
- [x] Backend-роуты авторизации: `POST .../auth/start` (QR или phone+code), `GET .../auth/state`, `GET .../auth/qr.png`, `POST .../auth/code`, `POST .../auth/password` (2FA), `POST .../auth/cancel`, `POST .../auth/disconnect` — `app/integrations/social/routes.py`
- [x] `TelegramPublisher` auth-manager: фоновый event loop (sync→async), машина состояний idle/qr_waiting/code_requested/password_required/connected/error, `get_me`, flood-wait/ошибочные коды, автовосстановление из keyring — `app/integrations/social/telegram.py`
- [x] `social.telegram.api_id/api_hash` в `ConfigStore` (секция `social`, `social_settings()`/`update_social_settings()`) + env `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`
- [x] Флаг опциональности (D-012): `SOCIAL_TELEGRAM_ENABLED=1` (env, по умолчанию выключен); при выключенном флаге — `enabled: false` в status и `404 not_enabled` на всех telegram-эндпоинтах и `publish` — `app/integrations/social/routes.py`
- [x] Тесты `tests/test_social_telegram_auth.py` (fake-клиент + fake-store, без сети): 15 passed; + 4 теста флага в `tests/test_social_publish_contract.py`
- [ ] Практическая проверка: вход на реальном аккаунте (QR или phone+code); повторное использование сессии без повторной авторизации. **Опционально** — проверится при включённом `SOCIAL_TELEGRAM_ENABLED=1`

## Этап 3. Telegram: UI-карточка — скрыта за тумблером (D-012)

- [x] Карточка «Telegram» в настройках (секция «Social accounts» на вкладке AI, образец — карточки CLI-интеграций) — `app/templates/ai_settings.html` + `app/static/css/features/ai-settings.css`
- [x] Кнопка «Авторизоваться» (QR в модалке `<dialog id="social-telegram-dialog">` с поллингом state каждые 3s; запасной путь phone+code; шаг 2FA password) — `app/static/js/social-accounts.js`
- [x] Индикатор состояния «Подключено: @user» / «Отключено» + бейдж «not configured» (поле `configured` в `_view()` держит Authorize disabled)
- [x] Кнопка «Отключить» (disconnect) для обоих провайдеров
- [x] Карточка Telegram **скрыта по умолчанию**; тумблер «Show optional adapters (Telegram — registration-required)» (localStorage `social.showOptionalAdapters`) раскрывает её с бейджем «Optional» и disabled Authorize — live-проверено на 7860 (Playwright), гейт `404 not_enabled` подтверждён (см. D-012)
- [x] Live-проверка на 7860 (Playwright): карточки рендерятся (2 колонки grid, flex-карточки), disabled-состояния, открытие/закрытие Telegram-диалога, toast-ошибки при отсутствии кредов; скриншот `social-cards.png`

## Этап 4. Telegram: экспорт

- [ ] Кнопка экспорта в `#selection-toolbar` медиатеки (Select Mode уже есть в `library.html`)
- [ ] Модалка публикации: выбор соцсети + таргета
- [ ] Отправка контакту из списка (`client.get_dialogs()`, поиск по имени)
- [ ] Отправка в «Избранное» (Saved Messages = диалог с собой)
- [ ] Публикация в свою группу/канал (`client.send_file`, `album` для нескольких работ)
- [ ] Практическая проверка: отправка в таргеты (контакт / Избранное / группа, в т.ч. album чанками по 10); при `FloodWaitError` — сообщение «подождите N» без авто-ретраев

## Этап 5. VK: публикация в группу (community-токен, основной путь) + стена (опционально)

- [x] Определить доступный путь: старое Standalone-приложение со scope `wall` / только community-токен (см. D-010) — решение: community-токен основной, личная стена не входит в продукт по умолчанию
- [x] VK ID OAuth (auth-часть): `auth_start()` (PKCE S256, verifier/challenge/state/device_id, prompt=login), `auth_submit_code()`, callback `GET /api/social/vk/auth/callback`, токен в keyring (`social:vk`) — `app/integrations/social/vk.py`, `app/integrations/social/routes.py`; UI: карточка VK с кнопкой Authorize (`window.open` + поллинг `/api/social/vk/auth/state` каждые 2s, таймаут 5 мин)
- [x] `VK_CLIENT_ID`/`VK_CLIENT_SECRET` в ConfigStore (секция `social`) + env
- [x] Тесты `tests/test_social_vk_auth.py` (fake store + fake post-callable, без сети): 17 passed; полный `pytest tests -q` → 452 passed (1 fail — предсуществующий red-herring test_database_paths)
- [ ] Community-токен: в настройках сообщества → Работа с API → Ключи доступа (права `photos`, `video`, `wall`, `offline`); `group_id` в ConfigStore + поле в UI
- [ ] Валидация: `users.get` (user) / `groups.getById` (community)
- [ ] Шифрование токена в keyring (`social:vk`)
- [ ] Публикация фото в группу: `photos.getWallUploadServer?group_id=` → загрузка → `photos.saveWallPhoto` → `wall.post` (`owner_id=-<gid>`, `from_group=1`)
- [ ] Публикация видео в группу: `video.save` (`wall=1`, `group_id`) → upload → `wall.post`
- [ ] (Опционально, старое приложение со scope `wall`) User-токен: auth-поток `oauth.vk.com/authorize?...&redirect_uri=https://oauth.vk.com/blank.html&response_type=token`; перехват токена из `blank.html#access_token=...` (fallback — copy-paste как основной путь, D-009); публикация на личную стену
- [ ] Практическая проверка: работает ли community-токен на группу (ожидаемо — да, официальный путь) — runtime-верификация: `groups.getById` (токен валиден и права на группу есть) → тестовый `wall.post` в группу (`owner_id=-<gid>`, `from_group=1`) с последующим удалением; есть ли у пользователя приложение со scope `wall`; лимиты (`wall.post` до 10 вложений, пост обязан содержать текст/медиа; `video.save` 5000/день)

## Этап 6. Instagram: Private API

- [ ] Добавить `instagrapi` в `pyproject.toml` (2.18.12)
- [ ] Авторизация: логин + пароль (+ 2FA TOTP / code challenge при необходимости)
- [ ] Сессия `dump_settings()` → шифрование в keyring (`social:instagram`)
- [ ] `photo_upload` / `video_upload` / `album_upload` (карусель 2–10 шт., фото+видео можно миксовать)
- [ ] Практическая проверка: стабильность сессии при переиспользовании без повторных логинов (`load_settings()` перед `login()`, полный логин — не sessionid-only); пре-резize фото до 1080 (4:5…1.91:1, q=92, >8MB — ошибка); соблюдение лимитов и единого профиля клиента (риск блокировки низкий — «не обходим лимиты», см. D-001)

## Этап 7. Персоны, альбомы, история

- [ ] Таблицы `personas` / `persona_assets` / `publications`
- [ ] Страница `personas.html`: CRUD, сетка изображений, история генераций, история публикаций
- [ ] Авто-альбом «Персона: <имя>» (виртуальный, по модели 03_MEDIA_LIBRARY_ALBUMS_AND_FAVORITES)
- [ ] Фильтр по персонам в библиотеке

## Этап 8. AI-постмейкер

- [ ] Операция `social_post` в реестре операций: `app/ai/prompting/content/operations/social_post.md`
- [ ] Manifest: output contract по соцсети (Instagram — caption+хештеги; Telegram — без хештегов; VK — пост+опциональные хештеги); жёсткий запрет выдумок
- [ ] `POST /api/ai/social-post` (по образцу `/api/ai/enhance`)
- [ ] Vision: прямая картинка (мультимодальные профили) / `SceneSpec` из `reconstruct` (остальные)
- [ ] Хештеги — политика «персона + контент», до N, редактируемо
- [ ] Кнопка «Сочинить текст ИИ» в модалке публикации (выбор персоны/легенды)
- [ ] Результат — черновик в `ai_jobs` / `ai_prompt_drafts`, обязательное редактирование перед публикацией
- [ ] Практическая проверка (критерии приёмки): стабильность образа (5 генераций с одним `appearance`); снижение галлюцинаций (пост с ролью vs без на одном SceneSpec); попадание в стиль персонажа

## Этап 9. Линковка в редакторе

- [ ] Поле «Персона» в `workflow_editor.html` при генерации
- [ ] Авто-линковка сгенерированных работ к персоне (`persona_assets`)
