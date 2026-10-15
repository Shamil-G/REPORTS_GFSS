from flask import session
from util.ip_addr import ip_addr
from util.logger import log, is_auto_refresh
from app_config import admin_post

ROLE_ADMIN = 'Admin'
ROLE_USER = 'User'


def local_role(post: str, ou_name: str, dep_name: str) -> str:
    """Роль заполняется локально: Admin или User.

    SSO роль не отдаёт - у него другая функция, он отвечает за то, кто вошёл
    (должность, подразделение, область). Admin - если должность и
    подразделение есть в `admin_post` (app_config), иначе User.

    Подразделение сравнивается и с коротким именем из AD (`ou_name`), и с
    полным названием департамента (`dep_name`): в списке допустимо любое из
    двух, чтобы короткие имена не приходилось угадывать.
    """
    places = admin_post.get(post, [])
    if '*' in places or ou_name in places or dep_name in places:
        return ROLE_ADMIN
    return ROLE_USER


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
            # Роль заполняется локально, из списка в app_config
            self.roles = {local_role(self.post, self.ou_name, self.dep_name)}
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
