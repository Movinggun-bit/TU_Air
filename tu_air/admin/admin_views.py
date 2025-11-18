# TU_Air/tu_air/admin/admin_views.py
# (!!! 새 파일 !!!)

from . import admin_bp
from ..extensions import db
# (!!! 신규: 필요한 모든 모델 임포트 !!!)
from ..models import Aircraft, Airport, Flight, Flight_Price, Flight_Seat_Availability, Staff, Crew_Assignment, Booking, Passenger, Boarding_Pass, Passenger, Boarding_Pass, Maintenance_Record, Member
from flask import render_template, redirect, url_for, session, g, flash, request
from functools import wraps
import datetime
from sqlalchemy import or_, and_

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
    # --- [이 부분을 추가하세요] ---
    elif g.user.Role == 'Engineer':
        return redirect(url_for('admin.maintenance_dashboard'))

    elif g.user.Role == 'HR':
        return redirect(url_for('admin.hr_dashboard'))

    # --- [이 부분을 추가하세요] ---
    elif g.user.Role in ['Pilot', 'Co-Pilot', 'Cabin Crew']:
        return redirect(url_for('admin.my_schedule'))
    # --- [여기까지] ---
    
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

@admin_bp.route('/delay_flight', methods=['POST'])
@staff_login_required
@role_required('Scheduler')
def delay_flight():
    """ 항공편 지연 정보를 업데이트합니다. """
    flight_id = request.form.get('flight_id')
    new_departure_time_str = request.form.get('new_departure_time')
    new_arrival_time_str = request.form.get('new_arrival_time')
    delay_reason = request.form.get('delay_reason')

    if not all([flight_id, new_departure_time_str, new_arrival_time_str, delay_reason]):
        flash('모든 지연 정보를 입력해야 합니다.', 'error')
        return redirect(url_for('admin.flight_management'))

    try:
        new_departure_time = datetime.datetime.strptime(new_departure_time_str, '%Y-%m-%dT%H:%M')
        new_arrival_time = datetime.datetime.strptime(new_arrival_time_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('날짜/시간 형식이 올바르지 않습니다.', 'error')
        return redirect(url_for('admin.flight_management'))

    flight = Flight.query.get(flight_id)
    if not flight:
        flash('해당 항공편을 찾을 수 없습니다.', 'error')
        return redirect(url_for('admin.flight_management'))

    try:
        flight.Departure_Time = new_departure_time
        flight.Arrival_Time = new_arrival_time
        flight.Flight_Status = 'Delayed'
        flight.Status_Reason = delay_reason
        db.session.commit()
        flash(f"항공편 {flight_id}의 지연 정보가 성공적으로 업데이트되었습니다.", 'success')
    except Exception as e:
        db.session.rollback()
    return redirect(url_for('admin.flight_management'))

@admin_bp.route('/cancel_flight', methods=['POST'])
@staff_login_required
@role_required('Scheduler')
def cancel_flight():
    """ 항공편을 취소하고 관련 예약 및 데이터를 처리합니다. """
    flight_id = request.form.get('flight_id')
    cancellation_reason = request.form.get('cancel_reason')

    if not all([flight_id, cancellation_reason]):
        flash('항공편 ID와 취소 사유를 모두 입력해야 합니다.', 'error')
        return redirect(url_for('admin.flight_management'))

    try:
        flight = Flight.query.get(flight_id)
        if not flight:
            flash('해당 항공편을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.flight_management'))

        # 1. 항공편 상태 업데이트
        flight.Flight_Status = 'Canceled'
        flight.Status_Reason = cancellation_reason

        # 2. 관련 예약 처리 (사용자 취소 로직과 유사하게)
        # 해당 항공편을 outbound 또는 return으로 포함하는 모든 예약 조회
        bookings_to_cancel = Booking.query.filter(
            or_(
                Booking.Outbound_Flight_ID == flight_id,
                Booking.Return_Flight_ID == flight_id
            )
        ).all()

        for booking in bookings_to_cancel:
            is_partial_cancellation = False
            other_flight_id = None
            
            # Determine if it's a round trip and which flight is being canceled
            if booking.Outbound_Flight_ID == flight_id and booking.Return_Flight_ID:
                other_flight_id = booking.Return_Flight_ID
            elif booking.Return_FLight_ID == flight_id and booking.Outbound_Flight_ID:
                other_flight_id = booking.Outbound_Flight_ID

            if other_flight_id:
                # Get the actual flight objects for comparison
                current_canceled_flight_obj = Flight.query.get(flight_id) # This is 'flight' from outside the loop
                outbound_flight_obj = Flight.query.get(booking.Outbound_Flight_ID)
                return_flight_obj = Flight.query.get(booking.Return_Flight_ID)
                
                current_time = datetime.datetime.now()

                # User's condition: cancellation time is between Flight A's departure and Flight B's departure
                # This implies Flight A has departed, and Flight B is being canceled before its departure.
                if outbound_flight_obj and return_flight_obj:
                    if (outbound_flight_obj.Departure_Time < current_time and
                        current_time < return_flight_obj.Departure_Time):
                        is_partial_cancellation = True
                else:
                    pass # Not a round trip or one leg missing for partial cancellation check.


            if is_partial_cancellation:
                booking.Status = 'Partial_Canceled'
                # For partial cancellation, only delete records related to the *canceled flight*
                # The other flight's passengers/boarding passes remain with the booking
                Boarding_Pass.query.filter_by(Booking_ID=booking.Booking_ID, Flight_ID=flight_id).delete(synchronize_session=False)
                Passenger.query.filter_by(Booking_ID=booking.Booking_ID, Flight_ID=flight_id).delete(synchronize_session=False)
            else:
                booking.Status = 'Canceled'
                # For full cancellation, delete all records related to the *entire booking*
                Boarding_Pass.query.filter_by(Booking_ID=booking.Booking_ID).delete(synchronize_session=False)
                Passenger.query.filter_by(Booking_ID=booking.Booking_ID).delete(synchronize_session=False)

            # Related payment refund processing (full refund)
            for payment in booking.payments:
                payment.status = 'Refunded'
                payment.refunded_amount = payment.Amount # Full refund
                payment.Refund_Date = datetime.datetime.now()

        # Delete flight seat availability for the *canceled flight* (moved outside the booking loop)
        Flight_Seat_Availability.query.filter_by(Flight_ID=flight_id).delete(synchronize_session=False)


        # 3. 항공편 관련 기타 데이터 삭제/업데이트
        # 승무원 배정 삭제
        Crew_Assignment.query.filter_by(Flight_ID=flight_id).delete(synchronize_session=False)
        
        # 항공편 가격 정보 삭제
        Flight_Price.query.filter_by(Flight_ID=flight_id).delete(synchronize_session=False)

        db.session.commit()
        flash(f"항공편 {flight_id}이(가) 성공적으로 취소되었으며, 관련 예약 및 데이터가 처리되었습니다.", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"항공편 취소 처리 중 오류 발생: {e}", 'error')

    return redirect(url_for('admin.flight_management'))

