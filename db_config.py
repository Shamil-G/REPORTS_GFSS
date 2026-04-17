from gfss_parameter import platform, ORACLE_HOME
from util.logger import log


if platform == 'unix':
    pool_min = 1
    pool_max = 40
    pool_inc = 10
    username = 'reports'
else:
    pool_min = 4
    pool_max = 10
    pool_inc = 4
    username = 'reports_test'

# report_db_dsn = '172.31.33.29:1521/gfss'
# report_db_user = 'sswh'
# report_db_password = 'sswh'
dsn = '192.168.20.60:1521/gfssdb.gfss.kz'
password = 'reports'

expire_time = 2  # количество минут между отправкой keepalive
tcp_connect_timeout = 5 # Кол-во секунд ождания установления соединения
timeout = 300     # В секундах. Время простоя, после которого курсор освобождается
wait_timeout = 2000  # Время (в миллисекундах) ожидания доступного сеанса в пуле, перед тем как выдать ошибку
max_lifetime_session = 180  # Время в секундах, в течении которого может существоват сеанс
retry_count = 1
retry_delay = 2

Debug = True

log.info(f"=====>\tDB CONFIG\n\tPLATFORM: {platform}\n\tORACLE_HOME: {ORACLE_HOME}\n\tDSN: {dsn}\n\tUSERNAME: {username}")

