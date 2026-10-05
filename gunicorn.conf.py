import logging
import multiprocessing
from gfss_parameter import app_name, BASE
from app_config import port

bind = f"localhost:{port}"
workers = int(multiprocessing.cpu_count()*2) + 1
worker_class = "gevent"
print(f'GUNICORN. change DIRECTORY: {BASE}')

chdir = BASE

wsgi_app = "wsgi:app"
loglevel = 'info'
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s"  "%(a)s"'
accesslog = "logs/reports-gunicorn-access.log"

error_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s"  "%(a)s"'
errorlog = "logs/reports-gunicorn-error.log"
proc_name = f'{app_name}'
# Перезапуск после N кол-во запросов
max_requests = 0
# Перезапуск, если ответа не было более 60 сек
timeout = 180
# umask or -m 007
umask = 0x007
# Проверка IP адресов, с которых разрешено обрабатывать набор безопасных заголовков
forwarded_allow_ips = '192.169.1.33,127.0.0.1'
#preload увеличивает производительность - хуже uwsgi!
preload_app = 'True'


class _SkipAutoRefresh(logging.Filter):
    """Не пишет в access-лог запросы автообновления /running-reports?auto=1.

    Пока отчёт готовится, страница дёргает сервер раз в несколько секунд (см.
    util.logger.is_auto_refresh); без фильтра access-лог забивается одинаковыми
    строками. Остальные запросы к /running-reports пишутся как обычно.
    """

    def filter(self, record):
        return '/running-reports?auto=1' not in record.getMessage()


def on_starting(server):
    """
    Вызывается ОДИН раз в master-процессе при старте сервиса (не при рестарте
    отдельного воркера и не по HUP). При остановке сервиса systemd гасит всю его
    группу процессов, включая report_runner, поэтому записи "готовится" в журнале
    к этому моменту заведомо осиротели - убираем их.

    Здесь же ставится фильтр access-лога: логгер gunicorn.access общий, воркеры
    наследуют его при fork().

    Чистка идёт отдельным процессом Python: master не должен сам открывать
    соединения с Oracle, иначе их унаследуют форкнутые воркеры (см. post_worker_init).
    """
    import subprocess
    import sys
    logging.getLogger('gunicorn.access').addFilter(_SkipAutoRefresh())
    try:
        result = subprocess.run([sys.executable, '-c',
                                 'from model.manage_reports import clear_running_reports; clear_running_reports()'],
                                cwd=BASE, timeout=120)
        if result.returncode != 0:
            print(f'GUNICORN. CLEAR RUNNING REPORTS FAILED: код возврата {result.returncode}')
    except Exception as e:
        print(f'GUNICORN. CLEAR RUNNING REPORTS FAILED: {e}')


def post_worker_init(worker):
    """
    Вызывается gunicorn'ом в КАЖДОМ воркере сразу после его форка из master-процесса,
    до того как этот воркер начнёт принимать запросы.

    Из-за preload_app=True выше приложение (в т.ч. модуль db/connect.py) импортируется
    ОДИН раз в master-процессе, а затем форкается в N воркеров. Раньше пул соединений
    Oracle создавался прямо при импорте db/connect.py, то есть ДО форка - все воркеры
    наследовали через fork() одни и те же уже открытые TCP-сокеты к Oracle и делили их
    между собой. При параллельном использовании одного и того же сокета несколькими
    процессами это ломает протокол на уровне TCP (похоже на источник непонятных
    зависаний/обрывов соединений).

    db/connect.py теперь не создаёт пул при импорте (см. init_pool()/get_connection()
    там) - вместо этого мы явно создаём пул здесь, уже после форка, так что у каждого
    воркера гарантированно свой собственный, независимый пул соединений.
    """
    from db.connect import init_pool
    init_pool()
