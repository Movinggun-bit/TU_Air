# TU_Air/tu_air/staff/__init__.py

from flask import Blueprint

# 'staff' 블루프린트 정의
staff_bp = Blueprint('staff', __name__, template_folder='../templates', url_prefix='/staff')

# staff_views.py 파일을 임포트해서 라우트들을 등록합니다.
from . import staff_views

