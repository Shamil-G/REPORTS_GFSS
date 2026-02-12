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

admin_post = { "Главный разработчик": ["Департамент информационных технологий и технического обеспечения"], 
               "Директор": ["Департамент анализа, учета и статистики",],
               "Главный специалист": ["Департамент анализа, учета и статистики"],
               }

work_post = { "Директор": ["*"],
              "Главный специалист-актуарий": ["*"],
              "Ведущий специалист" : ["Департамент анализа, учета и статистики"],
            }

view_post = { "И.о. директора": ["*",],
              "Руководитель": ["*",], 
              "Ведущий специалист-актуарий" : ["*"],
              "Ведущий разработчик": ["*"],
            }


ldap_admins = ['Гусейнов Шамиль Аладдинович', 'Алибаева Мадина Жасулановна', 'Маликов Айдар Амангельдыевич']

ldap_server = 'ldap://192.168.1.3:3268'
ldap_user = 'cn=ldp,ou=admins,dc=gfss,dc=kz'
ldap_password = 'hu89_fart7'
ldap_ignore_ou = ['UVOLEN',]
