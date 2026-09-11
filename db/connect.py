import atexit
import os
import threading
from configparser import ConfigParser
import db_config as cfg
from gfss_parameter import LD_LIBRARY_PATH, platform
from util.logger import log
from util.ip_addr import ip_addr 
import oracledb


def init_session(connection, requestedTag_ignored):
    cursor = connection.cursor()
    cursor.execute("ALTER SESSION SET NLS_TERRITORY = 'CIS'")
    cursor.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'DD.MM.YYYY HH24:MI'")
    cursor.execute("ALTER SESSION SET NLS_NUMERIC_CHARACTERS = ', '")
    log.info("--------------> Executed: ALTER SESSION SET NLS_TERRITORY = 'CIS'")
    log.info("--------------> Executed: ALTER SESSION SET NLS_DATE_FORMAT = 'DD.MM.YYYY HH24:MI'")
    cursor.close()

# Пул НЕ создаётся при импорте модуля - см. init_pool() ниже. Причина: gunicorn.conf.py
# использует preload_app=True, то есть master-процесс gunicorn импортирует всё
# приложение (а значит и этот модуль) ОДИН раз, а затем форкает N воркеров из него.
# Если бы пул (а значит и открытые TCP-сокеты к Oracle) создавался прямо при импорте,
# все форкнутые воркеры унаследовали бы через fork() ОДНИ И ТЕ ЖЕ уже открытые
# соединения и делили бы их между собой - при параллельном использовании несколькими
# процессами это ломает протокол Oracle на уровне TCP (зависания, обрывы, "случайные"
# ошибки). Вместо этого каждый воркер создаёт себе отдельный пул сам, уже после форка,
# через post_worker_init() в gunicorn.conf.py.
#
# ПРОФИЛИ ПОДКЛЮЧЕНИЯ.
# Основная учётка (профиль DEFAULT_PROFILE) - это схема reports, под которой работает
# всё приложение; её настройки, как и раньше, берутся из db_config. Части отчётов
# нужны таблицы боевых схем (pnpd_document, pnpt_payment, person и т.п.), которые
# схеме reports не видны - ORA-00942. Такие отчёты запрашивают отдельный профиль,
# а его учётка читается напрямую из секции db_config.ini (db_dsn / db_user /
# db_password) - там, где все креды и так лежат. Соответствие
# "профиль -> секция ini" задаётся в PROFILE_SECTIONS ниже.
#
# Пул на профиль создаётся лениво, при первом обращении, и тоже уже после форка.
DEFAULT_PROFILE = 'default'
LOADER_PROFILE = 'loader'

# профиль -> секция в db_config.ini
PROFILE_SECTIONS = {
    LOADER_PROFILE: 'rep_db_loader',
}

# ini лежит рядом с db_config.py
DB_CONFIG_INI = os.path.join(os.path.dirname(os.path.abspath(cfg.__file__)), 'db_config.ini')

_pools = {}                       # profile -> oracledb.ConnectionPool
_pool_lock = threading.Lock()
_thick_initialized = False        # init_oracle_client() можно звать только один раз на процесс
_ini = None                       # разобранный db_config.ini (только для доп. профилей)


def _ini_section(section_name):
    """Секция db_config.ini. Читается лениво и один раз на процесс."""
    global _ini
    if _ini is None:
        # inline_comment_prefixes не задаём: иначе '#' внутри пароля обрежется
        parser = ConfigParser()
        if not parser.read(DB_CONFIG_INI, encoding='utf-8'):
            raise ValueError(f'Не найден или пуст файл настроек БД: {DB_CONFIG_INI}')
        _ini = parser
    if section_name not in _ini:
        raise ValueError(f'В {DB_CONFIG_INI} нет секции [{section_name}]')
    return _ini[section_name]


def _profile_credentials(profile):
    """Параметры подключения для профиля.

    default - как и раньше, из db_config; остальные профили - из секции
    db_config.ini (db_dsn / db_user / db_password)."""
    if profile == DEFAULT_PROFILE:
        return dict(user=cfg.username,
                    password=cfg.password,
                    host=cfg.host,
                    port=cfg.port,
                    service_name=cfg.service)

    section_name = PROFILE_SECTIONS.get(profile, profile)
    section = _ini_section(section_name)
    missing = [k for k in ('db_dsn', 'db_user', 'db_password') if not section.get(k)]
    if missing:
        raise ValueError(f'В {DB_CONFIG_INI}, секция [{section_name}]: '
                         f'не заданы {", ".join(missing)}')
    return dict(user=section['db_user'],
                password=section['db_password'],
                dsn=section['db_dsn'])


