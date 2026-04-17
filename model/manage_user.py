from app_config import URL_LOGIN
# from gfss_parameter import public_name
from main_app import log
import requests


def get_user_roles(public_name, username, ip):
    request_json = { "app_name": public_name, "username": username, "ip_addr": ip }
    url = f'{URL_LOGIN}/get-roles'
    try:
        resp = requests.post(url, json=request_json)
        status = resp.status_code
        if status == 200:
            log.debug(f'-----> GET USER ROLES. resp: {resp}, status: {status}, request_json: {request_json}')
            resp_json = resp.json()
        else:
            log.error(f'\nERROR GET USER ROLES. "username": {username}, URL: {url}, status: {status}')
            resp_json = {"status": 'ERROR', "username": username, "roles": [], "mess": f'RESP STATUS: {status}'}
    except requests.exceptions.HTTPError as errH:
        log.error(f"=====> Http Error. request get-roles. username: {username} : {errH}")
        resp_json = {"mistake": f'{errH}', "username": username, "roles": []}
    except requests.exceptions.Timeout as errT:
        log.error(f'=====> TIMEOUT ERROR. request get-roles. username: {username} : {errT}')
        resp_json = {"mistake": f'{errT}', "username": username, "roles": []}
    except requests.exceptions.TooManyRedirects as errM:
        log.error(f'=====> ERROR MANY REDIRECT. request get-roles. username: {username} : {errM}')
        resp_json = {"mistake": f'{errM}', "username": username, "roles": []}
    except requests.exceptions.ConnectionError as errC:
        log.error(f'=====> ERROR CONNECTION. request get-roles. username: {username} : {errC}')
        resp_json = {"mistake": f'{errC}', "username": username, "roles": []}
    except requests.exceptions.RequestException as errE:
        log.error(f'=====> REQUEST ERROR. request get-roles. username: {username} : {errE}')
        resp_json = {"mistake": f'{errE}', "username": username, "roles": []}
    except Exception as e:
        log.error(f'---> GET USER ROLES. URL: {url}, ERROR: {e}')
        resp_json = {"mistake": f'{e}', "username": username, "roles": []}
    finally:
        log.info(f"GET ROLES. FINALLY. USERNAME: {username}, resp_json: {resp_json}")
    return resp_json



def server_logout(id_user):
    request_json = { "id_user": id_user}
    url = f'{URL_LOGIN}/user-logout'
    try:
        resp = requests.post(url, json=request_json)
        status = resp.status_code
        if status == 200:
            log.debug(f'-----> USER LOGOUT. resp: {resp}, status: {status}, request_json: {request_json}')
            resp_json = resp.json()
        else:
            log.error(f'\nERROR GET USER INFO. "id_user": {id_user}, URL: {url}, status: {status}')
            resp_json = {"mistake": 'ERROR', "id_user": {id_user}, "mess": f'RESP STATUS: {status}'}
    except requests.exceptions.HTTPError as errH:
        log.error(f"=====> Http Error. request user-info. id_user: {id_user} : {errH}")
        resp_json = {"mistake": f'{errH}', "id_user": {id_user}, "roles": []}
    except requests.exceptions.Timeout as errT:
        log.error(f'=====> TIMEOUT ERROR. request user-info. "id_user": {id_user} : {errT}')
        resp_json = {"mistake": f'{errT}', "id_user": {id_user}, "roles": []}
    except requests.exceptions.TooManyRedirects as errM:
        log.error(f'=====> ERROR MANY REDIRECT. request user-info. "id_user": {id_user} : {errM}')
        resp_json = {"mistake": f'{errM}', "id_user": {id_user}, "roles": []}
    except requests.exceptions.ConnectionError as errC:
        log.error(f'=====> ERROR CONNECTION. request user-info. "id_user": {id_user} : {errC}')
        resp_json = {"mistake": f'{errC}', "id_user": {id_user}, "roles": []}
    except requests.exceptions.RequestException as errE:
        log.error(f'=====> REQUEST ERROR. request user-info. "id_user": {id_user} : {errE}')
        resp_json = {"mistake": f'{errE}', "id_user": {id_user}, "roles": []}
    except Exception as e:
        log.error(f'=====> ERROR. request user-info. URL: {url}, ERROR: {e}')
        resp_json = {"mistake": f'{e}', "id_user": {id_user}, "roles": []}
    finally:
        log.debug(f"REQUEST USER INFO. FINALLY. id_user: {id_user}, resp_json: {resp_json}")
    return resp_json

def user_info(public_name, username):
    request_json = { "app_name": public_name, "username": username }
    url = f'{URL_LOGIN}/user-info'
    try:
        resp = requests.post(url, json=request_json)
        status = resp.status_code
        if status == 200:
            log.debug(f'-----> GET CHANGE PASSWORD. resp: {resp}, status: {status}, request_json: {request_json}')
            resp_json = resp.json()
        else:
            log.error(f'\nERROR GET USER INFO. "username": {username}, URL: {url}, status: {status}')
            resp_json = {"mistake": 'ERROR', "username": username, "mess": f'RESP STATUS: {status}'}
    except requests.exceptions.HTTPError as errH:
        log.error(f"=====> Http Error. request user-info. username: {username} : {errH}")
        resp_json = {"mistake": f'{errH}', "username": username, "roles": []}
    except requests.exceptions.Timeout as errT:
        log.error(f'=====> TIMEOUT ERROR. request user-info. username: {username} : {errT}')
        resp_json = {"mistake": f'{errT}', "username": username, "roles": []}
    except requests.exceptions.TooManyRedirects as errM:
        log.error(f'=====> ERROR MANY REDIRECT. request user-info. username: {username} : {errM}')
        resp_json = {"mistake": f'{errM}', "username": username, "roles": []}
    except requests.exceptions.ConnectionError as errC:
        log.error(f'=====> ERROR CONNECTION. request user-info. username: {username} : {errC}')
        resp_json = {"mistake": f'{errC}', "username": username, "roles": []}
    except requests.exceptions.RequestException as errE:
        log.error(f'=====> REQUEST ERROR. request user-info. username: {username} : {errE}')
        resp_json = {"mistake": f'{errE}', "username": username, "roles": []}
    except Exception as e:
        log.error(f'=====> ERROR. request user-info. URL: {url}, ERROR: {e}')
        resp_json = {"mistake": f'{e}', "username": username, "roles": []}
    finally:
        log.info(f"REQUEST USER INFO. FINALLY. USERNAME: {username}, resp_json: {resp_json}")
    return resp_json
