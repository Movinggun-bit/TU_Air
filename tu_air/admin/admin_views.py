# TU_Air/tu_air/admin/admin_views.py
# (!!! 새 파일 !!!)

from . import admin_bp
from ..extensions import db
# (!!! 신규: 필요한 모든 모델 임포트 !!!)
from ..models import Aircraft, Airport, Flight, Flight_Price, Flight_Seat_Availability, Staff, Crew_Assignment
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
@staff_login_required
@role_required('Scheduler')
def schedule_dashboard():
    """ 항공편 및 직원 배정을 한 번에 처리하는 통합 뷰 """
    small_aircraft, medium_aircraft, large_aircraft = get_aircraft_data()

    if request.method == 'POST':
        # --- 1. 전체 항공편 생성 및 직원 배정 처리 ---
        if 'create_flight' in request.form:
            try:
                # 1-1. 항공편 정보 유효성 검사
                flight_data = {
                    'flight_no': request.form.get('flight_no'),
                    'aircraft_id': request.form.get('aircraft_id'),
                    'dep_airport': request.form.get('departure_airport'),
                    'arr_airport': request.form.get('arrival_airport'),
                    'dep_gate': request.form.get('dep_gate'),
                    'arr_gate': request.form.get('arr_gate'),
                    'dep_time': request.form.get('dep_time'),
                    'arr_time': request.form.get('arr_time'),
                    'price_econ': request.form.get('price_econ'),
                    'price_biz': request.form.get('price_biz'),
                    'price_first': request.form.get('price_first'),
                }
                always_required_keys = ['flight_no', 'aircraft_id', 'dep_airport', 'arr_airport', 'dep_gate', 'arr_gate', 'dep_time', 'arr_time', 'price_econ']
                if not all(flight_data.get(key) for key in always_required_keys):
                    raise ValueError("모든 항공편 필수 입력값을 채워주세요 (이코노미 가격 포함).")

                aircraft = Aircraft.query.get(flight_data['aircraft_id'])
                if not aircraft:
                    raise ValueError("선택된 항공기를 찾을 수 없습니다.")
                if aircraft.Seat_Capacity > 179 and not flight_data.get('price_biz'):
                    raise ValueError("중형 항공기 이상은 비즈니스 가격을 입력해야 합니다.")
                if aircraft.Seat_Capacity >= 300 and not flight_data.get('price_first'):
                    raise ValueError("대형 항공기는 퍼스트 가격을 입력해야 합니다.")
                if flight_data['dep_airport'] == flight_data['arr_airport']:
                    raise ValueError("출발지와 도착지는 같을 수 없습니다.")

                # 1-2. 직원 정보 유효성 검사
                staff_assignments = {
                    'captain': (request.form.get('captain'), 'Pilot'),
                    'co_pilot': (request.form.get('co_pilot'), 'Co-Pilot'),
                    'crew1': (request.form.get('crew1'), 'Cabin Crew'),
                    'crew2': (request.form.get('crew2'), 'Cabin Crew')
                }
                if not all(val[0] for val in staff_assignments.values()):
                    raise ValueError("모든 직책(기장, 부기장, 승무원 2명)에 직원을 배정해야 합니다.")

                staff_ids_to_assign = []
                for staff_key, (staff_id_str, required_role) in staff_assignments.items():
                    if not staff_id_str:
                        raise ValueError(f"{staff_key}에 대한 직원 정보가 비어있습니다.")
                    staff_id = staff_id_str.split()[0]
                    staff_member = Staff.query.get(staff_id)
                    if not staff_member:
                        raise ValueError(f"직원 ID '{staff_id}'를 찾을 수 없습니다.")
                    if staff_member.Role != required_role:
                        raise ValueError(f"직원 '{staff_id}'의 역할이 '{required_role}'(이)가 아닙니다. (현재 역할: {staff_member.Role})")
                    staff_ids_to_assign.append(staff_id)

                # 1-3. 데이터베이스 레코드 생성
                dep_time_obj = datetime.datetime.strptime(flight_data['dep_time'], '%Y-%m-%dT%H:%M:%S')
                id_timestamp = dep_time_obj.strftime('%y%m%d%H')
                new_flight_id = f"{flight_data['flight_no'].upper()}-{id_timestamp}"

                if Flight.query.get(new_flight_id):
                    raise Exception(f"오류: 항공편 ID '{new_flight_id}'가 이미 존재합니다.")

                new_flight = Flight(
                    Flight_ID=new_flight_id, Flight_No=flight_data['flight_no'].upper(), Aircraft_ID=flight_data['aircraft_id'],
                    Departure_Airport_Code=flight_data['dep_airport'], Departure_Time=dep_time_obj, Departure_Gate=flight_data['dep_gate'].upper(),
                    Arrival_Airport_Code=flight_data['arr_airport'], Arrival_Time=datetime.datetime.strptime(flight_data['arr_time'], '%Y-%m-%dT%H:%M:%S'),
                    Arrival_Gate=flight_data['arr_gate'].upper(), Flight_Status='On_Time'
                )
                db.session.add(new_flight)

                db.session.add(Flight_Price(Flight_ID=new_flight_id, Class='Economy', Price=flight_data['price_econ']))
                if aircraft.Seat_Capacity > 179 and flight_data['price_biz']:
                    db.session.add(Flight_Price(Flight_ID=new_flight_id, Class='Business', Price=flight_data['price_biz']))
                if aircraft.Seat_Capacity >= 300 and flight_data['price_first']:
                    db.session.add(Flight_Price(Flight_ID=new_flight_id, Class='First', Price=flight_data['price_first']))

                if not aircraft.seats:
                    raise Exception(f"항공기({aircraft.Aircraft_ID})의 좌석 정보를 찾을 수 없습니다.")
                for seat in aircraft.seats:
                    db.session.add(Flight_Seat_Availability(Flight_ID=new_flight_id, Seat_ID=seat.Seat_ID, Availability_Status='Available'))

                for staff_id in staff_ids_to_assign:
                    db.session.add(Crew_Assignment(Flight_ID=new_flight_id, Staff_ID=staff_id))
                
                db.session.commit()
                flash(f"항공편 [ {new_flight_id} ] 이(가) 성공적으로 편성되고 직원이 배정되었습니다.", "success")
                return redirect(url_for('admin.schedule_dashboard'))

            except (ValueError, Exception) as e:
                db.session.rollback()
                error_message = str(e)
                flash(f"오류: {error_message}", "error")
                # 폼 데이터를 다시 템플릿으로 전달하여 사용자가 다시 입력하지 않도록 함
                return render_template('admin_schedule.html',
                                       error_message=error_message,
                                       form_data=request.form,
                                       small_aircraft=small_aircraft,
                                       medium_aircraft=medium_aircraft,
                                       large_aircraft=large_aircraft)

        # --- 2. 항공기 선택 처리 ---
        elif 'selected_aircraft_id' in request.form:
            selected_aircraft_id = request.form.get('selected_aircraft_id')
            selected_aircraft = Aircraft.query.get(selected_aircraft_id)
            if not selected_aircraft:
                flash('선택한 항공기를 찾을 수 없습니다.', 'error')
            else:
                flash(f'선택된 항공기: {selected_aircraft.Model} ({selected_aircraft.Seat_Capacity}석) - ID: {selected_aircraft.Aircraft_ID}', 'success')
                return render_template('admin_schedule.html',
                                       form_data={},
                                       selected_aircraft_id=selected_aircraft_id,
                                       selected_aircraft_capacity=selected_aircraft.Seat_Capacity,
                                       small_aircraft=small_aircraft,
                                       medium_aircraft=medium_aircraft,
                                       large_aircraft=large_aircraft)

    # --- 3. GET 요청 처리 ---
    return render_template('admin_schedule.html',
                           form_data={},
                           small_aircraft=small_aircraft,
                           medium_aircraft=medium_aircraft,
                           large_aircraft=large_aircraft)


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

