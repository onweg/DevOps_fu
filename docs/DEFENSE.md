# University Defense Preparation Guide

Complete preparation for the UBI.215 project defense, including demo script, expected questions, and weak-point mitigation.

**Student:** Фролкин А.Д., группа ИД23-3  
**Topic:** Тема 6 — Разработка контейнера для обеспечения безопасности системы при угрозе несанкционированного доступа при помощи сторонних сервисов (215)

---

## Defense Readiness Checklist

### Technical readiness
- [ ] `docker compose up --build` succeeds from a clean checkout
- [ ] Full workflow (generate → train → analyze) completes without errors
- [ ] Dashboard shows populated charts (threat distribution + model accuracy)
- [ ] Kubernetes deployment works: `kubectl get pods -n access-security` shows `4/4 Running`
- [ ] All API endpoints respond correctly (verify with curl commands below)
- [ ] pgAdmin accessible and shows all 6 tables

### Presentation readiness
- [ ] Laptop has Docker Desktop running with enough RAM (4 GB free)
- [ ] Fallback screenshots prepared (in case live demo fails)
- [ ] Know the answers to the 10 questions below
- [ ] Can explain EVERY file in the project
- [ ] Understand the data flow end-to-end

### Screenshots to prepare
1. Docker Dashboard showing all 4 containers healthy
2. `docker compose ps` output in terminal
3. Dashboard at `/` with populated charts
4. Recent Detections table with token_theft and oauth_hijack entries
5. Activity Log showing generate → train → analyze sequence
6. pgAdmin showing all 6 tables with row counts
7. `kubectl get all -n access-security` terminal output
8. `/api/status` JSON response
9. `/api/analysis/metrics` JSON response with model accuracy scores

---

## Demo Scenario

### Narrative (tell this story)

*"Данная система решает реальную задачу безопасности: защиту API от несанкционированного доступа через сторонние сервисы. Злоумышленники могут использовать украденные токены, атаки перебора, перехват OAuth-потоков и другие техники. Традиционные межсетевые экраны не различают легитимного пользователя и атаку, если запрос технически корректен.*

*Наше решение использует машинное обучение для классификации сессий по 22 признакам поведения на шесть категорий. Система полностью контейнеризирована — четыре сервиса под управлением Docker Compose для разработки и Kubernetes для продуктивной среды."*

---

## Demo Command Sequence

### Step 0 — Show the system is up

```bash
docker compose ps
```
> "Все четыре контейнера запущены и здоровы: API, ML-сервис, PostgreSQL и pgAdmin."

```bash
curl -s http://localhost:5050/api/status | python3 -m json.tool
```
> "Эндпоинт /api/status подтверждает, что все три внутренних сервиса доступны."

### Step 1 — Generate the dataset

```bash
curl -s -X POST http://localhost:5050/api/data/generate \
  -H "Content-Type: application/json" \
  -d '{"count": 5000}' | python3 -m json.tool
```
> "Мы сгенерировали 5000 синтетических записей о доступе к API. Каждая запись — это сессия с 22 признаками: частота запросов, количество ошибок аутентификации, возраст токена, аномалии геолокации и др. Генератор создаёт реалистичные распределения для каждого типа атаки."

### Step 2 — Train the models

```bash
curl -s -X POST http://localhost:5050/api/analysis/train | python3 -m json.tool
```
> "Мы обучили три классификатора: Gradient Boosting, многослойный перцептрон (MLP) и K-Means. Данные разделены 80/20 со стратификацией, признаки нормализованы StandardScaler. Метрики сохранены в PostgreSQL."

### Step 3 — Classify threats

```bash
curl -s -X POST http://localhost:5050/api/analysis/analyze | python3 -m json.tool
```
> "Предиктор применил все три модели к каждому событию через голосование большинством. Высококонфидентные не-нормальные детекции автоматически создали алерты с уровнями критичности."

### Step 4 — Show the dashboard

*Open http://localhost:5050 in browser*

> "Дашборд показывает статистику в реальном времени. Горизонтальная гистограмма отображает распределение угроз по классам. Кольцевая диаграмма сравнивает точность трёх алгоритмов. Таблица детекций показывает предсказания каждой модели с оценкой уверенности и флагом согласия моделей."

