import atexit
import os
import threading
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
_pool = None
_pool_lock = threading.Lock()


def _create_pool():
    # Thick-режим (через Oracle Instant Client) включаем только если явно попросили
    # через ORACLE_THICK_MODE=true. По умолчанию thin-режим - не требует Instant
    # Client и, в отличие от thick, не делает блокирующих OCI-вызовов в обход gevent.
    if platform == 'unix' and cfg.oracle_thick_mode:
        oracledb.init_oracle_client(lib_dir=LD_LIBRARY_PATH)
        log.info("Oracle client: THICK режим (ORACLE_THICK_MODE=true).")
    else:
        log.info("Oracle client: THIN режим (по умолчанию, gevent-совместимый).")

    pool = oracledb.create_pool(user=cfg.username,
                                 password=cfg.password,
                                 host=cfg.host,
                                 port=cfg.port,
                                 service_name=cfg.service,
                                 timeout=cfg.timeout,
                                 wait_timeout=cfg.wait_timeout,
                                 max_lifetime_session=cfg.max_lifetime_session,
                                 expire_time=cfg.expire_time,
                                 tcp_connect_timeout=cfg.tcp_connect_timeout,
                                 min=cfg.pool_min,
                                 max=cfg.pool_max,
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
    log.info(f"Пул соединений БД Oracle создан (pid={os.getpid()}). DB: {cfg.host}:{cfg.port}/{cfg.service}")
    return pool


def init_pool():
    """
    Явно создаёт пул (если он ещё не создан). Вызывается:
      - из post_worker_init() в gunicorn.conf.py - сразу после форка воркера,
        до начала обработки запросов, чтобы проблемы с БД (недоступна, неверные
        креды) проявлялись сразу при старте воркера, а не "внезапно" на первом
        запросе пользователя;
      - лениво из get_connection(), если по каким-то причинам ещё не была вызвана
        явно (dev-сервер main_app.py на Windows не использует gunicorn/хуки -
        там пул создаётся при первом реальном обращении к БД).
    Потокобезопасно (double-checked locking) - на случай, если несколько gevent
    гринлетов одновременно обратятся за первым соединением в только что
    запущенном воркере.
    """
    global _pool
    if _pool is not None:
        return
    with _pool_lock:
        if _pool is None:
            _pool = _create_pool()


def close_pool():
    """
    Корректно закрывает пул соединений при остановке процесса (gunicorn worker
    recycle/restart, dev-server Ctrl+C и т.п.). До этой правки пул нигде явно не
    закрывался в боевом режиме - соединения на стороне Oracle могли оставаться
    висеть до истечения expire_time/max_lifetime_session, что при частых
    рестартах могло накапливать "зависшие" сессии на БД.
    force=True закрывает пул немедленно, откатывая незавершённые транзакции,
    вместо того чтобы кидать ошибку, если в моменте есть занятые соединения.
    """
    global _pool
    if _pool is None:
        return
    try:
        _pool.close(force=True)
        log.info(f"Пул соединений БД Oracle закрыт (graceful shutdown, pid={os.getpid()}).")
    except Exception as e:
        log.error(f"Ошибка при закрытии пула соединений БД: {e}")
    finally:
        _pool = None


atexit.register(close_pool)


def get_connection():
    if _pool is None:
        init_pool()
    return _pool.acquire()


def close_connection(connection):
    if _pool is not None:
        _pool.release(connection)


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



def select_2(stmt, params=None):
    results = []
    with get_connection() as connection:
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
    except oracledb.DatabaseError as e:
        error, = e.args
        log.error(f"ERROR -----plsql-func-----> FNAME: {f_name}\nargs: {args}\nerror: {error.code} : {error.message}")
    finally:
        return ret


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
    _pool.close()