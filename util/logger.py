import logging
import logging.config
from logging.handlers import RotatingFileHandler
import gfss_parameter as cfg
import app_config as cfg_app
from app_config import debug


def init_logger():
    logger = logging.getLogger('REPORTS-GFSS')
    # logging.getLogger('PDD').addHandler(logging.StreamHandler(sys.stdout))
    # Console
    logging.getLogger('REPORTS-GFSS').addHandler(logging.StreamHandler())
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    fh = logging.FileHandler(f"{cfg_app.LOG_PATH}/{cfg.app_name.lower()}.log", encoding="UTF-8")
    # fh = RotatingFileHandler(cfg.LOG_FILE, encoding="UTF-8", maxBytes=100000000, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    logger.addHandler(fh)
    logger.info('REPORTS-GFSS Logging started')
    return logger

log = init_logger()


def is_auto_refresh() -> bool:
    """Запрос от автообновления страницы /running-reports (?auto=1).

    Пока отчёт готовится, страница дёргает сервер раз в несколько секунд; такие
    запросы не должны писать в журнал, иначе он забивается одинаковыми строками.
    """
    from flask import request, has_request_context
    return has_request_context() and request.args.get('auto') == '1'