@admin_bp.route('/flight_management')
@staff_login_required
@role_required('Scheduler')
def flight_management():
    """ 항공편 관리 페이지를 렌더링하고, 검색 필터링을 수행합니다. """
    
    # 1. GET 파라미터에서 검색 조건 가져오기
    search_filters = {
        'aircraft_id': request.args.get('aircraft_id', '').strip(),
        'flight_no': request.args.get('flight_no', '').strip(),
        'model': request.args.get('model', '').strip(),
        'manufacturer': request.args.get('manufacturer', '').strip(),
        'dep_airport': request.args.get('dep_airport', '').strip(),
        'arr_airport': request.args.get('arr_airport', '').strip(),
        'start_date': request.args.get('start_date', '').strip(),
        'end_date': request.args.get('end_date', '').strip(),
        'flight_status': request.args.get('flight_status', '').strip() # Add this line
    }

    # 2. 기본 쿼리 생성 (Flight와 Aircraft 테이블을 조인)
    query = Flight.query.join(Aircraft, Flight.Aircraft_ID == Aircraft.Aircraft_ID)

    # 3. 검색 조건에 따라 동적으로 쿼리 필터링
    if search_filters['aircraft_id']:
        query = query.filter(Flight.Aircraft_ID.ilike(f"%{search_filters['aircraft_id']}%"))
    
    if search_filters['flight_no']:
        query = query.filter(Flight.Flight_No.ilike(f"%{search_filters['flight_no']}%"))

    if search_filters['model']:
        query = query.filter(Aircraft.Model.ilike(f"%{search_filters['model']}%"))

    if search_filters['manufacturer']:
        query = query.filter(Aircraft.Manufacturer.ilike(f"%{search_filters['manufacturer']}%"))

    if search_filters['dep_airport']:
        query = query.filter(Flight.Departure_Airport_Code.ilike(f"%{search_filters['dep_airport']}%"))

    if search_filters['arr_airport']:
        query = query.filter(Flight.Arrival_Airport_Code.ilike(f"%{search_filters['arr_airport']}%"))

    # Add this block for flight_status filter
    if search_filters['flight_status']:
        query = query.filter(Flight.Flight_Status == search_filters['flight_status'])

    # 개선된 기간 필터링 로직
    start_date_str = search_filters['start_date']
    end_date_str = search_filters['end_date']
    
    try:
        if start_date_str and end_date_str:
            start_date_obj = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date_obj = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') + datetime.timedelta(days=1, seconds=-1)
            query = query.filter(
                or_(
                    Flight.Departure_Time.between(start_date_obj, end_date_obj),
                    Flight.Arrival_Time.between(start_date_obj, end_date_obj)
                )
            )
        elif start_date_str:
            start_date_obj = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(
                or_(
                    Flight.Departure_Time >= start_date_obj,
                    Flight.Arrival_Time >= start_date_obj
                )
            )
        elif end_date_str:
            end_date_obj = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') + datetime.timedelta(days=1, seconds=-1)
            query = query.filter(
                or_(
                    Flight.Departure_Time <= end_date_obj,
                    Flight.Arrival_Time <= end_date_obj
                )
            )
    except ValueError:
        flash('날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)', 'error')

    # 4. 최종 쿼리 실행 및 정렬
    flights = query.order_by(Flight.Departure_Time.desc()).all()

    # 5. 템플릿 렌더링
    return render_template('admin_flight_management.html', 
                           flights=flights, 
                           search_filters=search_filters)


