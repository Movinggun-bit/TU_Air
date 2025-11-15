# TU_Air/tu_air/staff/staff_views.py

from . import staff_bp
from ..extensions import db
from ..models import (Staff, Flight, Booking, Payment, Aircraft, Airport, 
                     Seat, Flight_Seat_Availability, Crew_Assignment, Passenger, 
                     Boarding_Pass, Flight_Price)
from flask import render_template, request, flash, redirect, url_for, session, g, jsonify
from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import func, or_, and_
import random
import string

# 직원 로그인 필수 데코레이터
def staff_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None or not hasattr(g.user, 'Role'):
            flash('직원 로그인이 필요합니다.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# 직업별 페이지 라우팅 함수
def get_staff_dashboard_url(role):
    """직업에 따라 적절한 대시보드 URL 반환"""
    role_map = {
        'Pilot': 'staff.flight_schedule',
        'Co-Pilot': 'staff.flight_schedule',
        'Cabin Crew': 'staff.flight_schedule',
        'Engineer': 'staff.maintenance',
        'Ground Staff': 'staff.maintenance',
        'HR': 'staff.hr_management',
        'Scheduler': 'staff.scheduler_dashboard',
        'CEO': 'staff.ceo_dashboard',
        'marketer': 'staff.sales_revenue'
    }
    return role_map.get(role, 'staff.flight_schedule')

@staff_bp.route('/dashboard')
@staff_login_required
def dashboard():
    """직업별 대시보드로 리다이렉트"""
    if g.user and hasattr(g.user, 'Role'):
        url = get_staff_dashboard_url(g.user.Role)
        return redirect(url_for(url))
    return redirect(url_for('auth.login'))

# --- 파일럿/코파일럿/카빈크루: 비행 스케줄 ---
@staff_bp.route('/flight-schedule')
@staff_login_required
def flight_schedule():
    """비행 스케줄 조회 페이지"""
    # 오늘부터 30일간의 비행 스케줄 조회
    today = datetime.now().date()
    end_date = today + timedelta(days=30)
    
    flights = Flight.query.filter(
        Flight.Departure_Time >= datetime.combine(today, datetime.min.time()),
        Flight.Departure_Time <= datetime.combine(end_date, datetime.max.time())
    ).order_by(Flight.Departure_Time).all()
    
    return render_template('staff/flight_schedule.html', 
                         flights=flights, 
                         role=g.user.Role,
                         staff_name=g.user.Name)

# --- 엔지니어/그라운드 스태프: 정비내역 ---
@staff_bp.route('/maintenance')
@staff_login_required
def maintenance():
    """정비내역 조회 페이지"""
    # 항공기 목록 조회
    aircrafts = Aircraft.query.all()
    
    # 간단한 정비 이력 (실제로는 별도 Maintenance 모델이 필요하지만, 여기서는 항공기 정보만 표시)
    maintenance_data = []
    for aircraft in aircrafts:
        # 해당 항공기의 최근 비행 횟수
        recent_flights = Flight.query.filter_by(Aircraft_ID=aircraft.Aircraft_ID).count()
        maintenance_data.append({
            'aircraft': aircraft,
            'recent_flights': recent_flights,
            'last_maintenance': 'N/A'  # 실제로는 Maintenance 모델에서 가져와야 함
        })
    
    return render_template('staff/maintenance.html', 
                         maintenance_data=maintenance_data,
                         role=g.user.Role,
                         staff_name=g.user.Name)

# --- HR: 인사관리 ---
@staff_bp.route('/hr-management')
@staff_login_required
def hr_management():
    """인사관리 페이지 (채용, 평가, 보상)"""
    # 전체 직원 목록
    all_staff = Staff.query.order_by(Staff.Name).all()
    
    # 직업별 통계
    role_stats = {}
    for role in ['Pilot', 'Co-Pilot', 'Cabin Crew', 'Engineer', 'Ground Staff', 'HR', 'Scheduler', 'CEO', 'marketer']:
        role_stats[role] = Staff.query.filter_by(Role=role).count()
    
    return render_template('staff/hr_management.html',
                         all_staff=all_staff,
                         role_stats=role_stats,
                         role=g.user.Role,
                         staff_name=g.user.Name)

# --- 스케줄러: 항공편 편성/수정/취소 관리 ---
@staff_bp.route('/scheduler-dashboard')
@staff_login_required
def scheduler_dashboard():
    """스케줄러 대시보드 - 항공편 편성, 수정, 취소"""
    # 스케줄러만 접근 가능
    if g.user.Role != 'Scheduler':
        flash('스케줄러만 접근할 수 있습니다.')
        return redirect(url_for('staff.dashboard'))
    
    # 전체 항공기 목록
    aircrafts = Aircraft.query.all()
    
    # 전체 공항 목록
    airports = Airport.query.all()
    
    # 전체 직원 목록 (Pilot, Co-Pilot, Cabin Crew만)
    crew_staff = Staff.query.filter(
        Staff.Role.in_(['Pilot', 'Co-Pilot', 'Cabin Crew'])
    ).order_by(Staff.Role, Staff.Name).all()
    
    # 오늘부터 30일간의 비행 스케줄
    today = datetime.now().date()
    end_date = today + timedelta(days=30)
    
    flights = Flight.query.filter(
        Flight.Departure_Time >= datetime.combine(today, datetime.min.time()),
        Flight.Departure_Time <= datetime.combine(end_date, datetime.max.time())
    ).order_by(Flight.Departure_Time).all()
    
    return render_template('staff/scheduler_dashboard.html',
                         aircrafts=aircrafts,
                         airports=airports,
                         crew_staff=crew_staff,
                         flights=flights,
                         role=g.user.Role,
                         staff_name=g.user.Name)

# --- 스케줄러: 항공기 스케줄 조회 API ---
@staff_bp.route('/api/aircraft-schedule/<aircraft_id>')
@staff_login_required
def get_aircraft_schedule(aircraft_id):
    """특정 항공기의 스케줄 조회 (시간 중복 확인용)"""
    if g.user.Role != 'Scheduler':
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    # 해당 항공기의 모든 비행편 조회
    flights = Flight.query.filter_by(Aircraft_ID=aircraft_id).order_by(Flight.Departure_Time).all()
    
    schedule = []
    for flight in flights:
        schedule.append({
            'flight_id': flight.Flight_ID,
            'flight_no': flight.Flight_No,
            'departure_time': flight.Departure_Time.isoformat(),
            'arrival_time': flight.Arrival_Time.isoformat(),
            'departure_airport': flight.Departure_Airport_Code,
            'arrival_airport': flight.Arrival_Airport_Code,
            'status': flight.Flight_Status
        })
    
    return jsonify({'schedule': schedule})

# --- 스케줄러: 직원 스케줄 조회 API ---
@staff_bp.route('/api/staff-schedule/<staff_id>')
@staff_login_required
def get_staff_schedule(staff_id):
    """특정 직원의 스케줄 조회 (시간 중복 확인용)"""
    if g.user.Role != 'Scheduler':
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    # 해당 직원이 배정된 모든 항공편 조회
    assignments = Crew_Assignment.query.filter_by(Staff_ID=staff_id).all()
    
    schedule = []
    for assignment in assignments:
        flight = assignment.flight
        schedule.append({
            'flight_id': flight.Flight_ID,
            'flight_no': flight.Flight_No,
            'departure_time': flight.Departure_Time.isoformat(),
            'arrival_time': flight.Arrival_Time.isoformat(),
            'departure_airport': flight.Departure_Airport_Code,
            'arrival_airport': flight.Arrival_Airport_Code,
            'status': flight.Flight_Status
        })
    
    return jsonify({'schedule': schedule})

# --- 스케줄러: 항공편 편성 (생성) ---
@staff_bp.route('/scheduler/create-flight', methods=['POST'])
@staff_login_required
def create_flight():
    """항공편 편성 (생성)"""
    if g.user.Role != 'Scheduler':
        flash('스케줄러만 접근할 수 있습니다.')
        return redirect(url_for('staff.dashboard'))
    
    try:
        # 폼 데이터 받기
        flight_no = request.form.get('flight_no')
        aircraft_id = request.form.get('aircraft_id')
        departure_airport = request.form.get('departure_airport')
        arrival_airport = request.form.get('arrival_airport')
        departure_time_str = request.form.get('departure_time')
        arrival_time_str = request.form.get('arrival_time')
        departure_gate = request.form.get('departure_gate')
        arrival_gate = request.form.get('arrival_gate')
        
        # 가격 정보
        economy_price = request.form.get('economy_price')
        business_price = request.form.get('business_price')
        first_price = request.form.get('first_price')
        
        # 직원 배정 (선택적)
        pilot_ids = request.form.getlist('pilot_id')
        copilot_ids = request.form.getlist('copilot_id')
        cabin_crew_ids = request.form.getlist('cabin_crew_id')
        
        # 유효성 검사
        if not all([flight_no, aircraft_id, departure_airport, arrival_airport, 
                   departure_time_str, arrival_time_str, departure_gate, arrival_gate]):
            flash('모든 필수 필드를 입력해주세요.')
            return redirect(url_for('staff.scheduler_dashboard'))
        
        departure_time = datetime.strptime(departure_time_str, '%Y-%m-%dT%H:%M')
        arrival_time = datetime.strptime(arrival_time_str, '%Y-%m-%dT%H:%M')
        
        if arrival_time <= departure_time:
            flash('도착 시간은 출발 시간보다 늦어야 합니다.')
            return redirect(url_for('staff.scheduler_dashboard'))
        
        # 항공기 시간 중복 확인
        conflicting_flights = Flight.query.filter(
            Flight.Aircraft_ID == aircraft_id,
            Flight.Flight_Status != 'Canceled',
            or_(
                and_(Flight.Departure_Time <= departure_time, Flight.Arrival_Time >= departure_time),
                and_(Flight.Departure_Time <= arrival_time, Flight.Arrival_Time >= arrival_time),
                and_(Flight.Departure_Time >= departure_time, Flight.Arrival_Time <= arrival_time)
            )
        ).all()
        
        if conflicting_flights:
            flash(f'해당 시간에 항공기 {aircraft_id}가 이미 사용 중입니다.')
            return redirect(url_for('staff.scheduler_dashboard'))
        
        # 직원 시간 중복 확인
        all_staff_ids = pilot_ids + copilot_ids + cabin_crew_ids
        for staff_id in all_staff_ids:
            if staff_id:
                conflicting_assignments = Crew_Assignment.query.join(Flight).filter(
                    Crew_Assignment.Staff_ID == staff_id,
                    Flight.Flight_Status != 'Canceled',
                    or_(
                        and_(Flight.Departure_Time <= departure_time, Flight.Arrival_Time >= departure_time),
                        and_(Flight.Departure_Time <= arrival_time, Flight.Arrival_Time >= arrival_time),
                        and_(Flight.Departure_Time >= departure_time, Flight.Arrival_Time <= arrival_time)
                    )
                ).all()
                
                if conflicting_assignments:
                    staff = Staff.query.get(staff_id)
                    flash(f'해당 시간에 직원 {staff.Name}({staff.Staff_ID})가 이미 배정되어 있습니다.')
                    return redirect(url_for('staff.scheduler_dashboard'))
        
        # Flight_ID 생성
        flight_id = 'FL' + ''.join(random.choices(string.digits, k=10))
        while Flight.query.get(flight_id):
            flight_id = 'FL' + ''.join(random.choices(string.digits, k=10))
        
        # 항공편 생성
        new_flight = Flight(
            Flight_ID=flight_id,
            Flight_No=flight_no,
            Aircraft_ID=aircraft_id,
            Departure_Airport_Code=departure_airport,
            Departure_Time=departure_time,
            Departure_Gate=departure_gate,
            Arrival_Airport_Code=arrival_airport,
            Arrival_Time=arrival_time,
            Arrival_Gate=arrival_gate,
            Flight_Status='On_Time'
        )
        db.session.add(new_flight)
        
        # 항공기 좌석 정보 가져오기
        aircraft = Aircraft.query.get(aircraft_id)
        seats = Seat.query.filter_by(Aircraft_ID=aircraft_id).all()
        
        # Flight_Seat_Availability 생성 (모든 좌석을 Available로)
        for seat in seats:
            fsa = Flight_Seat_Availability(
                Flight_ID=flight_id,
                Seat_ID=seat.Seat_ID,
                Availability_Status='Available'
            )
            db.session.add(fsa)
        
        # Flight_Price 생성
        if economy_price:
            fp_economy = Flight_Price(Flight_ID=flight_id, Class='Economy', Price=economy_price)
            db.session.add(fp_economy)
        if business_price:
            fp_business = Flight_Price(Flight_ID=flight_id, Class='Business', Price=business_price)
            db.session.add(fp_business)
        if first_price:
            fp_first = Flight_Price(Flight_ID=flight_id, Class='First', Price=first_price)
            db.session.add(fp_first)
        
        # 직원 배정
        assignment_counter = 1
        for staff_id in pilot_ids:
            if staff_id:
                assignment_id = f'CA{assignment_counter:010d}'
                while Crew_Assignment.query.get(assignment_id):
                    assignment_counter += 1
                    assignment_id = f'CA{assignment_counter:010d}'
                assignment = Crew_Assignment(
                    Assignment_ID=assignment_id,
                    Flight_ID=flight_id,
                    Staff_ID=staff_id
                )
                db.session.add(assignment)
                assignment_counter += 1
        
        for staff_id in copilot_ids:
            if staff_id:
                assignment_id = f'CA{assignment_counter:010d}'
                while Crew_Assignment.query.get(assignment_id):
                    assignment_counter += 1
                    assignment_id = f'CA{assignment_counter:010d}'
                assignment = Crew_Assignment(
                    Assignment_ID=assignment_id,
                    Flight_ID=flight_id,
                    Staff_ID=staff_id
                )
                db.session.add(assignment)
                assignment_counter += 1
        
        for staff_id in cabin_crew_ids:
            if staff_id:
                assignment_id = f'CA{assignment_counter:010d}'
                while Crew_Assignment.query.get(assignment_id):
                    assignment_counter += 1
                    assignment_id = f'CA{assignment_counter:010d}'
                assignment = Crew_Assignment(
                    Assignment_ID=assignment_id,
                    Flight_ID=flight_id,
                    Staff_ID=staff_id
                )
                db.session.add(assignment)
                assignment_counter += 1
        
        db.session.commit()
        flash(f'항공편 {flight_no}({flight_id})이(가) 성공적으로 편성되었습니다.')
        
    except Exception as e:
        db.session.rollback()
        flash(f'항공편 편성 중 오류가 발생했습니다: {str(e)}')
    
    return redirect(url_for('staff.scheduler_dashboard'))

# --- 스케줄러: 항공편 수정 ---
@staff_bp.route('/scheduler/edit-flight/<flight_id>', methods=['POST'])
@staff_login_required
def edit_flight(flight_id):
    """항공편 수정 (출/도착 시간, 게이트만 수정 가능)"""
    if g.user.Role != 'Scheduler':
        flash('스케줄러만 접근할 수 있습니다.')
        return redirect(url_for('staff.dashboard'))
    
    flight = Flight.query.get_or_404(flight_id)
    
    try:
        # 수정 가능한 필드만 받기
        departure_time_str = request.form.get('departure_time')
        arrival_time_str = request.form.get('arrival_time')
        departure_gate = request.form.get('departure_gate')
        arrival_gate = request.form.get('arrival_gate')
        
        original_departure = flight.Departure_Time
        original_arrival = flight.Arrival_Time
        
        if departure_time_str:
            flight.Departure_Time = datetime.strptime(departure_time_str, '%Y-%m-%dT%H:%M')
        if arrival_time_str:
            flight.Arrival_Time = datetime.strptime(arrival_time_str, '%Y-%m-%dT%H:%M')
        if departure_gate:
            flight.Departure_Gate = departure_gate
        if arrival_gate:
            flight.Arrival_Gate = arrival_gate
        
        # 시간이 변경되었으면 Delayed 상태로 변경
        if (departure_time_str and flight.Departure_Time != original_departure) or \
           (arrival_time_str and flight.Arrival_Time != original_arrival):
            flight.Flight_Status = 'Delayed'
            status_reason = request.form.get('status_reason', '스케줄 변경')
            flight.Status_Reason = status_reason
        
        # 항공기 시간 중복 확인 (자기 자신 제외)
        if flight.Departure_Time != original_departure or flight.Arrival_Time != original_arrival:
            conflicting_flights = Flight.query.filter(
                Flight.Aircraft_ID == flight.Aircraft_ID,
                Flight.Flight_ID != flight_id,
                Flight.Flight_Status != 'Canceled',
                or_(
                    and_(Flight.Departure_Time <= flight.Departure_Time, Flight.Arrival_Time >= flight.Departure_Time),
                    and_(Flight.Departure_Time <= flight.Arrival_Time, Flight.Arrival_Time >= flight.Arrival_Time),
                    and_(Flight.Departure_Time >= flight.Departure_Time, Flight.Arrival_Time <= flight.Arrival_Time)
                )
            ).all()
            
            if conflicting_flights:
                flash(f'수정된 시간에 항공기 {flight.Aircraft_ID}가 이미 사용 중입니다.')
                return redirect(url_for('staff.scheduler_dashboard'))
        
        db.session.commit()
        flash(f'항공편 {flight.Flight_No}({flight_id})이(가) 성공적으로 수정되었습니다.')
        
    except Exception as e:
        db.session.rollback()
        flash(f'항공편 수정 중 오류가 발생했습니다: {str(e)}')
    
    return redirect(url_for('staff.scheduler_dashboard'))

# --- 스케줄러: 항공편 취소 ---
@staff_bp.route('/scheduler/cancel-flight/<flight_id>', methods=['POST'])
@staff_login_required
def cancel_flight(flight_id):
    """항공편 취소 (예약 취소 및 전액 환불)"""
    if g.user.Role != 'Scheduler':
        flash('스케줄러만 접근할 수 있습니다.')
        return redirect(url_for('staff.dashboard'))
    
    flight = Flight.query.get_or_404(flight_id)
    
    if flight.Flight_Status == 'Canceled':
        flash('이미 취소된 항공편입니다.')
        return redirect(url_for('staff.scheduler_dashboard'))
    
    try:
        cancel_reason = request.form.get('cancel_reason', '스케줄러에 의한 취소')
        
        # 항공편 취소
        flight.Flight_Status = 'Canceled'
        flight.Status_Reason = cancel_reason
        
        # 해당 항공편과 관련된 모든 예약 취소 및 전액 환불
        bookings = Booking.query.filter(
            or_(
                Booking.Outbound_Flight_ID == flight_id,
                Booking.Return_Flight_ID == flight_id
            ),
            Booking.Status != 'Canceled'
        ).all()
        
        now = datetime.now()
        
        for booking in bookings:
            # 예약 취소
            booking.Status = 'Canceled'
            
            # 모든 탑승객 및 탑승권 삭제
            passengers_all = Passenger.query.filter_by(Booking_ID=booking.Booking_ID).all()
            seat_ids_to_free = []
            for pax in passengers_all:
                if pax.boarding_pass:
                    db.session.delete(pax.boarding_pass)
                seat_ids_to_free.append((pax.Flight_ID, pax.Seat_ID))
                db.session.delete(pax)
            
            # 좌석 상태 원복
            for flight_id_param, seat_id in seat_ids_to_free:
                fsa = Flight_Seat_Availability.query.get((flight_id_param, seat_id))
                if fsa and fsa.Availability_Status == 'Reserved':
                    fsa.Availability_Status = 'Available'
            
            # 전액 환불
            payment = booking.payments[0] if booking.payments else None
            if payment and payment.status == 'Paid':
                payment.status = 'Refunded'
                payment.refunded_amount = payment.Amount  # 전액 환불
                payment.Refund_Date = now
        
        db.session.commit()
        flash(f'항공편 {flight.Flight_No}({flight_id})이(가) 취소되었고, 관련 예약이 모두 취소 및 환불되었습니다.')
        
    except Exception as e:
        db.session.rollback()
        flash(f'항공편 취소 중 오류가 발생했습니다: {str(e)}')
    
    return redirect(url_for('staff.scheduler_dashboard'))

# --- 스케줄러: 직원 스케줄 관리 (기존 함수 유지) ---
@staff_bp.route('/employee-schedule')
@staff_login_required
def employee_schedule():
    """직원 스케줄 관리 페이지 (레거시)"""
    # 전체 직원 목록
    all_staff = Staff.query.order_by(Staff.Name).all()
    
    # 오늘부터 7일간의 비행 스케줄
    today = datetime.now().date()
    end_date = today + timedelta(days=7)
    
    flights = Flight.query.filter(
        Flight.Departure_Time >= datetime.combine(today, datetime.min.time()),
        Flight.Departure_Time <= datetime.combine(end_date, datetime.max.time())
    ).order_by(Flight.Departure_Time).all()
    
    return render_template('staff/employee_schedule.html',
                         all_staff=all_staff,
                         flights=flights,
                         role=g.user.Role,
                         staff_name=g.user.Name)

# --- 마케터: 총 매출액 ---
@staff_bp.route('/sales-revenue')
@staff_login_required
def sales_revenue():
    """총 매출액 조회 페이지"""
    # 전체 매출액
    total_revenue = db.session.query(func.sum(Payment.Amount)).filter(
        Payment.status == 'Paid'
    ).scalar() or 0
    
    # 환불액
    total_refund = db.session.query(func.sum(Payment.refunded_amount)).filter(
        Payment.status == 'Refunded'
    ).scalar() or 0
    
    # 순매출액
    net_revenue = float(total_revenue) - float(total_refund)
    
    # 월별 매출액 (최근 12개월)
    monthly_revenue = []
    for i in range(11, -1, -1):
        month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_total = db.session.query(func.sum(Payment.Amount)).filter(
            Payment.status == 'Paid',
            Payment.Payment_Date >= month_start,
            Payment.Payment_Date <= month_end
        ).scalar() or 0
        
        monthly_revenue.append({
            'month': month_start.strftime('%Y-%m'),
            'revenue': float(month_total)
        })
    
    return render_template('staff/sales_revenue.html',
                         total_revenue=total_revenue,
                         total_refund=total_refund,
                         net_revenue=net_revenue,
                         monthly_revenue=monthly_revenue,
                         role=g.user.Role,
                         staff_name=g.user.Name)

# --- CEO: 대시보드 ---
@staff_bp.route('/ceo-dashboard')
@staff_login_required
def ceo_dashboard():
    """CEO 대시보드 페이지"""
    # 전체 직원 수
    total_staff = Staff.query.count()
    
    # 전체 매출액
    total_revenue = db.session.query(func.sum(Payment.Amount)).filter(
        Payment.status == 'Paid'
    ).scalar() or 0
    
    # 오늘의 비행편 수
    today = datetime.now().date()
    today_flights = Flight.query.filter(
        func.date(Flight.Departure_Time) == today
    ).count()
    
    # 오늘의 예약 수
    today_bookings = Booking.query.filter(
        func.date(Booking.Booking_Date) == today
    ).count()
    
    # 직업별 직원 수
    role_counts = {}
    for role in ['Pilot', 'Co-Pilot', 'Cabin Crew', 'Engineer', 'Ground Staff', 'HR', 'Scheduler', 'CEO', 'marketer']:
        role_counts[role] = Staff.query.filter_by(Role=role).count()
    
    return render_template('staff/ceo_dashboard.html',
                         total_staff=total_staff,
                         total_revenue=total_revenue,
                         today_flights=today_flights,
                         today_bookings=today_bookings,
                         role_counts=role_counts,
                         role=g.user.Role,
                         staff_name=g.user.Name)