def _create_pool(profile=DEFAULT_PROFILE):
    global _thick_initialized

    # Thick-режим (через Oracle Instant Client) включаем только если явно попросили
    # через ORACLE_THICK_MODE=true. По умолчанию thin-режим - не требует Instant
    # Client и, в отличие от thick, не делает блокирующих OCI-вызовов в обход gevent.
    # Инициализировать клиент можно ровно один раз на процесс, поэтому при создании
    # второго пула (другой профиль) этот блок пропускается.
    if not _thick_initialized:
        if platform == 'unix' and cfg.oracle_thick_mode:
            oracledb.init_oracle_client(lib_dir=LD_LIBRARY_PATH)
            log.info("Oracle client: THICK режим (ORACLE_THICK_MODE=true).")
        else:
            log.info("Oracle client: THIN режим (по умолчанию, gevent-совместимый).")
        _thick_initialized = True

    creds = _profile_credentials(profile)

    # Дополнительные профили нужны эпизодически (тяжёлые отчёты), поэтому по умолчанию
    # они не держат простаивающих соединений: min=0.
    pool_min = cfg.pool_min if profile == DEFAULT_PROFILE else getattr(cfg, f'{profile}_pool_min', 0)
    pool_max = cfg.pool_max if profile == DEFAULT_PROFILE else getattr(cfg, f'{profile}_pool_max', cfg.pool_max)

    pool = oracledb.create_pool(**creds,
                                 timeout=cfg.timeout,
                                 wait_timeout=cfg.wait_timeout,
                                 max_lifetime_session=cfg.max_lifetime_session,
                                 expire_time=cfg.expire_time,
                                 tcp_connect_timeout=cfg.tcp_connect_timeout,
                                 min=pool_min,
                                 max=pool_max,
                                 increment=cfg.pool_inc,
                                 # getmode=WAIT (умолчание в драйвере) означает, что
                                 # acquire() при исчерпанном пуле ждёт СВОБОДНОЕ
                                 # соединение БЕСКОНЕЧНО - wait_timeout выше в этом
                                 # режиме молча игнорируется! Именно TIMEDWAIT
                                 # заставляет драйвер реально уважать wait_timeout и
                                 # кидать ошибку вместо зависания запроса/воркера.
                                 getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
                                 # Сколько секунд соединение может простаивать в
                                 # пуле, прежде чем перед выдачей его "пропингуют" -
                                 # защита от тихо умерших на стороне БД/сети
                                 # соединений.
                                 ping_interval=cfg.ping_interval,
                                 # Ретраи попытки установить соединение при
                                 # создании/пополнении пула (например, БД на
                                 # секунду недоступна во время рестарта).
                                 retry_count=cfg.retry_count,
                                 retry_delay=cfg.retry_delay,
                                 session_callback=init_session)
    db_addr = creds.get('dsn') or f"{creds.get('host')}:{creds.get('port')}/{creds.get('service_name')}"
    log.info(f"Пул соединений БД Oracle создан (profile={profile}, user={creds['user']}, "
             f"pid={os.getpid()}). DB: {db_addr}")
    return pool


def init_pool(profile=DEFAULT_PROFILE):
    """
    Явно создаёт пул указанного профиля (если он ещё не создан). Вызывается:
      - из post_worker_init() в gunicorn.conf.py - сразу после форка воркера,
        до начала обработки запросов, чтобы проблемы с БД (недоступна, неверные
        креды) проявлялись сразу при старте воркера, а не "внезапно" на первом
        запросе пользователя;
      - лениво из get_connection(), если по каким-то причинам ещё не была вызвана
        явно (dev-сервер main_app.py на Windows не использует gunicorn/хуки -
        там пул создаётся при первом реальном обращении к БД). Так же лениво
        создаются пулы дополнительных профилей - при первом отчёте, который их
        запросит; это тоже происходит уже после форка, поэтому fork-safe.
    Потокобезопасно (double-checked locking) - на случай, если несколько gevent
    гринлетов одновременно обратятся за первым соединением в только что
    запущенном воркере.
    """
    if _pools.get(profile) is not None:
        return
    with _pool_lock:
        if _pools.get(profile) is None:
            _pools[profile] = _create_pool(profile)


def close_pool():
    """
    Корректно закрывает пулы соединений при остановке процесса (gunicorn worker
    recycle/restart, dev-server Ctrl+C и т.п.). До этой правки пул нигде явно не
    закрывался в боевом режиме - соединения на стороне Oracle могли оставаться
    висеть до истечения expire_time/max_lifetime_session, что при частых
    рестартах могло накапливать "зависшие" сессии на БД.
    force=True закрывает пул немедленно, откатывая незавершённые транзакции,
    вместо того чтобы кидать ошибку, если в моменте есть занятые соединения.
    """
    for profile, pool in list(_pools.items()):
        if pool is None:
            continue
        try:
            pool.close(force=True)
            log.info(f"Пул соединений БД Oracle закрыт (profile={profile}, "
                     f"graceful shutdown, pid={os.getpid()}).")
        except Exception as e:
            log.error(f"Ошибка при закрытии пула соединений БД (profile={profile}): {e}")
        finally:
            _pools.pop(profile, None)


