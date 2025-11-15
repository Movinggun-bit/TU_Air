# TU_Air/tu_air/__init__.py
# (create_app 함수 수정)

from flask import Flask
from config import Config
from .extensions import db

def create_app(config_class=Config):
    app = Flask(__name__)
    
    # 1. 설정 로드
    app.config.from_object(config_class)
    
    # 2. db 객체를 app과 연결 (초기화)
    db.init_app(app)

    # 3. 블루프린트 등록 및 모델 임포트
    with app.app_context():
        # (!!! 1. 모델 임포트 추가 !!!)
        #     (DB 테이블을 생성하거나 앱이 모델을 인식하도록 함)
        from . import models 
    
        from .main import main_views
        from . import auth
        from . import mypage
        from . import booking
        from . import reservation
        from . import checkin
        from . import staff
        
        app.register_blueprint(main_views.main_bp)
        app.register_blueprint(auth.auth_bp, url_prefix='/auth')
        app.register_blueprint(mypage.mypage_bp)
        app.register_blueprint(booking.booking_bp, url_prefix='/booking')
        app.register_blueprint(reservation.reservation_bp, url_prefix='/reservation')
        app.register_blueprint(checkin.checkin_bp, url_prefix='/checkin')
        app.register_blueprint(staff.staff_bp)
        
    return app