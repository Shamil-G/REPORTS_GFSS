from __init__ import app, log, login_manager
import app_config as cfg
#from db.user_login import * 
from view.routes import *

from gfss_parameter import SSO_LOGIN
if SSO_LOGIN:
    from sso.user_login_sso import *
else:
    from ldap.user_login import *


class _QuietDevAccessLog(__import__('logging').Filter):
    """Консольный access-лог встроенного сервера (python main_app.py).

    Автообновление /running-reports (?auto=1) раз в 4 с тянет страницу целиком, и каждый раз за ней
    идут десять с лишним запросов /static/... с ответом 304 (при Ctrl+F5 - 200). Такие строки не несут информации и
    засоряют консоль; запросы с ошибками и все остальные обращения остаются. В gunicorn то же
    делает gunicorn.conf.py (_SkipAutoRefresh).
    """

    def filter(self, record):
        msg = record.getMessage()
        if '/running-reports?auto=1' in msg:
            return False
        return not ('GET /static/' in msg and ('" 304 ' in msg or '" 200 ' in msg))


if __name__ == "__main__":
    __import__('logging').getLogger('werkzeug').addFilter(_QuietDevAccessLog())
    log.info(f"===> Main REPORTS-GFSS started on {cfg.host}:{cfg.port}, work_dir: {cfg.BASE}")
    from model.manage_reports import clear_running_reports
    clear_running_reports()
    app.run(host=cfg.host, port=cfg.port, debug=False)
