from typing import List, Any
import os.path
from flask import session
from gfss_parameter import BASE
from util.logger import log
from app_config import src_lang, language
from db.connect import get_connection


class I18N:
    file_names: List[Any] = []
    files: List[Any] = []
    objects: List[Any] = []

    def get_resource(self, lang, resource_name):
        if not resource_name:
            return ''

        file_object = ''
        return_value = ''
        file_name = f'{BASE}/i18n.{lang}'

        for i, f_name in enumerate(self.file_names):
            if f_name == file_name:
                file_object = self.objects[i]
                break

        if file_object == '' and os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                file_object = file.read()
                self.file_names.append(file_name)
                self.objects.append(file_object)

        if file_object:
            for line in file_object.splitlines():
                if line.startswith(resource_name + '='):
                    return_value = line.split('=', 1)[1]
                    break

        return return_value or resource_name

    def close(self):
        log.info("I18N. CLOSE")
        for file in self.files:
            file.close()
        self.file_names.clear()
        self.files.clear()
        self.objects.clear()


i18n = I18N()

def get_i18n_value(res_name):
    if 'language' in session:
        lang = session['language']
    else:
        lang = language
        session['language'] = language
    if src_lang == 'db':
        with get_connection().cursor() as cursor:
            return_value = cursor.callfunc("i18n.get_value", str, [lang, res_name])
    if src_lang == 'file':
        return_value = i18n.get_resource(lang, res_name)
    return return_value