# Development Roadmap

Эта директория содержит архитектурные технические задания, спецификации этапов и карту развития ComfyUI Meta Viewer.

---

## Навигация по дорожной карте

### 1. Core (Фундамент платформы)

- [ ] **[00. Cross-platform foundation](core/00_CROSS_PLATFORM_FOUNDATION.md)**  
  Кроссплатформенная поддержка (Windows, Linux, macOS), Unicode-пути, нативный диалог выбора директорий и платформозависимые действия.

- [x] **[01. Database and index reset](core/01_DATABASE_AND_INDEX_RESET.md)**  
  Механизмы сброса индекса (Reset Index) и полного сброса настроек (Factory Reset) с сохранением пользовательских исходных медиафайлов.

- [ ] **[02. Source monitoring and cloud directories](core/02_SOURCE_MONITORING_AND_CLOUD_DIRECTORIES.md)**  
  Наблюдение за файловыми изменениями (watcher + periodic reconcile), обработка облачных папок (Яндекс.Диск, Google Drive, OneDrive) и устойчивость к отключению дисков.

---

### 2. Simple Mode (Текущий этап)

- [ ] **[03. Simple Mode - калибровка базовых моделей](simple/03_SIMPLE_MODE_MODEL_CALIBRATION.md)**  
  Стартовые параметры, калибровка пресетов (`Быстро`, `Стандартно`, `Детально`), связки семплеров и шедулеров для восьми базовых моделей (Flux, SDXL, Pony, Anima, Krea 2, Chroma, Animagine, Illustrious).

---

### 3. Advanced Mode & Studios (Следующий этап)

- [ ] **[04. Advanced Mode and Embedded ComfyUI Integration](advanced/04_ADVANCED_MODE_AND_COMFYUI_INTEGRATION.md)**  
  Расширенные генеративные сценарии (Txt2Img, Img2Img / Style Transfer, Inpaint / Outpaint, Hi-Res Fix / Face Detailer, IP-Adapter), встроенный Webview/Iframe веб-редактора ComfyUI и интерактивная доводка/экспорт Workflow JSON.

- [ ] **[05. Character and Environment Studio](advanced/05_CHARACTER_AND_ENVIRONMENT_STUDIO.md)**  
  Студия сущностей для консистентных генераций: текстовые паспорта внешности и локаций, авто-декомпозиция через Vision LLM, слоты референсов FaceID/IP-Adapter, мульти-ракурсные карты окружений, композитор сцен, сквозная привязка метаданных (`character_id`, `environment_id`) и фильтрация в галерее.

---

### 4. Social & OAuth (Экспорт и соцсети)

- [ ] **[06. Соцсети (Telegram / ВКонтакте / Instagram) и экспорт](oauth/06_SOCIAL_EXPORT_PLAN.md)**  
  Авторизация (личные аккаунты Telegram MTProto, VK Implicit Flow, Instagram Private API), ручная публикация медиа-ассетов по кнопке, AI-постмейкер на основе легенды персонажа и связка с историей публикаций. Дополнительно: [Чеклист реализации](oauth/SOCIAL_EXPORT_CHECKLIST.md) и [Реестр решений](oauth/SOCIAL_EXPORT_DECISIONS.md).

---

### 5. Desktop (Финальная дистрибуция)

- [ ] **[07. Desktop packaging and installers](desktop/07_DESKTOP_PACKAGING_AND_INSTALLERS.md)**  
  Автономная сборка приложения с установщиками для Windows, Linux и macOS, запуск локального backend, управление процессом ComfyUI и безопасное хранение секретов (выполняется после завершения функциональных этапов).

---

## Общие принципы разработки

1. **Локальность и приватность:** Приложение работает полностью локально и является однопользовательским.
2. **Последовательность этапов:** Сначала полностью доводится и полируется **Simple Mode**, затем реализуются расширенные пайплайны **Advanced Mode**, студия сущностей и интеграции с соцсетями, и лишь в самом конце создаются desktop-установщики.
3. **Сохранность файлов:** Исходные изображения и видео пользователя никогда не перемещаются и не изменяются ради виртуальной организации.
4. **Устойчивость метаданных:** Метаданные генераций, паспорта персонажей и воркфлоу сохраняются независимо от пересоздания кэша эскизов.
