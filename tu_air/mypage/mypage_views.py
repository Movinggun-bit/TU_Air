# TU_Air/tu_air/mypage/mypage_views.py
# (!!! 새 파일 !!!)

from . import mypage_bp
from ..extensions import db
from ..models import Member, Booking, Payment, Passenger, Boarding_Pass
from flask import render_template, request, flash, redirect, url_for, session, g
from functools import wraps

# --- (1) 로그인 필수 데코레이터 ---
# 마이페이지의 모든 라우트는 '회원' 로그인이 필수이므로,
# g.user가 없거나 'member'가 아니면 로그인 페이지로 보냅니다.
def member_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None or session.get('user_type') != 'member':
            flash('로그인이 필요한 서비스입니다.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- (2) 마이페이지 메인 (정보 + 예약/결제/탑승권 조회) ---
@mypage_bp.route('/mypage')
@member_login_required
def mypage():
    # [!!!] (R2) (수정) 예약을 '진행 중'과 '취소'로 분리하여 조회 [!!!]
    
    # 1. 진행 중인 예약 (Reserved, Check-In)
    active_bookings = Booking.query.filter(
        Booking.Member_ID == g.user.Member_ID,
        Booking.Status.in_(['Reserved', 'Check-In'])
    ).order_by(Booking.Booking_Date.desc()).all()

    # 2. 취소된 예약 (Canceled, Partial_Canceled)
    canceled_bookings = Booking.query.filter(
        Booking.Member_ID == g.user.Member_ID,
        Booking.Status.in_(['Canceled', 'Partial_Canceled'])
    ).order_by(Booking.Booking_Date.desc()).all()

    return render_template('mypage.html', 
                           user=g.user, 
                           bookings=active_bookings, # (기존 'bookings' 변수에는 활성 예약 전달)
                           canceled_bookings=canceled_bookings) # (새 변수 전달)

# --- (3) 회원 정보 수정 (POST) ---
@mypage_bp.route('/mypage/update_info', methods=['POST'])
@member_login_required
def update_info():
    # 1. 폼에서 수정할 데이터 받기
    phone = request.form.get('phone')
    email = request.form.get('email')
    nationality = request.form.get('nationality')
    
    # 2. DB에서 현재 사용자 정보 다시 가져오기
    user_to_update = Member.query.get(g.user.Member_ID)
    
    if user_to_update:
        # 3. 정보 업데이트
        user_to_update.Phone = phone
        user_to_update.Email = email
        user_to_update.Nationality = nationality
        
        try:
            db.session.commit()
            flash('회원 정보가 성공적으로 수정되었습니다.')
        except Exception as e:
            db.session.rollback()
            flash(f'정보 수정 중 오류가 발생했습니다: {e}')
    
    return redirect(url_for('mypage.mypage'))

# --- (4) 비밀번호 변경 (POST) ---
@mypage_bp.route('/mypage/update_password', methods=['POST'])
@member_login_required
def update_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('new_password_confirm')
    
    user_to_update = Member.query.get(g.user.Member_ID)
    
    # [!!!] 학습용: 평문 비밀번호 비교 [!!!]
    # (경고: 실제 서비스에서는 절대 사용 금지)
    if user_to_update.passwd != current_password:
        flash('현재 비밀번호가 일치하지 않습니다.')
    elif new_password != confirm_password:
        flash('새 비밀번호와 확인 비밀번호가 일치하지 않습니다.')
    elif len(new_password) > 20:
        flash('새 비밀번호는 20자 이내여야 합니다.')
    else:
        # [!!!] 학습용: 평문 비밀번호 저장 [!!!]
        user_to_update.passwd = new_password
        try:
            db.session.commit()
            flash('비밀번호가 성공적으로 변경되었습니다.')
        except Exception as e:
            db.session.rollback()
            flash(f'비밀번호 변경 중 오류가 발생했습니다: {e}')
            
    return redirect(url_for('mypage.mypage'))