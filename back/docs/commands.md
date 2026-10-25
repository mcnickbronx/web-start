# Полезные команды
Шпаргалка · 25.10.2026

Команды по темам. Подробности про деплой — в [deploy.md](deploy.md), про устройство
проекта — в [architecture.md](architecture.md).

## Начать работу

Первая установка описана в [readme.md](../readme.md): окружение, зависимости, настройки,
база, суперпользователь. Дублировать её здесь не будем — разъедется. Ниже то, что нужно
потом, в каждой новой сессии работы.

```bash
. .venv/bin/activate                # в каждом новом окне терминала
deactivate                          # выйти из окружения

cd app                              # команды manage.py — отсюда
python manage.py runserver          # админка и API на 127.0.0.1:8000
python manage.py runserver 8001     # другой порт
```

Админка — http://127.0.0.1:8000/admin/, Swagger — http://127.0.0.1:8000/api/docs. `runserver` здесь
свой: стандартный поднял бы только админку, без API ([почему](../readme.md#структура)).

Имя папки `.venv` менять нельзя: именно оно указано в `.gitignore`. Если в системе
несколько версий Python, окружение создаётся нужной явно: `python3.14 -m venv .venv`.

## Схема базы

```bash
python manage.py makemigrations              # создать миграцию по изменённым моделям
python manage.py migrate                     # накатить
python manage.py sync_async_models           # обновить модели для API
python manage.py sync_async_models --check   # проверить, что они не отстали (это же делает деплой)

python manage.py showmigrations              # что накатано, что нет
python manage.py sqlmigrate <модуль> <номер> # посмотреть SQL миграции, ничего не выполняя
python manage.py migrate <модуль> <номер>    # откатиться к указанной миграции
```

После изменения моделей всегда две команды подряд: `makemigrations`, затем
`sync_async_models`. В коммит идут оба файла — и миграция, и `models_async.py`.

## Типы API для фронта

```bash
python manage.py export_openapi              # схема API (openapi.json) из кода — в консоль
npm run api:types                            # во front/: типы фронта из этой схемы
```

Поменял API — `npm run api:types`, типы в тот же коммит. Как это устроено —
[слой core фронта](../../front/layers/core/readme.md).

## База данных

```bash
psql project                                 # подключиться
python manage.py dbshell                     # то же самое, с настройками проекта

pg_dump -Fc project > project.dump           # дамп
pg_restore -d project -c project.dump        # восстановить (-c сначала удалит объекты)

python manage.py shell                       # консоль Django, модели уже импортированы
python manage.py shell -c "print(Page.objects.count())"   # разовая команда без консоли
```

Сервис API из консоли — тем же вызовом `.sync()`, что и из админки
([как устроено](../app/core/readme.md#асинхронный-сервис-из-админки)):

```python
from form import services
services.resend_request_email.sync(form_request_id)
```

### Расширения Postgres — только миграцией

Расширение (`pg_trgm` — поиск по похожим строкам, `unaccent`, `uuid-ossp`, `citext`…) ставится
миграцией, а не руками в базе. Поставленное руками есть только в той базе, где его ставили: на проде
есть, а в dev, в CI, у вас локально и на новом сервере после переезда — нет, и код или следующая
миграция падают только там. Миграция ставит его везде одинаково:

```bash
python manage.py makemigrations <модуль> --empty -n pg_trgm   # пустая миграция, в неё — операция
```

```python
from django.contrib.postgres.operations import TrigramExtension   # или CreateExtension("unaccent")

class Migration(migrations.Migration):
    dependencies = [...]
    operations = [TrigramExtension()]
```

Миграция пройдёт и на сервере: «доверенные» расширения ставит сам владелец базы, а база проекта —
его. Доверенные — `pg_trgm`, `unaccent`, `uuid-ossp`, `citext`, `hstore`, `pgcrypto`, `btree_gin`,
`btree_gist`, `ltree`, `fuzzystrmatch`, `intarray`, `cube` и ещё несколько. Остальные (PostGIS,
pgvector) так не поставить — их ставит администратор сервера, и они нужны ещё и в CI и локально:
договоритесь с ним заранее. Поиск похожих строк в запросах Django (`__trigram_similar`) — ещё
и `django.contrib.postgres` в `INSTALLED_APPS`.

## Пользователи админки

```bash
python manage.py createsuperuser                      # новый суперпользователь
python manage.py changepassword admin@example.com     # сменить пароль, вход — по email
```

На сервере — те же команды через `docker compose run --rm cron python manage.py ...`
в папке проекта ([деплой](deploy.md)).

## Скопировать боевую базу в локальную

На сервере с нашей инфраструктурой — одной командой администратора (прод не останавливается), затем у себя:

```bash
ssh <сервер> sudo project-db-dump <проект> > prod.pgdump
pg_restore --no-owner --no-acl -c --if-exists -d project prod.pgdump   # pg_restore 17+
```

Без доступа администратора — через SSH-туннель к базе (`ssh -N -L 15432:127.0.0.1:5432 <сервер>`)
и пароль базы из `.env` проекта:

```bash
PGPASSWORD=<пароль_прода> pg_dump -h 127.0.0.1 -p 15432 -U <пользователь> -Fc <база_прода> > prod.pgdump
PGPASSWORD=<локальный_пароль> pg_restore --no-owner --no-acl -c --if-exists -U <пользователь> -d project prod.pgdump
```

В копии — персональные данные прода: держите её на зашифрованном диске. Свежие данные прода
в dev-проекте на сервере (проверить миграцию на настоящих данных) — `project-db-copy` администратора.

Перед заливкой стоит снять копию локальной базы: восстановление затирает данные.
В планах — команда `sync_from_prod`, которая делает это сама и с бэкапами, см. [todo.md](todo.md).

## Docker и деплой

На сервере, в папке проекта (`/srv/projects/<проект>/web`):

```bash
docker compose ps                       # что запущено
docker compose logs -f --tail=200 app   # логи приложения (без имени — всех сервисов)
docker compose run --rm cron python manage.py shell   # Django shell
docker compose up -d --force-recreate   # пересоздать после правки .env

git push origin dev             # выкладка dev-проекта: CI → образ → сервер сам (docs/deploy.md)
sudo project-deploy <проект> rollback   # администратор: вернуть версию до последней выкладки
```

Разовая команда без поднятия всего стека:

```bash
docker compose run --rm --no-deps cron python manage.py <команда>
```

## Обслуживание сервера

```bash
docker ps --format "{{.Names}} -> {{.Ports}}"   # что запущено и на каких портах
docker system prune -f                          # удалить неиспользуемые образы, контейнеры, сети (тома не трогает)
sudo usermod -aG docker <пользователь>          # разрешить пользователю docker, нужен перезаход
```

Проверить ветку перед push (push в `dev` — выкладка dev-проекта):

```bash
git rev-parse --abbrev-ref HEAD   # текущая ветка
git branch -a                     # все ветки, включая удалённые
git fetch --all                   # подтянуть список веток с сервера
git checkout <ветка>              # переключиться
```

Если образы тянутся медленно или реестр недоступен, прописывается зеркало
в `/etc/docker/daemon.json`, после чего docker перезапускается:

```json
{ "registry-mirrors": ["https://mirror.gcr.io"] }
```

Права на docker выдаются только через группу (`usermod -aG docker`). Совет открыть
доступ к сокету через `chmod 666 /var/run/docker.sock` встречается в старых заметках —
так делать нельзя: это отдаёт docker всем пользователям машины, а docker равен правам root.

## Очередь задач

Нужна, только когда в настройках задан `REDIS_URL`. Без него задачи выполняются
прямо в процессе API, и ни Redis, ни воркер не нужны.

```bash
taskiq worker project.worker:broker             # запустить воркер вручную
docker compose logs -f worker                   # что он сейчас делает

docker compose exec redis redis-cli KEYS '*'    # посмотреть, какие очереди есть
docker compose exec redis redis-cli FLUSHALL    # очистить Redis целиком
```

`FLUSHALL` стирает всё содержимое Redis, а не только застрявшие задачи. На проде
так делать можно, лишь когда точно известно, что в Redis нет ничего другого.

## Проверки

```bash
python manage.py check                       # общие ошибки конфигурации
python manage.py check --deploy              # настройки безопасности для прода
python manage.py sync_async_models --check   # модели для API не отстали
python manage.py env_settings                # настройки модулей: что действует и откуда (.env или по умолчанию)
python manage.py test --keepdb               # тесты: база test_<база>, Redis не нужен
python manage.py test form --keepdb          # тесты одного модуля
python manage.py test form.tests.test_admin --keepdb   # один файл; через точку дальше — класс, тест
python manage.py test -k filter --keepdb     # тесты, в имени которых есть «filter»
python manage.py test --failfast --keepdb    # остановиться на первом упавшем
python manage.py test --parallel auto --keepdb   # в несколько процессов, по числу ядер
```

Тестам нужен PostgreSQL, где можно создать базу (`test_` + имя из `.env`). `--keepdb` оставляет
её между прогонами — второй запуск быстрее. Без него Django спросит, удалить ли старую;
`--noinput` — удалить молча. `--parallel` заводит по копии тестовой базы на процесс
(`test_<база>_1`, `_2`…). Запустить только упавшие в прошлый раз, как `pytest --lf`, Django не умеет:
имя упавшего теста — в выводе, его и передать.

Своего Postgres нет — в Docker, тот же образ и та же версия, что в CI (`.github/workflows/back.yml`):

```bash
docker run -d --name web-start-pg -p 127.0.0.1:5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust mirror.gcr.io/library/postgres:17
docker exec web-start-pg createdb -U postgres project   # база для migrate и runserver, имя — из DEV_DB_NAME
docker stop web-start-pg                                # остановить; docker start web-start-pg — снова, базы на месте
docker rm -fv web-start-pg                              # удалить вместе с базами (без -v они останутся на диске безымянным томом)
```

`.env` из `.env.txt` подходит как есть: `DEV=True`, `DEV_DB_USER=postgres`, `DEV_DB_PASSWORD=` пустой,
`DEV_DB_HOST=localhost`, `DEV_DB_PORT=5432`. Тестам хватает первой строки: `test_<база>` Django
заводит сам, база из `DEV_DB_NAME` им не нужна. `trust` пускает в базу без пароля, поэтому перед портом —
`127.0.0.1:`: так он открыт только самому ноутбуку. Без адреса Docker откроет порт на всех сетях,
и в кафе или в офисе к базе подключится любой из той же сети. Порт 5432 занят своим Postgres —
`-p 127.0.0.1:5433:5432` и `DEV_DB_PORT=5433`.

## Шпаргалка

- Поменял модели — `makemigrations`, потом `sync_async_models`, в коммит оба файла.
- Поменял API — `npm run api:types` во `front/`, типы в тот же коммит.
- Что-то не поднимается в докере — `docker compose logs app`, чаще всего дело в `.env`.
- Нужна разовая команда на сервере — `docker compose run --rm --no-deps cron python manage.py ...`.
- Перед выкаткой на прод — `check --deploy`.
- Перед коммитом — `test --keepdb`.
