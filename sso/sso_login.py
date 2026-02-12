from flask import session
from util.ip_addr import ip_addr
from util.logger import log
from app_config import admin_post, work_post, view_post

     
class SSO_User:
    def get_user_by_name(self, src_user):
        ip = ip_addr()
        self.src_user = src_user
        self.post=''
        self.dep_name=''
        self.roles=''
        self.top_control=0

        if 'password' in session:
            self.password = session['password']
        if src_user and 'login_name' in src_user:
            log.debug(f'SSO_USER. src_user: {src_user}')

            self.username = src_user['login_name']
            session['username'] = self.username
            # Required fields check
            if 'fio' not in src_user:
                log.info(f"---> SSO\n\tUSER {self.username} not Registred\n\tFIO is empty\n<---")
                return None

            if 'dep_name' not in src_user:
                log.info(f"---> SSO\n\tUSER {self.username} not Registred\n\tDEP_NAME is empty\n<---")
                return None

            if 'post' not in src_user:
                log.info(f"---> SSO\n\tUSER {self.username} not Registred\n\tPOST in \n{src_user}\n\tis empty\n<---")
                return None

            # RFBN_ID
            self.rfbn_id=src_user.get('rfbn_id','')
            # dep_name
            self.dep_name = src_user.get('dep_name','')

            # Эту переменную выставлять нельзя, так как она будет перезаписывать 
            # используемую в приложении session['dep_name']
            # что приведет к ошеломляющим артефактам
            # session['dep_name']=self.dep_name

            # post
            self.post = src_user.get('post','')
            session['post']=self.post
            # check admin right!
            list_admin_dep = admin_post.get(self.post,[])
            if self.dep_name in list_admin_dep:
                self.roles='Admin'
                self.top_control=2

            log.info(f'SSO. list_admin_dep: {list_admin_dep}. top_control: {self.top_control}')
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
                    log.info(f'SSO. Undefined ROLE for: {self.username}')
                    return None

            # FIO
            self.fio = src_user.get('fio','')
            session['fio'] = self.fio
            #

            if 'roles' in src_user:
                self.roles.append(src_user['roles'])
                session['roles']=self.roles
                
            session['top_control']=self.top_control

            self.full_name = self.fio
            session['full_name'] = self.fio

            self.ip_addr = ip
            log.info(f"--->\n\tSSO SUCCESS\n\tUSERNAME: {self.username}\n\tIP_ADDR: {self.ip_addr}\n\tFIO: {self.fio}\n\tROLES: {self.roles}, POST: {self.post}\n\tRFBN: {self.rfbn_id}\n\tDEP_NAME: {self.dep_name}\n<---")
            return self
        log.info(f"---> SSO FAIL. USERNAME: {src_user}\n\tip_addr: {ip}, password: {session['password']}\n<---")
        return None

    def have_role(self, role_name):
        if hasattr(self, 'roles'):
            return role_name in self.roles

    def is_authenticated(self):
        if not hasattr(self, 'username'):
            return False
        else:
            return True

    def is_active(self):
        if hasattr(self, 'username'):
            return True
        else:
            return False

    def is_anonymous(self):
        if not hasattr(self, 'username'):
            return True
        else:
            return False

    def get_id(self):
        log.debug(f'LDAP_User. GET_ID. self.src_user: {self.src_user}, self.username: {self.username}')
        if hasattr(self, 'src_user'):
            return self.src_user
        else: 
            return None


if __name__ == "__main__":
    #'bind_dn'       => 'cn=ldp,ou=admins,dc=gfss,dc=kz',
    #'bind_pass'     => 'hu89_fart7',    
    #connect_ldap('Гусейнов', '123')
    log.debug(f'__main__ function')
