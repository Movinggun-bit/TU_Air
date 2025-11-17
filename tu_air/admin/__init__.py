# TU_Air/tu_air/admin/__init__.py
# (!!! 새 파일 !!!)

from flask import Blueprint

admin_bp = Blueprint('admin', 
                     __name__, 
                     template_folder='../templates', 
                     static_folder='../static')

from . import admin_views