atexit.register(close_pool)


def get_connection(profile=DEFAULT_PROFILE):
    if _pools.get(profile) is None:
        init_pool(profile)
    return _pools[profile].acquire()


def close_connection(connection):
    # Соединение само знает, из какого пула оно взято, поэтому close() возвращает
    # его туда же. Раньше здесь был release() в единственный глобальный пул.
    if connection is not None:
        connection.close()


def is_english_column(name: str) -> bool: 
    return all(c.isascii() and (c.isalnum() or c == '_') for c in name)


def _select(stmt, cursor, params=None):
    results = []
    try:
        cursor.execute(stmt, params or {})

        columns = [ col[0].lower() if is_english_column(col[0]) else col[0] for col in cursor.description ]

        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results
    except oracledb.DatabaseError as e:
        error, = e.args
        err_message = f'STMT: {stmt}\nPARAMS: {params}\n\t{error.code} : {error.message}'
        log.error(f"------select------> ERROR\n{err_message}\n")
        return []


def select(stmt, params=None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _select(stmt, cursor, params)



def select_2(stmt, params=None, profile=DEFAULT_PROFILE, raise_on_error=False):
    # profile        - под какой учётной записью Oracle выполнять запрос
    #                  (см. комментарий к DEFAULT_PROFILE выше). Отчёты по боевым
    #                  схемам передают profile=LOADER_PROFILE.
    # raise_on_error - пробрасывать ошибку БД вместо возврата пустого списка.
    #                  Нужно там, где пустой результат нельзя путать с ошибкой
    #                  запроса: формирование отчёта иначе тихо запишет пустой
    #                  файл и выставит ему статус "готов".
    # Оба аргумента необязательные, поведение старых вызовов select_2(stmt, params)
    # не меняется.
    results = []
    with get_connection(profile) as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(stmt, params or {})

                columns = [ col[0].lower() if is_english_column(col[0]) else col[0] for col in cursor.description ]

                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                return results
            except oracledb.DatabaseError as e:
                error, = e.args
                err_message = f'STMT: {stmt}\nPARAMS: {params}\n\t{error.code} : {error.message}'
                log.error(f"------select------> ERROR\n{err_message}\n")
                if raise_on_error:
                    raise
                return []


def select_one(stmt, args):
    result = {}
    with get_connection() as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(stmt, args)
                columns = [ col[0].lower() if is_english_column(col[0]) else col[0] for col in cursor.description ]
                row = cursor.fetchone()
                if row:
                    result=dict(zip(columns, row))
                else:
                    log.info(f'--->\n\tSELECT_ONE. ROW is Empty\n\tparams: {args}\n\tSTMT: {stmt}\n<---')
                return result
            except oracledb.DatabaseError as e:
                error, = e.args
                err_message = f'STMT: {stmt}\n\tARGS: {args}\n\t{error.code} : {error.message}'
                log.error(f"------select------> ERROR\n\t{err_message}")
                log.error(err_message)
                return {}


def plsql_execute(cursor, f_name, cmd, args):
    try:
        cursor.execute(cmd, args)
    except oracledb.DatabaseError as e:
        error, = e.args
        log.error(f"ERROR ------execute------> FNAME:{f_name}\nIP_Addr: {ip_addr()}, args: {args}\nerror: {error.code} : {error.message}")


def plsql_proc(cursor, f_name, proc_name, args):
    try:
        cursor.callproc(proc_name, args)
    except oracledb.DatabaseError as e:
        error, = e.args
        log.error(f"ERROR -----plsql-proc-----> FNAME: {f_name}\nARGS: {args}\nerror: {error.code} : {error.message}")


def plsql_proc_s(f_name, proc_name, args):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            plsql_proc(cursor, f_name, proc_name, args)


def plsql_func(cursor, f_name, func_name, args):
    ret = ''
    try:
        ret = cursor.callfunc(func_name, args)
        return ret
    except oracledb.DatabaseError as e:
        error, = e.args
        log.error(f"ERROR -----plsql-func-----> FNAME: {f_name}\nargs: {args}\nerror: {error.code} : {error.message}")


def plsql_func_s(f_name, proc_name, args):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return plsql_func(cursor, f_name, proc_name, args)


if __name__ == "__main__":
    log.debug("Тестируем CONNECT блок!")
    con = get_connection()
    log.debug("Версия: " + con.version)
    val = "Hello from main"
    con.close()
    close_pool()