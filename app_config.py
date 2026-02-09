from gfss_parameter import BASE

styles = ['color', 'dark']

debug=False

host = 'localhost'
port=5090
src_lang = 'file'
language = 'ru'
URL_LOGIN = 'http://192.168.1.34:8000'
LOG_PATH = f"{BASE}/logs"
REPORT_MODULE_PATH = f"reports"
REPORT_PATH = f"{BASE}/spool"
UPLOAD_PATH = f"{BASE}/uploads"

tolem_server='http://tolem.gfss.kz'

sso_server = 'http://192.168.1.34:8825'

ldap_admins = ['Гусейнов Шамиль Аладдинович', 'Алибаева Мадина Жасулановна', 'Маликов Айдар Амангельдыевич']
ldap_server = 'ldap://192.168.1.3:3268'
ldap_user = 'cn=ldp,ou=admins,dc=gfss,dc=kz'
ldap_password = 'hu89_fart7'
ldap_ignore_ou = ['UVOLEN',]
ldap_boss = ['Директор', 'Руководитель','И.о. директора','Главный разработчик', 'Главный специалист', 'Главный специалист-актуарий']
permit_deps = ['Управление актуарных расчетов и моделирования', 'Департамент анализа, учета и статистики',
               'Департамент координации и мониторинга социальных выплат', 'Департамент по работе с плательщиками',
               'Департамент информационных технологий и технического обеспечения', 'Департамент контроля качества назначений социальных выплат']