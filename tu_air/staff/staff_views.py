# TU_Air/tu_air/staff/staff_views.py

from . import staff_bp
from ..extensions import db
from ..models import Staff, Flight, Booking, Payment, Aircraft
from flask import render_template, request, flash, redirect, url_for, session, g, jsonify
from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import func

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
        'Scheduler': 'staff.employee_schedule',
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

# --- 스케줄러: 직원 스케줄 관리 ---
@staff_bp.route('/employee-schedule')
@staff_login_required
def employee_schedule():
    """직원 스케줄 관리 페이지"""
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

