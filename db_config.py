from gfss_parameter import platform, debug
from os import getenv

if platform == 'unix':
    _default_pool_min = 1
    # pool_max - это лимит НА КАЖДЫЙ воркер gunicorn (см. db/connect.py: пул теперь
    # создаётся отдельно в каждом воркере через post_worker_init, а не один общий
    # на всё приложение). Общий потолок соединений к Oracle = workers * pool_max.
    # 4 ядра (workers=cpu_count()) * 10 = 40 - тот же суммарный бюджет соединений,
    # что фактически был у приложения и раньше (до фикса с post_worker_init все
    # воркеры небезопасно делили между собой один пул на ~40 соединений). Если
    # число ядер на сервере изменится - пересчитать (workers * pool_max) и при
    # необходимости поднять/опустить через DB_POOL_MAX, свериться с лимитом
    # PROCESSES/SESSIONS на стороне Oracle (там же "сидят" и другие приложения).
    _default_pool_max = 10
    _default_pool_inc = 2
else:
    _default_pool_min = 1
    _default_pool_max = 4
    _default_pool_inc = 1

pool_min = int(getenv('DB_POOL_MIN', str(_default_pool_min)))
pool_max = int(getenv('DB_POOL_MAX', str(_default_pool_max)))
pool_inc = int(getenv('DB_POOL_INC', str(_default_pool_inc)))

# Значения по умолчанию оставлены как fallback для локальной разработки.
# На проде задавайте DB_USERNAME/DB_PASSWORD/DB_HOST/DB_PORT/DB_SERVICE через
# переменные окружения (см. court.env.example и service/court.service).
username = getenv('DB_USERNAME', 'xyz')
password = getenv('DB_PASSWORD', 'xyz')
host = getenv('DB_HOST', '192.168.20.60')
port = int(getenv('DB_PORT', '1521'))
service = getenv('DB_SERVICE', 'gfssdb.gfss.kz')

expire_time = 2 # количество минут между отправкой keepalive
tcp_connect_timeout = 5 # Максимальное время ожидания установления соединения
timeout = 300       # В секундах. Время простоя, после которого курсор освобождается
wait_timeout = 2000  # Время (в миллисекундах) ожидания доступного сеанса в пуле, перед тем как выдать ошибку
max_lifetime_session = 7200  # Время в секундах, в течении которого может существоват сеанс
retry_count = 1
retry_delay = 2

# Сколько секунд соединение может простаивать в пуле, прежде чем при следующей
# выдаче (acquire) драйвер сделает "пинг" на сервер, чтобы убедиться, что оно живое.
# Именно это защищает от зависаний из-за "молча отвалившихся" на стороне БД
# соединений (напр. firewall/DB тихо порвал TCP по таймауту, а клиент не в курсе).
ping_interval = int(getenv('DB_PING_INTERVAL', '60'))

# По умолчанию python-oracledb использует "thick"-режим только если явно вызван
# oracledb.init_oracle_client(). На unix-проде это включалось всегда - см. db/connect.py.
# Thick-режим не совместим с gevent-кооперативностью (блокирующие OCI-вызовы), поэтому
# по умолчанию теперь используется "thin"-режим (чистый Python, gevent-friendly).
# Если когда-нибудь понадобится вернуть thick-режим (напр. для функций, которых нет в thin,
# такие как advanced queuing/некоторые типы аутентификации) - выставьте ORACLE_THICK_MODE=true.
oracle_thick_mode = getenv('ORACLE_THICK_MODE', 'false').lower() == 'true'

