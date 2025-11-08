# tu_air/auth/auth_views.py
# (파일 전체를 덮어쓰세요)

from . import auth_bp
from ..extensions import db
from ..models import Member, Staff 
from flask import render_template, request, flash, redirect, url_for, session, g, jsonify # (!!! 1. jsonify 임포트)
import datetime 

@auth_bp.before_app_request
def load_logged_in_user():
    # ( ... 이전과 동일 ... )
    user_id = session.get('user_id')
    user_type = session.get('user_type') 
    g.user = None 
    if user_id is None:
        return 
    if user_type == 'member':
        g.user = Member.query.get(user_id)
    elif user_type == 'staff':
        g.user = Staff.query.get(user_id)
    if g.user is None:
        session.clear()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        login_type = request.form.get('login_type') 
        member_id = request.form.get('member_id')
        password = request.form.get('password')
        error = None

        next_url = None # (!!! 1. 로그인 후 이동할 URL 변수)

        if login_type == 'id':
            # --- 1. 회원 로그인 (평문 비교) ---
            user = Member.query.filter_by(Member_ID=member_id).first()
            if user is None or user.passwd != password: # (평문 비교)
                error = '아이디 또는 비밀번호가 올바르지 않습니다.'
            if error is None:
                session.clear()
                session['user_id'] = user.Member_ID
                session['user_type'] = 'member'
                # [!!!] (수정) 세션에 'pending_booking'이 있는지 확인 [!!!]
                if 'pending_booking' in session:
                    # (TODO: '/passenger_info' 페이지의 URL로 변경해야 함)
                    next_url = url_for('booking.passenger_info') # (임시)
                else:
                    next_url = url_for('main.home')
                
                return redirect(next_url)
        
        elif login_type == 'staff':
            # --- 2. 직원 로그인 (해시 비교) ---
            staff_user = Staff.query.filter_by(Staff_ID=member_id).first()
            if staff_user is None or staff_user.Passwd != password:
                error = '직원 아이디 또는 비밀번호가 올바르지 않습니다.'
            if error is None:
                session.clear()
                session['user_id'] = staff_user.Staff_ID
                session['user_type'] = 'staff' 
                return redirect(url_for('main.home'))
        
        flash(error)
        
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))

# [!!!] (신규) ID 중복 검사 AJAX 라우트 [!!!]
@auth_bp.route('/check_id', methods=['POST'])
def check_id():
    """ID 중복 검사를 위한 API 엔드포인트"""
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        
        if not member_id:
            return jsonify({'available': False, 'message': '아이디를 입력하세요.'}), 400

        # (Member 테이블과 Staff 테이블 모두에서 검색)
        exists_member = Member.query.filter_by(Member_ID=member_id).first()
        exists_staff = Staff.query.filter_by(Staff_ID=member_id).first()
        
        if exists_member or exists_staff:
            return jsonify({'available': False, 'message': '이미 사용 중인 아이디입니다.'})
        else:
            return jsonify({'available': True, 'message': '사용 가능한 아이디입니다.'})
            
    except Exception:
        return jsonify({'available': False, 'message': '서버 오류가 발생했습니다.'}), 500


