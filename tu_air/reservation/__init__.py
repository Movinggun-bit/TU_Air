# TU_Air/tu_air/reservation/__init__.py
# (!!! 새 파일 !!!)

from flask import Blueprint

# 'reservation' 블루프린트 정의
reservation_bp = Blueprint('reservation', __name__, template_folder='../templates')

# reservation_views.py 파일을 임포트해서 라우트들을 등록합니다.
from . import reservation_views