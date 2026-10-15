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

# Локальный список администраторов отчётности: должность -> подразделения.
# Роль в приложении заполняется здесь, а не в SSO (у него другая функция):
# Admin, если должность и подразделение пользователя есть в этом списке,
# иначе User (см. ACCESS-PLAN.md, § 3).
# Подразделение можно писать коротким именем из AD (ou_name, например DITiTO)
# или полным названием департамента (dep_name) - сравнивается и с тем, и с
# другим. "*" - любое подразделение при этой должности.
admin_post = { "Главный разработчик": ["DITiTO"],
               "Ведущий разработчик": ["DITiTO"],
               "Директор": ["Департамент анализа, учета и статистики",],
               "Главный специалист": ["Департамент анализа, учета и статистики"],
               }


ldap_admins = ['Гусейнов Шамиль Аладдинович', 'Алибаева Мадина Жасулановна', 'Маликов Айдар Амангельдыевич']

ldap_server = 'ldap://192.168.1.3:3268'
ldap_user = 'cn=ldp,ou=admins,dc=gfss,dc=kz'
ldap_password = 'hu89_fart7'
ldap_ignore_ou = ['UVOLEN',]