# [!!!] 회원가입 로직 (생년월일 입력 방식 변경) [!!!]
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        # 1. 폼에서 값 가져오기
        member_id = request.form.get('member_id')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        name = request.form.get('name')
        surname_en = request.form.get('reg_surname_en')
        given_name_en = request.form.get('reg_given_name_en')
        nationality = request.form.get('nationality')
        # [!!!] (수정) 생년월일을 3개의 <select>에서 받음 [!!!]
        dob_year = request.form.get('dob_year')
        dob_month = request.form.get('dob_month')
        dob_day = request.form.get('dob_day')
        phone = request.form.get('phone')
        email = request.form.get('email')
        
        error = None

        # 2. 유효성 검사
        if not all([member_id, password, password_confirm, 
                    surname_en, given_name_en, 
                    name, nationality, dob_year, 
                    dob_month, dob_day, phone, email]):
            error = '모든 필드를 입력해야 합니다.'
        
        elif password != password_confirm:
            error = '비밀번호가 일치하지 않습니다.'
        
        else:
            # (서버 측 최종 중복 검사)
            existing_user = Member.query.filter_by(Member_ID=member_id).first()
            if existing_user:
                error = f"아이디 '{member_id}'는 이미 사용 중입니다."
            
            existing_email = Member.query.filter_by(Email=email).first()
            if existing_email:
                error = f"이메일 '{email}'는 이미 사용 중입니다."

            # [!!!] (수정) 생년월일 조합 [!!!]
            try:
                dob_date = datetime.date(int(dob_year), int(dob_month), int(dob_day))
            except ValueError:
                error = '생년월일이 올바르지 않습니다.'
                
        # 3. DB에 저장
        if error is None:
            try:
                full_name_en = f"{surname_en.upper()} {given_name_en.upper()}"

                new_user = Member(
                    Member_ID=member_id,
                    passwd=password, # (평문 저장)
                    Name=name,
                    eng_Name=full_name_en,
                    Nationality=nationality,
                    Date_OF_Birth=dob_date, # (조합된 날짜)
                    Phone=phone,
                    Email=email
                )
                db.session.add(new_user)
                db.session.commit()
                
                flash('회원가입에 성공했습니다. 로그인해 주세요.')
                return redirect(url_for('auth.login'))
            
            except Exception as e:
                db.session.rollback()
                error = f'데이터베이스 저장 중 오류가 발생했습니다: {e}'

        flash(error)

    return render_template('register.html')

# --- [!!! 2. '아이디 찾기' 라우트 추가 !!!] ---
@auth_bp.route('/find_id', methods=['GET', 'POST'])
def find_id():
    if g.user: # (로그인한 사용자는 접근 금지)
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        # 1. 폼에서 4개 정보 가져오기
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        
        dob_year = request.form.get('dob_year')
        dob_month = request.form.get('dob_month')
        dob_day = request.form.get('dob_day')
        
        try:
            # (생년월일 조합)
            dob_date = datetime.date(int(dob_year), int(dob_month), int(dob_day))
            
            # 2. DB에서 4개 정보가 모두 일치하는 회원 검색
            user = Member.query.filter_by(
                Name=name,
                Date_OF_Birth=dob_date,
                Phone=phone,
                Email=email
            ).first()

            if user:
                # 3. 찾았으면, 아이디를 템플릿에 전달
                return render_template('find_id.html', found_id=user.Member_ID)
            else:
                # 4. 못 찾았으면, 에러 메시지 전달
                return render_template('find_id.html', error='일치하는 회원 정보가 없습니다.')

        except Exception:
            return render_template('find_id.html', error='입력 정보가 올바르지 않습니다.')

    # GET 요청 시 폼 페이지 렌더링
    return render_template('find_id.html')

# --- [!!! 3. '비밀번호 찾기' 라우트 추가 !!!] ---
@auth_bp.route('/find_password', methods=['GET', 'POST'])
def find_password():
    if g.user:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        # 1. 폼에서 4개 정보 가져오기
        member_id = request.form.get('member_id')
        name = request.form.get('name')
        phone = request.form.get('phone')
        
        dob_year = request.form.get('dob_year')
        dob_month = request.form.get('dob_month')
        dob_day = request.form.get('dob_day')

        try:
            # (생년월일 조합)
            dob_date = datetime.date(int(dob_year), int(dob_month), int(dob_day))

            # 2. DB에서 4개 정보가 모두 일치하는 회원 검색
            user = Member.query.filter_by(
                Member_ID=member_id,
                Name=name,
                Date_OF_Birth=dob_date,
                Phone=phone
            ).first()

            if user:
                # 3. 찾았으면, (학습용) 평문 비밀번호를 템플릿에 전달
                return render_template('find_password.html', found_password=user.passwd)
            else:
                # 4. 못 찾았으면, 에러 메시지 전달
                return render_template('find_password.html', error='일치하는 회원 정보가 없습니다.')

        except Exception:
            return render_template('find_password.html', error='입력 정보가 올바르지 않습니다.')

    # GET 요청 시 폼 페이지 렌더링
    return render_template('find_password.html')