### Step 5 — Show the API

```bash
curl -s "http://localhost:5050/api/analysis/threats?threat_type=token_theft&min_confidence=0.9&limit=3" \
  | python3 -m json.tool
```
> "REST API полностью доступен для запросов. Здесь мы фильтруем кражи токенов с уверенностью выше 90%. Каждая детекция показывает предсказание каждой из трёх моделей и ансамблевый результат."

### Step 6 — Show Kubernetes

```bash
kubectl get all -n access-security
kubectl describe pod -n access-security | grep -A5 "Readiness"
```
> "Kubernetes-деплоймент использует один под с четырьмя контейнерами, разделяющими сетевое пространство имён. ConfigMap хранит конфигурацию, Secret — учётные данные в base64. Readiness-пробы гарантируют, что PostgreSQL принимает соединения до старта ML-сервиса, а ML-сервис проходит health-check до старта API."

---

## Expected Professor Questions

### Q1: Почему именно три алгоритма и почему такой выбор?

**Сильный ответ:** "Три алгоритма выбраны из разных семейств ML для максимальной диверсификации подхода. Gradient Boosting — ансамбль деревьев с последовательным исправлением ошибок; он лучше всего работает на табличных данных со смешанными признаками и является основным тай-брейкером. MLP — нейронная сеть с тремя скрытыми слоями (128-64-32), которая обучает нелинейные взаимодействия между признаками автоматически — например, комбинация ip_change_count и geolocation_anomaly вместе указывает на кражу токена сильнее, чем каждый признак по отдельности. K-Means — это метод неконтролируемой кластеризации, адаптированный для классификации путём маркировки каждого кластера доминирующим классом из обучающих данных. Такой подход подтверждает, что классы атак геометрически разделимы в пространстве признаков."

---

### Q2: Почему точность близка к 100%? Это не подозрительно?

**Сильный ответ:** "Высокая точность ожидаема и намеренна на этом датасете. Данные синтетические — признаки для каждого класса атак специально спроектированы с разделимыми распределениями. Например, брутфорс всегда имеет failed_auth_count > 150 и response_error_rate > 0.90, а нормальный трафик никогда не имеет таких значений. Это чёткие математические границы, а не зашумлённые реальные данные. В продуктивной среде, с реальными логами API, точность была бы ниже из-за шума, дрейфа данных и неизвестных паттернов атак. Это признанное ограничение проекта."

---

### Q3: Почему синтетические данные, а не реальные логи?

**Сильный ответ:** "Реальные логи API требуют доступа к продуктивным системам, создают проблемы конфиденциальности (152-ФЗ о персональных данных), и не имеют размеченных меток — вы не знаете заранее, была ли та или иная сессия атакой. Синтетические данные с инженерными распределениями — стандартная практика для первоначальной валидации ML-пайплайна. Признаки основаны на реальных индикаторах атак из документации OWASP, RFC 6749 (OAuth) и руководств ФСТЭК."

---

### Q4: Что такое Docker Compose и зачем он нужен?

**Сильный ответ:** "Docker Compose — декларативный инструмент для запуска многоконтейнерных приложений. Файл `docker-compose.yml` описывает все четыре сервиса, их переменные окружения, volumes, сеть, healthcheck'и и порядок запуска. Ключевое DevOps-преимущество — воспроизводимость среды: команда `docker compose up --build` на любой машине с Docker поднимает идентичную конфигурацию. Это устраняет проблему 'у меня работает, у тебя нет'."

---

### Q5: В чём разница между Docker Compose и Kubernetes в вашем проекте?

**Сильный ответ:** "Docker Compose — наша среда разработки: простой запуск одной командой, прямой проброс портов, конфигурация из `.env` файла. Kubernetes — продакшн-деплоймент: добавляет ConfigMap для разделения конфигурации и кода, Secret для управления учётными данными (base64), PersistentVolumeClaims для хранилища, readiness-пробы для health-гейтинга. Наш K8s-деплоймент использует Minikube для локального кластера. Однопод-архитектура означает, что все четыре контейнера разделяют localhost, что зеркалит сетевую модель Docker Compose, сохраняя при этом практику написания манифестов K8s."

---