@admin_bp.route('/maintenance', methods=['GET', 'POST'])
@staff_login_required
@role_required('Engineer')
def maintenance_dashboard():
    """
    엔지니어용 정비 대시보드.
    - POST: 새 정비 기록 생성
    - GET: 정비 기록 필터링 및 조회
    """
    
    # --- 1. POST (새 정비 기록 생성) ---
    if request.method == 'POST':
        try:
            aircraft_id = request.form.get('aircraft_id')
            maintenance_date_str = request.form.get('maintenance_date')
            details = request.form.get('details')
            
            # (1-1) 유효성 검사
            if not all([aircraft_id, maintenance_date_str, details]):
                raise ValueError("항공기 ID, 정비 날짜, 정비 내역을 모두 입력해야 합니다.")
            
            if not Aircraft.query.get(aircraft_id):
                raise ValueError(f"항공기 ID '{aircraft_id}'를 찾을 수 없습니다.")

            maintenance_date = datetime.datetime.strptime(maintenance_date_str, '%Y-%m-%d').date()
            
            # (1-2) 새 기록 생성
            new_record = Maintenance_Record(
                Aircraft_ID=aircraft_id,
                Staff_ID=g.user.Staff_ID, # 현재 로그인한 엔지니어
                Date=maintenance_date,
                Details=details
            )
            db.session.add(new_record)
            db.session.commit()
            flash('정비 기록이 성공적으로 등록되었습니다.', 'success')
        
        except (ValueError, Exception) as e:
            db.session.rollback()
            flash(f'오류: {str(e)}', 'error')
        
        return redirect(url_for('admin.maintenance_dashboard'))

    # --- 2. GET (정비 기록 조회 및 필터링) ---
    
    # (2-1) 필터 조건 가져오기
    search_filters = {
        'aircraft_id': request.args.get('aircraft_id', '').strip(),
        'staff_id': request.args.get('staff_id', '').strip(),
        'start_date': request.args.get('start_date', '').strip(),
        'end_date': request.args.get('end_date', '').strip()
    }

    # (2-2) 기본 쿼리 (Join을 통해 항공기 모델, 직원 이름도 가져옴)
    query = db.session.query(Maintenance_Record).join(
        Aircraft, Maintenance_Record.Aircraft_ID == Aircraft.Aircraft_ID
    ).join(
        Staff, Maintenance_Record.Staff_ID == Staff.Staff_ID
    )

    # (2-3) 필터 적용
    if search_filters['aircraft_id']:
        query = query.filter(Maintenance_Record.Aircraft_ID.ilike(f"%{search_filters['aircraft_id']}%"))
    if search_filters['staff_id']:
        query = query.filter(Maintenance_Record.Staff_ID == search_filters['staff_id'])
    
    try:
        if search_filters['start_date']:
            start_date_obj = datetime.datetime.strptime(search_filters['start_date'], '%Y-%m-%d').date()
            query = query.filter(Maintenance_Record.Date >= start_date_obj)
        if search_filters['end_date']:
            end_date_obj = datetime.datetime.strptime(search_filters['end_date'], '%Y-%m-%d').date()
            query = query.filter(Maintenance_Record.Date <= end_date_obj)
    except ValueError:
        flash('날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)', 'error')
        search_filters['start_date'] = ''
        search_filters['end_date'] = ''

    # (2-4) 쿼리 실행
    records = query.order_by(Maintenance_Record.Date.desc()).all()
    
    # (2-5) 폼 내 Select Box를 채우기 위한 데이터
    all_aircraft = Aircraft.query.order_by(Aircraft.Model).all()
    all_engineers = Staff.query.filter_by(Role='Engineer').order_by(Staff.Name).all()

    # (2-6) 템플릿 렌더링
    return render_template('admin_maintenance_dashboard.html',
                           records=records,
                           search_filters=search_filters,
                           all_aircraft=all_aircraft,
                           all_engineers=all_engineers)

