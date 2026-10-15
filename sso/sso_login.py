from flask import session
from util.ip_addr import ip_addr
from util.logger import log, is_auto_refresh
from app_config import admin_post, work_post, view_post


def _roles_from_post(post: str, dep_name: str) -> set:
    """Переходный вывод роли по должности и департаменту (таблицы app_config).

    SSO роль пока не отдаёт: в ответе есть post, dep_name, ou_name и rfbn_id,
    поля roles нет. Как только оно появится, этот вывод и сами таблицы
    должностей уходят (этап 4 в ACCESS-PLAN.md). Роль одна - первая
    подошедшая, как было до перехода на множество.
    """
    for role, table in (('Admin', admin_post), ('Operator', work_post), ('Guest', view_post)):
        list_dep = table.get(post, [])
        if '*' in list_dep or dep_name in list_dep:
            return {role}
    return set()


class SSO_User:
    def init_user(self, info_user):
        self.ip = ip_addr()
        self.post=''
        self.dep_name=''
        self.ou_name=''
        self.rfbn_id=''
        # Роли - множество: проверка 'Admin' in roles на строке сравнивает
        # подстроку и при двух ролях соврёт.
        self.roles=set()

        if 'password' in session:
            self.password = session['password']
        #log.info(f'SSO. init_user. info_user: {info_user}')
        if info_user and 'login_name' in info_user:
            log.debug(f'SSO_USER. info_user: {info_user}')

            self.login_name = info_user['login_name']
            session['username'] = self.login_name
            # Required fields check
            if 'fio' not in info_user:
                log.info(f"---> SSO\n\tUSER {self.login_name} not Registred\n\tFIO is empty\n<---")
                return None

            if 'dep_name' not in info_user:
                log.info(f"---> SSO\n\tUSER {self.login_name} not Registred\n\tDEP_NAME is empty\n<---")
                return None
            if 'ou_name' not in info_user:
                log.info(f"---> SSO\n\tUSER {self.login_name} not Registred\n\tOU_NAME is empty\n<---")
                return None

            if 'post' not in info_user:
                log.info(f"---> SSO\n\tUSER {self.login_name} not Registred\n\tPOST in \n{info_user}\n\tis empty\n<---")
                return None

            # RFBN_ID
            self.rfbn_id=info_user.get('rfbn_id','')
            # dep_name
            self.dep_name = info_user.get('dep_name','')
            # ou_name
            self.ou_name = info_user.get('ou_name','')

            # Эту переменную выставлять нельзя, так как она будет перезаписывать 
            # используемую в приложении session['dep_name']
            # что приведет к ошеломляющим артефактам
            # session['dep_name']=self.dep_name

            # post
            self.post = info_user.get('post','')
            session['post']=self.post
            # Роль: из ответа SSO, если он её отдаёт, иначе переходно по должности
            roles = info_user.get('roles') or []
            if isinstance(roles, str):
                roles = [roles]
            self.roles = {str(role).strip() for role in roles if str(role).strip()}
            if not self.roles:
                self.roles = _roles_from_post(self.post, self.dep_name)
            if not self.roles:
                log.info(f'SSO. Undefined ROLE for: {self.login_name}')
                return None
            # Множество в сессию не уходит: она сериализуется в JSON
            session['roles'] = sorted(self.roles)

            # FIO
            self.fio = info_user.get('fio','')
            session['fio'] = self.fio
            #

            self.full_name = self.fio
            session['full_name'] = self.fio

            if not is_auto_refresh():
                log.info(f"--->\n\tSSO SUCCESS\n\tLOGIN_NAME:\t{self.login_name}\tFIO:\t  {self.fio}\n"
                f"\tROLES:\t\t{sorted(self.roles)}\tIP_ADDR:\t{self.ip}\tPOST:\t  {self.post}\n"
                f"\tRFBN:\t\t{self.rfbn_id}\tOU_NAME:\t{self.ou_name}\t\tDEP_NAME: {self.dep_name}\n<---")

            return self
        log.info(f"---> SSO FAIL. login_name: {info_user}\n\tip_addr: {self.ip}, password: {session.get('password', '')}\n<---")
        return None

    def have_role(self, role_name):
        if hasattr(self, 'roles'):
            return role_name in self.roles

    def is_authenticated(self):
        if not hasattr(self, 'login_name'):
            return False
        else:
            return True

    def is_active(self):
        if hasattr(self, 'login_name'):
            return True
        else:
            return False

    def is_anonymous(self):
        if not hasattr(self, 'login_name'):
            return True
        else:
            return False

    def get_id(self):
        log.debug(f'LDAP_User. GET_ID. self.id_addr: {self.ip}, self.login_name: {self.login_name}')
        if hasattr(self, 'login_name'):
            return self.login_name
        else: 
            return None


if __name__ == "__main__":
    #'bind_dn'       => 'cn=ldp,ou=admins,dc=gfss,dc=kz',
    #'bind_pass'     => 'hu89_fart7',    
    #connect_ldap('Гусейнов', '123')
    log.debug(f'__main__ function')