### Q6: Что делает StandardScaler и зачем он нужен?

**Сильный ответ:** "StandardScaler нормализует каждый признак до нулевого среднего и единичной дисперсии. Это критично для MLP: без нормализации `data_volume_mb` (до 1000 МБ) полностью доминировал бы над `ssl_valid` (0 или 1) при вычислении градиентов, делая обучение нестабильным. Критически важно: скейлер обучается **только на тренировочных данных**, затем применяется к тестовым — это предотвращает утечку данных (data leakage), которая привела бы к завышенным оценкам точности."

---

### Q7: Как работает K-Means в качестве классификатора?

**Сильный ответ:** "K-Means — алгоритм неконтролируемой кластеризации. Мы адаптируем его для классификации следующим образом: после кластеризации обучающих данных на 6 кластеров мы смотрим, какой класс атаки доминирует в каждом кластере (через `np.bincount(...).argmax()`), и сохраняем маппинг cluster_id → label_id в файле `kmeans_cluster_map.pkl`. При инференсе: `km_label = cluster_map[kmeans.predict(X_scaled)]`. Это подтверждает, что атаки образуют устойчивые геометрические кластеры в 22-мерном пространстве признаков."

---

### Q8: Как работает ансамблевое голосование?

**Сильный ответ:** "После того как все три модели делают предсказания, мы берём голосование большинством: если хотя бы две модели согласны — этот класс побеждает. Если все три расходятся (возможно при 6 классах) — побеждает Gradient Boosting как тай-брейкер, поскольку он эмпирически показывает наивысшую точность. Оценка уверенности — среднее значение predict_proba от GB и MLP для победившего класса, что даёт калиброванную меру."

---

### Q9: Что делает `init.sql` и как он применяется?

**Сильный ответ:** "Это авторитетное определение схемы базы данных. Образ Docker postgres:16 автоматически выполняет все `.sql` файлы из директории `/docker-entrypoint-initdb.d/` при первом старте. Наш `init.sql` создаёт шесть таблиц с нужными типами колонок и внешними ключами, индексы для производительности, и начальные данные: 5 доверенных сервисов (Google OAuth, GitHub OAuth, Stripe, SendGrid, Twilio). Защитники `IF NOT EXISTS` делают скрипт идемпотентным."

---

### Q10: Как бы вы масштабировали систему для реального продакшна?

**Сильный ответ:** "Потребовалось бы несколько изменений. Первое — разнести четыре контейнера в отдельные поды, чтобы каждый масштабировался независимо: ML-сервис — узкое место по CPU, его имеет смысл масштабировать горизонтально. Второе — добавить очередь сообщений (Redis или Kafka) между API и ML-сервисом для асинхронной обработки. Третье — добавить реальный сборщик логов из API-шлюза вместо синтетики. Четвёртое — добавить аутентификацию (JWT), rate limiting и TLS. Всё это признаётся ограничениями текущей версии в документации."

---

## Weak Points — Acknowledge Professionally

| Weakness | Professional response |
|---|---|
| Synthetic data | "Признанное ограничение. Признаки основаны на реальных индикаторах из OWASP и RFC 6749. В продуктивной среде нужен сборщик реальных логов." |
| No authentication | "Проект рассчитан на контролируемую лабораторную среду. В продакшне — JWT или mTLS." |
| Single-pod Kubernetes | "Намеренное упрощение для демонстрации. Документированное ограничение; продакшн требует отдельных подов." |
| ~100% accuracy | "Ожидаемо на инженерных синтетических данных. Подтверждает корректность пайплайна; реальные данные дадут ниже." |
| No CI/CD | "Вне scope текущего проекта; GitHub Actions пайплайн — запланированное улучшение." |

---

## Backup Plan (if live demo fails)

1. Show the prepared screenshots
2. Walk through the code structure file by file
3. Explain the ML pipeline from `generator.py` → `trainer.py` → `predictor.py`
4. Show `docker-compose.yml` and `k8s/config.yaml` explaining each section

Always have these commands ready as fallback (no Docker needed):
```bash
# Show architecture
cat docker-compose.yml
cat k8s/config.yaml

# Show ML code
cat ml-service/trainer.py
cat ml-service/predictor.py
```