# (admin_views.py 파일 맨 아래에 이 함수를 통째로 추가)

@admin_bp.route('/hr', methods=['GET', 'POST'])
@staff_login_required
@role_required('HR')
def hr_dashboard():
    """
    HR용 직원 관리 대시보드.
    - POST (action='create'): 새 직원 등록
    - POST (action='delete'): 기존 직원 삭제
    - GET: 직원 목록 조회
    """
    
    # --- 1. POST (직원 등록 또는 삭제) ---
    if request.method == 'POST':
        action = request.form.get('action')
        
        # --- 1A. 새 직원 등록 ---
        if action == 'create':
            try:
                staff_id = request.form.get('staff_id')
                name = request.form.get('name')
                passwd = request.form.get('passwd')
                role = request.form.get('role')
                department = request.form.get('department')
                
                # (유효성 검사)
                if not all([staff_id, name, passwd, role, department]):
                    raise ValueError("모든 필드를 입력해야 합니다.")
                
                # (ID 중복 검사: Staff 테이블과 Member 테이블 모두)
                if Staff.query.get(staff_id) or Member.query.get(staff_id):
                    raise ValueError(f"ID '{staff_id}'는 이미 사용 중입니다.")

                # (새 직원 객체 생성 - 비밀번호는 평문 저장)
                new_staff = Staff(
                    Staff_ID=staff_id,
                    Name=name,
                    Passwd=passwd, 
                    Role=role,
                    Department=department
                )
                db.session.add(new_staff)
                db.session.commit()
                flash('새 직원이 성공적으로 등록되었습니다.', 'success')
            
            except (ValueError, Exception) as e:
                db.session.rollback()
                flash(f'직원 등록 오류: {str(e)}', 'error')
        
        # --- 1B. 직원 삭제 ---
        elif action == 'delete':
            staff_id_to_delete = request.form.get('staff_id_to_delete')
            try:
                if not staff_id_to_delete:
                    raise ValueError("삭제할 직원 ID가 없습니다.")
                
                staff_to_delete = Staff.query.get(staff_id_to_delete)
                if not staff_to_delete:
                    raise ValueError(f"직원 ID '{staff_id_to_delete}'를 찾을 수 없습니다.")
                
                # (자신 삭제 방지)
                if staff_to_delete.Staff_ID == g.user.Staff_ID:
                    raise ValueError("현재 로그인된 본인 계정은 삭제할 수 없습니다.")

                # [!!!] 핵심 제약 조건 검사 (요청사항) [!!!]
                if staff_to_delete.assignments:
                    raise ValueError(f"직원 '{staff_to_delete.Name}'({staff_id_to_delete})는 항공편에 배정되어 있어 삭제할 수 없습니다.")
                
                # (엔지니어의 경우, 정비 기록이 있어도 삭제 방지)
                if staff_to_delete.maintenance_records:
                    raise ValueError(f"직원 '{staff_to_delete.Name}'({staff_id_to_delete})는 정비 기록이 있어 삭제할 수 없습니다.")

                # (제약 조건 통과 시 삭제)
                db.session.delete(staff_to_delete)
                db.session.commit()
                flash(f"직원 '{staff_to_delete.Name}'({staff_id_to_delete})이(가) 삭제되었습니다.", 'success')
            
            except (ValueError, Exception) as e:
                db.session.rollback()
                flash(f'직원 삭제 오류: {str(e)}', 'error')
        
        return redirect(url_for('admin.hr_dashboard'))

    # --- 2. GET (직원 목록 조회) ---
    
    # (2-1) 필터 조건 가져오기
    search_filters = {
        'staff_id': request.args.get('staff_id', '').strip(),
        'name': request.args.get('name', '').strip(),
        'role': request.args.get('role', '').strip(),
        'department': request.args.get('department', '').strip(),
    }

    # (2-2) 기본 쿼리
    query = Staff.query

    # (2-3) 필터 적용
    if search_filters['staff_id']:
        query = query.filter(Staff.Staff_ID.ilike(f"%{search_filters['staff_id']}%"))
    if search_filters['name']:
        query = query.filter(Staff.Name.ilike(f"%{search_filters['name']}%"))
    if search_filters['role']:
        query = query.filter(Staff.Role == search_filters['role'])
    if search_filters['department']:
        query = query.filter(Staff.Department.ilike(f"%{search_filters['department']}%"))

    # (2-4) 쿼리 실행
    all_staff = query.order_by(Staff.Staff_ID).all()
    
    # (2-5) 템플릿 렌더링
    return render_template('admin_hr_management.html',
                           all_staff=all_staff,
                           search_filters=search_filters,
                           # (Role Enum 값을 템플릿 Select Box에 전달)
                           staff_roles=Staff.Role.type.enums)

