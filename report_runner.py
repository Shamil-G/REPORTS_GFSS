"""
Универсальный раннер для отчётов, запускаемых в отдельном процессе.

Заменяет прежний os.fork() внутри gevent-воркера gunicorn (см. call_report.py).
os.fork() в gevent-процессе создаёт дочерний процесс, наследующий "мёртвый"
event loop (epoll fd, гринлеты) родителя - первый же сетевой вызов к Oracle
в такой копии падает практически мгновенно. Здесь же через subprocess.Popen
запускается полностью новый, чистый интерпретатор Python - без унаследованного
gevent hub и без общих с родительским воркером TCP-сокетов пула Oracle.

Ничего в самих модулях отчётов (rep_dia_300_09.py и т.п.) менять не нужно -
они как были функциями do_report(**params), так и остаются. Раньше
call_report.py вызывал loaded_module.do_report(**params) напрямую в
forked-child; теперь он спавнит этот файл как отдельный процесс, а тот
делает ровно тот же вызов - только уже в чистом процессе.

Использование (см. call_report.py):
    python -m report_runner <module_path> <json_params>

<module_path>  - dotted-путь модуля отчёта, тот же, что вычисляется в
                 call_report.py: f"{module_dir}.{proc}"
                 (например "model.reports.DIA.dia_300.rep_dia_300_09")
<json_params>  - JSON-сериализованный словарь параметров, тот же самый,
                 что раньше передавался в do_report(**params) напрямую.
                 Все значения должны быть JSON-сериализуемыми (строки,
                 числа, списки, словари) - в текущих отчётах так и есть
                 (даты передаются строками, коды - строками/числами).
"""
import sys
import json
import importlib
import traceback

from util.logger import log


def main():
    if len(sys.argv) != 3:
        log.error(f'REPORT_RUNNER. Неверные аргументы командной строки: {sys.argv}')
        sys.exit(1)

    module_path = sys.argv[1]
    raw_params = sys.argv[2]

    try:
        params = json.loads(raw_params)
    except json.JSONDecodeError as e:
        log.error(f'REPORT_RUNNER. Не удалось разобрать JSON-параметры.\n'
                  f'module: {module_path}\nraw: {raw_params}\nerror: {e}')
        sys.exit(1)

    log.info(f'REPORT_RUNNER. START. module: {module_path}, params: {params}')

    try:
        loaded_module = importlib.import_module(module_path)
        loaded_module.do_report(**params)
        log.info(f'REPORT_RUNNER. DONE. module: {module_path}')
    except Exception:
        log.error(f'REPORT_RUNNER. FAILED. module: {module_path}\n{traceback.format_exc()}')
        sys.exit(1)


if __name__ == "__main__":
    main()
