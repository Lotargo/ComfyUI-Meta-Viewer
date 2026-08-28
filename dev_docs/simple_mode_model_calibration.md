# Simple Mode - калибровка восьми базовых моделей

## Назначение

Этот документ фиксирует стартовые параметры для восьми заранее выбранных моделей Create. Это не универсальная таблица `steps = quality`: каждый model pack хранит собственный workflow и три независимых пресета `fast / standard / detailed`.

Параметры ниже собраны из model cards, авторских рекомендаций и зеркал исходных карточек. Они являются стартовой точкой. Финальные значения подтверждаем локальными A/B тестами на одинаковом наборе сцен.

В Simple Mode пользователь не видит sampler, scheduler, CFG и число шагов. UI показывает только `Быстро`, `Стандартно`, `Детально`.

---

## Model 1 - Realistic Vision V6.0 B1

Источник: `https://civitai.com/models/4201/realistic-vision-v60-b1?modelVersionId=245598`

- Base: SD 1.5.
- Закреплённая версия: `245598`.
- Выбранный файл: `Realistic_Vision_V6.0_NV_B1_fp16.safetensors`.
- Автор рекомендует повышенные относительно классического SD1.5 разрешения: 896x896, 768x1024, 640x1152, 1024x768, 1152x640.
- Подходящие sampler'ы: DPM++ SDE Karras / DPM++ 2M SDE, также Euler A.
- Рабочий CFG широкий; для Simple Mode держим умеренные значения около 4.5-5.0.

Стартовые presets:

| Preset | Steps | CFG | Sampler | Scheduler |
|---|---:|---:|---|---|
| fast | 25 | 4.5 | dpmpp_sde | karras |
| standard | 32 | 5.0 | dpmpp_sde | karras |
| detailed | 50 | 5.0 | dpmpp_2m_sde | karras |

---

## Model 2 - Juggernaut XL Ragnarok

Источник: `https://civitai.com/models/133005/juggernaut-xl?modelVersionId=1759168`

- Base: SDXL 1.0.
- Закреплённая версия: `1759168` (Ragnarok).
- Рекомендуемый sampler: DPM++ 2M SDE.
- Авторский диапазон: 30-40 steps, CFG 3-6.
- Чем ниже CFG внутри диапазона, тем реалистичнее результат.
- VAE встроен; отдельный VAE не добавляем.

Presets: 30/35/40 steps, CFG 3.5/4.0/4.5, DPM++ 2M SDE Karras.

---

## Model 3 - CyberRealistic Pony v18.0 CoreShift

Источник: `https://civitai.com/models/443821/cyberrealistic-pony?modelVersionId=2884631`

- Base: Pony SDXL.
- Закреплённая версия: `2884631`.
- Файл: `CyberRealisticPony_V18.0_F16.safetensors`.
- Авторские рекомендации: DPM++ SDE Karras / DPM++ 2M Karras / Euler A, 30+ steps, CFG 5, Clip Skip 2.
- Для Pony сохраняем score-теги как технический prompt prefix, а не как пользовательскую терминологию.

Presets: fast 25 Euler A, standard 30 DPM++ 2M Karras, detailed 36 DPM++ SDE Karras; CFG 5.

---

## Model 4 - Moody Krea 2 Mix V7 FP8

Источники: модель `2731187`, версия `3209007`; FP8-файл `Moody-Krea-Mix-v7_00002__clean_fp8.safetensors`.

- Архитектура: Krea 2, не SDXL checkpoint.
- В рекомендациях автора для текущей линии: Euler A + BETA, 8 steps; до 12 steps для дополнительной детализации.
- Поэтому не используем старую логику увеличения steps до десятков.
- Нужны отдельные Qwen text encoder и Qwen Image VAE.

Presets: 8 / 10 / 12 steps, CFG 1.0, Euler A, beta.

`workflow_ready=false` до добавления и локальной проверки настоящего Krea 2 graph. Не подменять его фальшивым FLUX/SDXL workflow.

---

## Model 5 - WAI-ANIMA v1.0

Источник: `https://civitai.com/models/2544636/wai-anima?modelVersionId=2983680`

- Base: Anima.
- Файл: `WAI-ANIMA1.safetensors`.
- Обязательные компоненты: `qwen_3_06b_base.safetensors` и `qwen_image_vae.safetensors`.
- Рекомендации: 20-30 steps, CFG 4-5, Euler A Normal; для base также допускается ER SDE BETA.
- Примеры автора используют 1024x1344.

Presets: 20/25/30 steps, CFG 4/4.5/5, Euler A Normal.

`workflow_ready=false` до подготовки Anima-specific graph.

---

## Model 6 - GonzaLomo Chroma v3.0 FP8

Источник: `https://civitai.com/models/2182526/gonzalomo-chroma?modelVersionId=2627397`

- Base: Chroma.
- Файл: `gonzalomoChroma_v30_UNET_FP8.safetensors`.
- Рекомендации: 8-14 steps, sampler Euler или DPM++ 2M, scheduler simple или beta, CFG 1.0-1.3.
- Для нашего простого flow предусмотрены FLAN-T5 XXL encoder и AE VAE.

Presets:
- fast: Euler / simple / 8 / CFG 1.0;
- standard: DPM++ 2M / beta / 10 / CFG 1.1;
- detailed: DPM++ 2M / beta / 14 / CFG 1.3.

`workflow_ready=false` до подготовки Chroma-specific graph.

---

## Model 7 - Animagine XL 3.1

Источник: `https://huggingface.co/cagliostrolab/animagine-xl-3.1`, Civitai version `403131`.

- Base: SDXL.
- Официальная рекомендация: CFG 5-7, меньше 30 steps, Euler Ancestral.
- Официальная таблица поддерживает 1024x1024, 1152x896, 896x1152, 1344x768, 768x1344 и другие SDXL-разрешения.
- Мы не инжектим пользовательски нежелательную лексику из старых quality-tag prompt examples. Качество задаётся параметрами и AI-adaptation, а не названием продукта.

Presets: 20/24/28 steps, CFG 5/6/6.5, Euler A Normal.

---

## Model 8 - LunarCherryMix Illustrious v2.4

Источник: `https://civitai.com/models/1412760?modelVersionId=2590517`.

- Base: Illustrious XL 2.0.
- Закреплённая версия: v2.4, `2590517`.
- Файл: `lunarcherrymix_v24.safetensors`.
- Рекомендации автора: 30-40 steps, CFG примерно 3.5-7, Euler A или DPM++ 2M, Clip Skip 2.
- Наиболее рекомендуемое портретное разрешение в model card: 832x1216; также поддерживаются стандартные SDXL ratios.

Presets: 30 Euler A CFG4; 35 DPM++2M CFG5; 40 DPM++2M CFG6. Clip Skip 2 зафиксирован в workflow.

---

## Правила дальнейшей калибровки

1. Не переносить значения между моделями только потому, что preset называется одинаково.
2. Каждый preset может менять любые bindings конкретного workflow, не только steps.
3. Сначала тестировать базовый t2i без LoRA, upscale и refiner. Эти слои добавляются отдельным этапом.
4. Для каждой модели прогонять одинаковый набор сцен: портрет, full-body, интерьер, пейзаж, несколько объектов, сложный свет, текст/надписи там, где архитектура их поддерживает.
5. Отдельно фиксировать скорость, VRAM peak, стабильность анатомии, prompt adherence и визуальную деградацию при повышении/понижении preset.
6. После локальной проверки правится только JSON конкретного model pack; Python compiler не должен получать model-specific `if`-ветки.
