# TU_Air/tu_air/admin/admin_views.py
# (!!! 새 파일 !!!)

from . import admin_bp
from ..extensions import db
# (!!! 신규: 필요한 모든 모델 임포트 !!!)
from ..models import Aircraft, Airport, Flight, Flight_Price, Flight_Seat_Availability
from flask import render_template, redirect, url_for, session, g, flash, request
from functools import wraps
import datetime

# (1. 직원 로그인 여부를 확인하는 데코레이터)
def staff_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # (세션에 'user_type'이 없거나 'staff'가 아니면)
        if g.user is None or session.get('user_type') != 'staff':
            flash('직원 계정으로 로그인이 필요합니다.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# (2. 특정 역할을 확인하는 데코레이터)
def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user.Role != role_name:
                flash(f"'{role_name}' 권한이 없습니다.")
                return redirect(url_for('main.home')) # (권한 없으면 홈으로)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# [!!!] (신규) 1. 관리자(직원) 홈 - 새로운 '문지기' [!!!]
@admin_bp.route('/')
@staff_login_required # (직원만 접근 가능)
def index():
    """ 모든 직원의 로그인 랜딩 페이지 """
    
    # (V86의 '문지기' 로직을 여기로 이동)
    if g.user.Role == 'Scheduler':
        return redirect(url_for('admin.schedule_dashboard'))
    
    # (TODO: 'Pilot'이나 'HR' 등 다른 역할(Role)에 따른 분기)
    # elif g.user.Role == 'Pilot':
    #     return redirect(url_for('admin.flight_briefing'))
    
    # (기본 관리자 홈)
    return render_template('admin_index.html')

# [!!!] (R2) 'Scheduler'를 위한 항공편 편성 뷰 [!!!]
@admin_bp.route('/schedule', methods=['GET', 'POST'])
@staff_login_required  # (1. 스태프인가?)
@role_required('Scheduler') # (2. 스태프 중 'Scheduler'인가?)
def schedule_dashboard():
    """ 항공편 편성 화면 """
    try:
        # 항공기 데이터 초기화
        small_aircraft, medium_aircraft, large_aircraft = get_aircraft_data()

        if request.method == 'POST':
            # 선택된 항공기 처리
            selected_aircraft_id = request.form.get('selected_aircraft_id')
            if selected_aircraft_id:
                selected_aircraft = Aircraft.query.get(selected_aircraft_id)
                if not selected_aircraft:
                    flash('선택한 항공기를 찾을 수 없습니다.', 'error')
                else:
                    flash(f'선택된 항공기: {selected_aircraft.Model} ({selected_aircraft.Seat_Capacity}석) - ID: {selected_aircraft.Aircraft_ID}', 'success')
                    return render_template('admin_schedule.html',
                                           selected_aircraft_id=selected_aircraft_id,
                                           selected_aircraft_capacity=selected_aircraft.Seat_Capacity,
                                           small_aircraft=small_aircraft,
                                           medium_aircraft=medium_aircraft,
                                           large_aircraft=large_aircraft)

            # 항공편 편성 처리
            flight_no = request.form.get('flight_no')
            aircraft_id = request.form.get('aircraft_id')
            dep_airport = request.form.get('dep_airport')
            arr_airport = request.form.get('arr_airport')
            dep_gate = request.form.get('dep_gate')
            arr_gate = request.form.get('arr_gate')
            dep_time_str = request.form.get('dep_time')
            arr_time_str = request.form.get('arr_time')
            price_econ = request.form.get('price_econ')
            price_biz = request.form.get('price_biz')
            price_first = request.form.get('price_first')

            # 입력값 검증
            if not all([flight_no, aircraft_id, dep_airport, arr_airport, dep_gate, arr_gate, dep_time_str, arr_time_str]):
                raise ValueError("모든 필수 입력값을 채워주세요.")

            # 항공기 정보 조회
            aircraft = Aircraft.query.get(aircraft_id)
            if not aircraft:
                raise ValueError("항공기를 찾을 수 없습니다.")
            
            # 항공기 크기에 따른 가격 검증
            if not price_econ:
                raise ValueError("이코노미 가격은 필수입니다.")
            
            if aircraft.Seat_Capacity > 179:  # 중형 이상
                if not price_biz:
                    raise ValueError("비즈니스 가격을 입력해주세요.")
            
            if aircraft.Seat_Capacity >= 300:  # 대형
                if not price_first:
                    raise ValueError("퍼스트 가격을 입력해주세요.")

            # (2. 데이터 변환 및 검증)
            dep_time_obj = datetime.datetime.strptime(dep_time_str, '%Y-%m-%dT%H:%M')
            arr_time_obj = datetime.datetime.strptime(arr_time_str, '%Y-%m-%dT%H:%M')

            if dep_airport == arr_airport:
                raise ValueError("출발지와 도착지는 같을 수 없습니다.")

            # (R) Flight_ID 생성 규칙: [Flight_No]-[YYMMDDHH]
            id_timestamp = dep_time_obj.strftime('%y%m%d%H')
            new_flight_id = f"{flight_no.upper()}-{id_timestamp}"

            # (3. 유효성 검사)
            if dep_airport == arr_airport:
                raise Exception("출발지와 도착지는 같을 수 없습니다.")
            
            # (R) 중복 검사
            existing_flight = Flight.query.get(new_flight_id)
            if existing_flight:
                raise Exception(f"오류: 항공편 ID '{new_flight_id}'가 이미 존재합니다.")

            # (4. DB 트랜잭션 시작)
            
            # (4a. Flight 테이블)
            new_flight = Flight(
                Flight_ID=new_flight_id,
                Flight_No=flight_no.upper(),
                Aircraft_ID=aircraft_id,
                Departure_Airport_Code=dep_airport,
                Departure_Time=dep_time_obj,
                Departure_Gate=dep_gate.upper(),
                Arrival_Airport_Code=arr_airport,
                Arrival_Time=arr_time_obj,
                Arrival_Gate=arr_gate.upper(),
                Flight_Status='On_Time'
            )
            db.session.add(new_flight)
            
            # (4b. Flight_Price 테이블) - 항공기 크기에 따라 가격 추가
            db.session.add(Flight_Price(Flight_ID=new_flight_id, Class='Economy', Price=price_econ))
            
            if aircraft.Seat_Capacity > 179:  # 중형 이상
                db.session.add(Flight_Price(Flight_ID=new_flight_id, Class='Business', Price=price_biz))
            
            if aircraft.Seat_Capacity >= 300:  # 대형
                db.session.add(Flight_Price(Flight_ID=new_flight_id, Class='First', Price=price_first))
            
            # (4c. Flight_Seat_Availability 테이블)
            if not aircraft.seats:
                raise Exception(f"항공기({aircraft_id})의 좌석 정보를 찾을 수 없습니다.")
                
            for seat in aircraft.seats:
                fsa = Flight_Seat_Availability(
                    Flight_ID=new_flight_id, 
                    Seat_ID=seat.Seat_ID, 
                    Availability_Status='Available'
                )
                db.session.add(fsa)

            # (5. 커밋)
            db.session.commit()
            flash(f"항공편 [ {new_flight_id} ] 이(가) 성공적으로 편성되었습니다.", "success")

        return render_template('admin_schedule.html',
                               small_aircraft=small_aircraft,
                               medium_aircraft=medium_aircraft,
                               large_aircraft=large_aircraft)

    except ValueError as ve:
        flash(f"입력 오류: {ve}", "error")
        return redirect(url_for('admin.schedule_dashboard'))

    except Exception as e:
        # 예외를 로깅하고 사용자에게 오류 메시지 표시
        print(f"서버 오류: {e}")
        flash("서버에서 오류가 발생했습니다. 관리자에게 문의하세요.", "error")
        return redirect(url_for('admin.schedule_dashboard'))

# [!!!] (신규) 2. 항공기 선택 화면 [!!!]
@admin_bp.route('/aircraft_selection')
@staff_login_required
@role_required('Scheduler')
def aircraft_selection():
    """항공기 선택 화면"""
    all_aircraft = Aircraft.query.order_by(Aircraft.Model).all()
    small_aircraft = [a for a in all_aircraft if a.Seat_Capacity <= 179]
    medium_aircraft = [a for a in all_aircraft if 180 <= a.Seat_Capacity <= 299]
    large_aircraft = [a for a in all_aircraft if a.Seat_Capacity >= 300]

    return render_template('aircraft_selection.html',
                           small_aircraft=small_aircraft,
                           medium_aircraft=medium_aircraft,
                           large_aircraft=large_aircraft)

# 선택된 항공기 처리
    selected_aircraft_id = request.form.get('selected_aircraft_id')
    if selected_aircraft_id:
        selected_aircraft = Aircraft.query.get(selected_aircraft_id)
        if not selected_aircraft:
            flash('선택한 항공기를 찾을 수 없습니다.', 'error')
        else:
            flash(f'선택된 항공기: {selected_aircraft.Model} ({selected_aircraft.Seat_Capacity}석) - ID: {selected_aircraft.Aircraft_ID}', 'success')

# [!!!] (신규) 3. 특정 항공기의 일정 조회 [!!!]
@admin_bp.route('/aircraft_schedule/<aircraft_id>')
@staff_login_required
@role_required('Scheduler')
def aircraft_schedule(aircraft_id):
    """ 특정 항공기의 1년 이내 일정 표시 """
    aircraft = Aircraft.query.get(aircraft_id)
    if not aircraft:
        flash('항공기를 찾을 수 없습니다.', 'error')
        return redirect(url_for('admin.aircraft_selection'))

    # 현재 날짜부터 1년 이내의 일정 조회
    today = datetime.date.today()
    next_year = today + datetime.timedelta(days=365)
    flights = Flight.query.filter(
        Flight.Aircraft_ID == aircraft_id,
        Flight.Departure_Time.isnot(None),  # 출발 시간이 None이 아닌 경우만 필터링
        Flight.Departure_Time >= today,
        Flight.Departure_Time <= next_year
    ).order_by(Flight.Departure_Time).all()

    if not flights:
        return render_template('aircraft_schedule.html', aircraft=aircraft, schedule={})

    # 월별, 날짜별로 그룹화
    schedule = {}
    for flight in flights:
        month = flight.Departure_Time.strftime('%Y-%m')
        day = flight.Departure_Time.strftime('%Y-%m-%d')
        if month not in schedule:
            schedule[month] = {}
        if day not in schedule[month]:
            schedule[month][day] = []
        schedule[month][day].append(flight)

    return render_template('aircraft_schedule.html', aircraft=aircraft, schedule=schedule)

def get_aircraft_data():
    """항공기 데이터를 초기화하는 함수"""
    all_aircraft = Aircraft.query.order_by(Aircraft.Model).all()
    small_aircraft = [a for a in all_aircraft if a.Seat_Capacity <= 179]
    medium_aircraft = [a for a in all_aircraft if 180 <= a.Seat_Capacity <= 299]
    large_aircraft = [a for a in all_aircraft if a.Seat_Capacity >= 300]
    return small_aircraft, medium_aircraft, large_aircraft