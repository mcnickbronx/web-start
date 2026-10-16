# Официальный python:3.14-slim с зеркала AWS: у Docker Hub лимит скачиваний без входа, CI в него упирается
FROM public.ecr.aws/docker/library/python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/www

# Зависимости — отдельным слоем: меняются редко, и сборка с новым кодом идёт за секунды
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Папки данных — пользователя 1000: новый том Docker берёт владельца из образа
RUN mkdir -p /usr/www/media /usr/www/private /usr/www/static \
    && chown 1000:1000 /usr/www/media /usr/www/private /usr/www/static

# cron для контейнеров — сервис cron в compose.yml, расписание в project/crontab. Файл сверяется
# по sha256: подменённый на GitHub не соберётся. Новая версия — github.com/aptible/supercronic/releases:
# номер в адресе и sha256 файла supercronic-linux-amd64 (образ собирает CI, он amd64)
ADD --checksum=sha256:a53ae236602c7338aba3fbaff40bda6300eae3b9fedb8261eb06cfe3724430c1 --chmod=755 \
    https://github.com/aptible/supercronic/releases/download/v0.2.49/supercronic-linux-amd64 /usr/local/bin/supercronic

# Код — в образе. Образ собирает CI на каждый push в dev и main, сервер выкладывает тот, что
# в его .env (автовыкладка, docs/deploy.md). Файлы принадлежат root: приложение (пользователь 1000)
# поменять свой код не может
COPY app /usr/www/app
# compose проекта — тоже в образе: автовыкладка берёт его отсюда, руками его на сервер не кладут
COPY compose.yml /deploy/compose.yml

WORKDIR /usr/www/app
# Не root, даже если запускают без compose (docker run, панель): тот же пользователь, что user: в compose
USER 1000:1000
ENV HOME=/tmp