# (admin_views.py 파일 맨 아래에 이 함수를 통째로 추가)

@admin_bp.route('/my_schedule')
@staff_login_required
def my_schedule():
    """
    Pilot, Co-Pilot, Cabin Crew가 로그인했을 때
    본인의 항공편 일정을 보여주는 페이지.
    """
    
    # (1. 스케줄러가 아니면 접근 제한 - 이 3가지 역할만 허용)
    if g.user.Role not in ['Pilot', 'Co-Pilot', 'Cabin Crew']:
        flash('본인 일정 조회 권한이 없습니다.')
        return redirect(url_for('admin.index'))
        
    try:
        # (2. 오늘 날짜 기준으로, 앞으로의 일정만 조회)
        today = datetime.date.today()
        
        # (3. Crew_Assignment 테이블에서 내 ID가 포함된 항공편(Flight) 목록 조회)
        assignments = db.session.query(Flight).join(Crew_Assignment).filter(
            Crew_Assignment.Staff_ID == g.user.Staff_ID,
            Flight.Departure_Time >= today
        ).order_by(Flight.Departure_Time).all()

        # (4. Pilot_schedule.html 템플릿에서 사용하던 형식(schedule 딕셔너리)으로 가공)
        schedule = {}
        for flight in assignments:
            month = flight.Departure_Time.strftime('%Y-%m')
            day = flight.Departure_Time.strftime('%Y-%m-%d')
            if month not in schedule:
                schedule[month] = {}
            if day not in schedule[month]:
                schedule[month][day] = []
            schedule[month][day].append(flight)
        
        # (5. 새 템플릿 렌더링)
        return render_template('admin_my_schedule.html', 
                               staff=g.user, 
                               schedule=schedule)
                               
    except Exception as e:
        flash(f"스케줄을 불러오는 중 오류가 발생했습니다: {e}", "error")
        return redirect(url_for('admin.index'))