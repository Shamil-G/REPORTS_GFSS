from gfss_parameter import app_name, platform
from flask_login import LoginManager
from flask import Flask
# from flask_session import Session
from redis import from_url
from util.logger import log
from os import getenv
from secrets import token_hex

app = Flask(__name__, template_folder='templates', static_folder='static')

# Для куки нужен криптографический ключ
app.secret_key = getenv('SECRET_KEY', default=token_hex())

login_manager = LoginManager(app)
login_manager.login_view = 'login_page_get'
login_manager.login_message = "Необходимо зарегистрироваться в системе"
login_manager.login_message_category = "warning"

app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 36000

if platform!='unix':
    # app.config['SESSION_TYPE']  = 'filesystem'
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = from_url('redis://@192.168.20.33:6379')
else:
    # app.config['SESSION_TYPE']  = 'filesystem'
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = from_url('redis://@192.168.20.33:6379')

# Автоматическая регистрация точки входа
# app.add_url_rule('/login', 'login', ldap.login, methods=['GET', 'POST'])

log.info(f"__INIT__ for {app_name} started")