@admin_bp.route('/pilot_selection')
@staff_login_required
@role_required('Scheduler')
def pilot_selection():
    """기장 선택 화면"""
    target = request.args.get('target')
    pilots = Staff.query.filter_by(Role='Pilot').all()
    return render_template('Pilot_selection.html', staffs=pilots, title='기장', target=target)

@admin_bp.route('/co_pilot_selection')
@staff_login_required
@role_required('Scheduler')
def co_pilot_selection():
    """부기장 선택 화면"""
    target = request.args.get('target')
    co_pilots = Staff.query.filter_by(Role='Co-Pilot').all()
    return render_template('Co-Pilot_selection.html', staffs=co_pilots, title='부기장', target=target)

@admin_bp.route('/cabin_crew_selection')
@staff_login_required
@role_required('Scheduler')
def cabin_crew_selection():
    """승무원 선택 화면"""
    target = request.args.get('target')
    cabin_crews = Staff.query.filter_by(Role='Cabin Crew').all()
    return render_template('Cabin_Crew_selection.html', staffs=cabin_crews, title='승무원', target=target)

@admin_bp.route('/staff_schedule/<staff_id>')
@staff_login_required
@role_required('Scheduler')
def staff_schedule(staff_id):
    """ 특정 직원의 1년 이내 일정 표시 """
    staff = Staff.query.get_or_404(staff_id)
    
    today = datetime.date.today()
    next_year = today + datetime.timedelta(days=365)

    assignments = db.session.query(Flight).join(Crew_Assignment).filter(
        Crew_Assignment.Staff_ID == staff_id,
        Flight.Departure_Time >= today,
        Flight.Departure_Time <= next_year
    ).order_by(Flight.Departure_Time).all()

    schedule = {}
    for flight in assignments:
        month = flight.Departure_Time.strftime('%Y-%m')
        day = flight.Departure_Time.strftime('%Y-%m-%d')
        if month not in schedule:
            schedule[month] = {}
        if day not in schedule[month]:
            schedule[month][day] = []
        schedule[month][day].append(flight)

    template_map = {
        'Pilot': 'Pilot_schedule.html',
        'Co-Pilot': 'Co-Pilot_schedule.html',
        'Cabin Crew': 'Cabin_Crew_schedule.html'
    }
    template = template_map.get(staff.Role)
    if not template:
        flash(f"'{staff.Role}' 역할에 대한 스케줄 템플릿이 없습니다.", "error")
        return redirect(url_for('admin.index'))

    return render_template(template, staff=staff, schedule=schedule)