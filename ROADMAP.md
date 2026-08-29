# ComfyUI Meta Viewer — Project Roadmap

Этот документ отражает стратегический план развития проекта **ComfyUI Meta Viewer (CMV)**. Подробные архитектурные спецификации и технические задания по каждому этапу находятся в директории [`dev_docs/roadmap/`](dev_docs/roadmap/README.md).

---

## Текущий статус и этапы разработки

| # | Этап / Документ | Статус | Описание |
| :---: | :--- | :---: | :--- |
| **00** | [Cross-platform foundation](dev_docs/roadmap/core/00_CROSS_PLATFORM_FOUNDATION.md) | `In Progress` | Поддержка Windows, Linux, macOS, нативные диалоги и Unicode-пути |
| **01** | [Database and index reset](dev_docs/roadmap/core/01_DATABASE_AND_INDEX_RESET.md) | `Completed` | Сброс индекса и настроек без затрагивания исходных медиафайлов |
| **02** | [Source monitoring & cloud directories](dev_docs/roadmap/core/02_SOURCE_MONITORING_AND_CLOUD_DIRECTORIES.md) | `In Progress` | Наблюдение за папками (watcher + reconcile) и облачными дисками |
| **03** | [Simple Mode & model calibration](dev_docs/roadmap/simple/03_SIMPLE_MODE_MODEL_CALIBRATION.md) | `Active Focus` | Фокусный режим генератора промптов и калибровка 8 базовых моделей |
| **04** | [Advanced Mode & embedded ComfyUI](dev_docs/roadmap/advanced/04_ADVANCED_MODE_AND_COMFYUI_INTEGRATION.md) | `Planned` | Пайплайны Txt2Img, Img2Img, Inpaint, Upscale, IP-Adapter и встроенный UI ComfyUI |
| **05** | [Character & Environment Studio](dev_docs/roadmap/advanced/05_CHARACTER_AND_ENVIRONMENT_STUDIO.md) | `Planned` | Студия персонажей/локаций, FaceID/IP-Adapter, Vision-паспорта и фильтры |
| **06** | [Social OAuth & Export](dev_docs/roadmap/oauth/06_SOCIAL_EXPORT_PLAN.md) | `Draft` | Экспорт в Telegram, VK, Instagram, локальный OAuth и AI-постмейкер |
| **07** | [Desktop packaging and installers](dev_docs/roadmap/desktop/07_DESKTOP_PACKAGING_AND_INSTALLERS.md) | `Deferred` | Финальная упаковка в нативные desktop-инсталляторы (после всего функционала) |

---

## Ближайший фокус разработки

1. **Simple Mode (Редактор и Базовый Генератор):**
   - Полировка основного интерфейса редактора;
   - Завершение калибровки моделей (Flux, SDXL, Pony и др.) и пресетов (`Быстро`, `Стандартно`, `Детально`);
   - Стабильный вывод валидных контрактов `PromptResult` и `SceneSpec`.

2. **Переход к Advanced Mode и Студиям:**
   - Интеграция расширенных режимов (Inpaint, Img2Img, Upscale Detailer, IP-Adapter);
   - Встраивание оригинального веб-интерфейса ComfyUI прямо внутрь приложения;
   - Студия персонажей и окружения для консистентных многосерийных генераций.

3. **Экспорт в Соцсети (Social OAuth):**
   - Авторизация в личных аккаунтах (Telegram, VK, Instagram) и ручная публикация постов.

4. **Desktop Packaging:**
   - Подготовка автономных инсталляторов под Windows, Linux и macOS в самом финале.
