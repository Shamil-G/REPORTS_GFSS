rem python -m venv venv
rem . /home/reports/REPORTS_GFSS/venv/bin/activate
call C:\Projects\REPORTS_GFSS\venv\Scripts\activate.bat

python -m pip install --upgrade pip
rem pip install oracledb
rem pip install flask
rem pip install flask_login
rem pip install redis
rem pip install flask_session
rem pip install openpyxl
rem pip install requests
rem pip install ldap3
rem pip freeze > requirements.txt
pip install dotenv
python main_app.py
rem gunicorn
