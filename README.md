# CV System

Платформа компьютерного зрения для детекции, трекинга и подсчёта объектов в реальном времени.

## Возможности

- **Детекция объектов** — YOLO12 (n/s/m/l/x), автоматическое определение GPU (CUDA)
- **Мульти-трекинг** — отслеживание объектов между кадрами с присвоением ID
- **Подсчёт по зонам и линиям** — настраиваемые зоны (полигоны) и линии пересечения
- **Живое видео** — MJPEG-стриминг с камер в веб-интерфейсе
- **Кастомное обучение** — разметка объектов на кадрах и fine-tuning YOLO на своих данных
- **Аутентификация** — роли admin/operator, назначение потоков операторам
- **Веб-интерфейс** — дашборд, управление потоками, счётчиками, пользователями
- **Метрики** — CPU, RAM, диск, сеть (реальное время), GPU
- **Мультиязычность** — русский / английский
- **Тёмная / светлая тема**

## Архитектура

```
cv_system/
├── src/
│   ├── core/              # Детектор, трекер, счётчик
│   ├── sources/           # RTSP, камера, видеофайл
│   ├── analytics/         # Сбор статистики
│   ├── visualization/     # Отрисовка bbox, зон, линий
│   └── training_engine.py # Движок обучения YOLO
├── web/
│   ├── app.py             # FastAPI сервер
│   ├── auth.py            # JWT аутентификация
│   ├── database.py        # SQLAlchemy модели
│   ├── routers/           # API endpoints
│   ├── templates/         # Jinja2 HTML шаблоны
│   └── static/            # CSS, JS
├── datasets/              # Датасеты для обучения
├── models/                # Скачанные и обученные модели
├── configs/               # YAML конфигурации
├── install.sh             # Скрипт установки
└── requirements.txt
```

## Установка

### Требования

- Python 3.10+
- Linux (Ubuntu 22.04+ рекомендуется)
- (Опционально) NVIDIA GPU + CUDA 11.8+

### Быстрая установка

```bash
git clone https://github.com/ZaahiD-CODE/cv-system-lite.git
cd cv-system-lite
chmod +x install.sh
./install.sh
```

Скрипт создаст `.env` с автоматически сгенерированными секретами. Пароль админа будет показан один раз при установке.

### Ручная установка

```bash
# Виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Зависимости
pip install -r requirements.txt
pip install -r web/requirements.txt

# Скачивание моделей YOLO12
python3 -c "
from ultralytics import YOLO
for m in ['yolo12n.pt','yolo12s.pt','yolo12m.pt','yolo12l.pt','yolo12x.pt']:
    YOLO(m)
    print(f'{m} downloaded')
"

# Инициализация БД
python3 -c "from web.database import init_db; init_db()"
```

### С GPU (NVIDIA)

```bash
# Установить PyTorch с CUDA перед install.sh
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Проверить
python3 -c "import torch; print(torch.cuda.is_available())"
```

Система автоматически обнаружит GPU и переключит детекцию на `cuda:0`.

## Запуск

```bash
source venv/bin/activate
export $(grep -v '^#' .env | xargs)
python3 run_web.py
```

Веб-интерфейс: `http://localhost:8000`

### Переменные окружения (`.env`)

| Переменная | Описание | Default |
|-----------|----------|---------|
| `JWT_SECRET_KEY` | Секрет для JWT-токенов | генерируется при установке |
| `CV_ADMIN_PASSWORD` | Пароль админа | генерируется при установке |
| `CORS_ORIGINS` | Разрешённые origins через запятую | `http://localhost:8000` |

### Как systemd-сервис

```bash
sudo cp cv-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cv-system
```

Файл сервиса должен загружать переменные из `.env`:
```ini
[Service]
EnvironmentFile=/root/cv_system/.env
```

### С HTTPS (Let's Encrypt)

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo cp nginx-cv-system.conf /etc/nginx/sites-available/cv-system
sudo ln -s /etc/nginx/sites-available/cv-system /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
sudo systemctl restart nginx
```

## Веб-интерфейс

| Страница | Описание |
|----------|----------|
| `/dashboard` | Панель управления — статистика, популярные объекты |
| `/streams` | Потоки — создание, живое видео, зоны, линии, счётчики |
| `/counters` | Счётчики — табличный вид по потокам |
| `/users` | Пользователи — CRUD, роли, назначение потоков |
| `/training` | Обучение — разметка кастомных объектов, fine-tuning YOLO |
| `/system` | Система — метрики, логи, модели, настройки |

## API

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/auth/login` | POST | Авторизация (JWT) |
| `/api/streams/` | GET/POST | Потоки |
| `/api/streams/{id}/zones` | POST | Добавить зону |
| `/api/streams/{id}/lines` | POST | Добавить линию |
| `/api/streams/{id}/counters` | POST | Добавить счётчик |
| `/api/training/objects` | GET/POST | Кастомные объекты |
| `/api/training/objects/{id}/annotate` | POST | Добавить разметку |
| `/api/training/objects/{id}/train` | POST | Запустить обучение |
| `/api/training/classes` | GET | Список классов (YOLO + кастомные) |
| `/api/training/models` | GET | Доступные модели |
| `/api/stream/{id}/mjpeg` | GET | MJPEG-стрим |
| `/api/stats/dashboard` | GET | Статистика дашборда |
| `/api/stats/system` | GET | Информация о системе и GPU |
| `/api/system/metrics` | GET | CPU/RAM/Disk/Net метрики |
| `/api/system/logs` | GET | Логи системы |

## Модели

| Модель | Размер | Скорость | Точность |
|--------|--------|----------|----------|
| YOLO12n | ~5 MB | Очень быстро | Низкая |
| YOLO12s | ~18 MB | Быстро | Средняя |
| YOLO12m | ~39 MB | Средне | Хорошая |
| YOLO12l | ~51 MB | Медленно | Высокая |
| YOLO12x | ~114 MB | Очень медленно | Максимальная |

## Кастомное обучение

1. Создайте объект на странице **Обучение**
2. Выберите поток — появится живое видео
3. Нажмите **Пробел** для захвата кадра
4. Нарисуйте bbox на объекте
5. Нажмите **Enter** для сохранения
6. Повторите 5+ раз с разных ракурсов
7. Нажмите **Начать обучение**

Обученная модель сохранится как `yolo12n_ваш_объект.pt` и появится в списке моделей при настройке потока.

### Горячие клавиши (обучение)

| Клавиша | Действие |
|---------|----------|
| Пробел | Захватить кадр |
| Enter | Сохранить разметку |
| Escape | Сбросить кадр (вернуть live) |

## Конфигурация

`configs/default.yaml`:

```yaml
pipeline:
  source_type: "rtsp"
  source_path: "rtsp://..."
  detector:
    model: "yolo12n.pt"
    confidence: 0.5
    device: "auto"  # auto / cpu / cuda:0
    input_size: 640
  tracker:
    type: "centroid"
    max_age: 30
    min_hits: 3
  counter:
    mode: "zone"
```

## Технологии

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: Vanilla JS, Jinja2, CSS
- **ML**: Ultralytics YOLO12, PyTorch
- **Видео**: OpenCV, MJPEG streaming
- **Аутентификация**: JWT (python-jose)
- **Деплой**: Nginx, Let's Encrypt, systemd

## Лицензия

MIT
