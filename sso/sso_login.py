from flask import session
from util.ip_addr import ip_addr
from util.logger import log
from app_config import admin_post, work_post, view_post

     
class SSO_User:
    def init_user(self, info_user):
        self.ip = ip_addr()
        self.post=''
        self.dep_name=''
        self.roles=''
        self.top_control=0

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

            if 'post' not in info_user:
                log.info(f"---> SSO\n\tUSER {self.login_name} not Registred\n\tPOST in \n{info_user}\n\tis empty\n<---")
                return None

            # RFBN_ID
            self.rfbn_id=info_user.get('rfbn_id','')
            # dep_name
            self.dep_name = info_user.get('dep_name','')

            # Эту переменную выставлять нельзя, так как она будет перезаписывать 
            # используемую в приложении session['dep_name']
            # что приведет к ошеломляющим артефактам
            # session['dep_name']=self.dep_name

            # post
            self.post = info_user.get('post','')
            session['post']=self.post
            # check admin right!
            list_admin_dep = admin_post.get(self.post,[])
            if self.dep_name in list_admin_dep:
                self.roles='Admin'
                self.top_control=2

            log.debug(f'SSO. list_admin_dep: {list_admin_dep}. top_control: {self.top_control}')
            # check user right
            if self.top_control==0:
                list_work_dep = work_post.get(self.post,[])
                if '*' in list_work_dep or self.dep_name in list_work_dep:
                    self.roles='Operator'
                    self.top_control=1

            # check user right
            if self.top_control==0:
                list_view_dep = view_post.get(self.post,[])
                if '*' in list_view_dep or self.dep_name in list_view_dep:
                    self.roles='Guest'
                else:
                    log.info(f'SSO. Undefined ROLE for: {self.login_name}')
                    return None

            # FIO
            self.fio = info_user.get('fio','')
            session['fio'] = self.fio
            #

            if 'roles' in info_user:
                self.roles.append(info_user['roles'])
                session['roles']=self.roles
                
            session['top_control']=self.top_control

            self.full_name = self.fio
            session['full_name'] = self.fio

            log.info(f"--->\n\tSSO SUCCESS\n\tTOP_CONTROL:\t{self.top_control}\tLOGIN_NAME:\t{self.login_name}\tFIO:\t  {self.fio}\n"
            f"\tROLES:\t\t{self.roles}\tIP_ADDR:\t{self.ip}\tPOST:\t  {self.post}\n"
            f"\tRFBN:\t\t{self.rfbn_id}\tDEP_NAME:\t{self.dep_name}\n<---")

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
