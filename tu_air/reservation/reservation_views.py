# TU_Air/tu_air/reservation/reservation_views.py
# (!!! 새 파일 !!!)

from . import reservation_bp
from ..extensions import db
from ..models import Booking, Payment, Passenger, Flight_Seat_Availability
from flask import render_template, request, flash, redirect, url_for, g, session
import datetime

@reservation_bp.route('/', methods=['GET', 'POST'])
def index():
    """ 예약 번호 입력 페이지 (GET/POST) """
    if request.method == 'POST':
        booking_id = request.form.get('booking_id', '').strip().upper()
        
        if not booking_id:
            flash('예약 번호를 입력해 주세요.')
            return redirect(url_for('reservation.index'))

        # (DB에서 Booking_ID로 예약 조회)
        booking = Booking.query.get(booking_id)
        
        if booking:
            # (찾았으면, 상세 페이지로 이동)
            return redirect(url_for('reservation.details', booking_id=booking.Booking_ID))
        else:
            flash('일치하는 예약 정보를 찾을 수 없습니다.')
            return redirect(url_for('reservation.index'))

    # (GET 요청 시)
    return render_template('reservation_index.html')


@reservation_bp.route('/<string:booking_id>')
def details(booking_id):
    """ 예약 상세 정보 페이지 (GET) """
    # (쿼리로 조회)
    booking = Booking.query.get_or_404(booking_id)
    
    # (비회원 예약인데, 다른 사람이 로그인해서 보려는 경우 방지)
    if booking.Member_ID and g.user and booking.Member_ID != g.user.Member_ID:
        flash('본인의 예약만 조회할 수 있습니다.')
        return redirect(url_for('main.home'))

    return render_template('reservation_details.html', 
                           booking=booking,
                           now=datetime.datetime.now())

# [!!!] (신규) 환불금 계산을 위한 헬퍼 함수 [!!!]
# (cancel_booking 함수 *위에* 이 함수를 추가해 주세요)
def get_refund_amount(base_amount, flight_departure_time, now):
    """
    요청한 환불 규정에 따라 환불액을 계산합니다.
    - base_amount: 전액(100%) 환불 기준 금액 (전체 결제액 또는 50%)
    - flight_departure_time: 기준이 되는 항공편의 출발 시간
    - now: 현재 시간
    """
    time_left = flight_departure_time - now
    days_left = time_left.days
    total_base = float(base_amount) # (Decimal -> float)
    
    penalty_rate = 0.0
    if days_left >= 91:
        penalty_rate = 0.0
    elif 61 <= days_left <= 90:
        penalty_rate = 0.10
    elif 31 <= days_left <= 60:
        penalty_rate = 0.25
    elif 8 <= days_left <= 30:
        penalty_rate = 0.45
    elif time_left.total_seconds() >= (24 * 3600): # (7일~24시간 전)
        penalty_rate = 0.70
    else: # (24시간 이내 = "출발 당일 취소")
        penalty_rate = 1.0
        
    return total_base * (1.0 - penalty_rate)

@reservation_bp.route('/<string:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    """ 예약 취소 처리 (POST) """
    
    booking = Booking.query.get_or_404(booking_id)

    # (비회원 예약인데, 다른 사람이 로그인해서 취소하려는 경우 방지)
    if booking.Member_ID and (not g.user or booking.Member_ID != g.user.Member_ID):
        flash('본인의 예약만 취소할 수 있습니다.')
        return redirect(url_for('main.home'))
    
    # (이미 취소되었는지 확인)
    if booking.Status == 'Canceled':
        flash('이미 전체 취소된 예약입니다.')
        return redirect(url_for('reservation.details', booking_id=booking_id))

    try:
        now = datetime.datetime.now()
        outbound_flight = booking.outbound_flight
        inbound_flight = booking.return_flight
        # (결제는 1번만 일어났다고 가정)
        payment = booking.payments[0] if booking.payments else None
        
        if not payment:
            raise Exception("결제 기록을 찾을 수 없습니다.")

        total_amount = float(payment.Amount)

        # --- (R3) 전체 취소 로직 (가는 편 출발 이전) ---
        if now < outbound_flight.Departure_Time:
            
            booking.Status = 'Canceled' # (1. Booking 상태 변경)

            # (2/3. 모든 탑승객(Passenger) 및 탑승권(Boarding_Pass) 삭제)
            passengers_all = Passenger.query.filter_by(Booking_ID=booking_id).all()
            seat_ids_to_free = []
            for pax in passengers_all:
                if pax.boarding_pass: 
                    db.session.delete(pax.boarding_pass)
                seat_ids_to_free.append((pax.Flight_ID, pax.Seat_ID))
                db.session.delete(pax)
                
            # (좌석(FSA) 상태 'Available'로 원복)
            for flight_id, seat_id in seat_ids_to_free:
                fsa = Flight_Seat_Availability.query.get((flight_id, seat_id))
                if fsa and fsa.Availability_Status == 'Reserved':
                    fsa.Availability_Status = 'Available'
                        
            # (4. Payment 상태 'Refunded' 및 환불금 계산)
            if payment:
                payment.status = 'Refunded'
                payment.refunded_amount = get_refund_amount(
                    total_amount, 
                    outbound_flight.Departure_Time, 
                    now
                )
                db.session.add(payment)
        # --- (R4) 부분 취소 로직 (가는 편 출발 이후 ~ 오는 편 출발 이전) ---
        elif inbound_flight and (now > outbound_flight.Departure_Time and now < inbound_flight.Departure_Time):
            
            if booking.Status == 'Partial_Canceled':
                flash('이미 부분 취소된 예약입니다.')
                return redirect(url_for('reservation.details', booking_id=booking_id))

            booking.Status = 'Partial_Canceled' # (1. Booking 상태 변경)

            # (2/3. '오는 편' 탑승객(Passenger) 및 탑승권(Boarding_Pass) 삭제)
            passengers_in = Passenger.query.filter_by(Booking_ID=booking_id, Flight_ID=inbound_flight.Flight_ID).all()
            seat_ids_to_free = []
            for pax in passengers_in:
                if pax.boarding_pass: 
                    db.session.delete(pax.boarding_pass)
                seat_ids_to_free.append((pax.Flight_ID, pax.Seat_ID))
                db.session.delete(pax)

            # (오는 편 좌석(FSA) 상태 'Available'로 원복)
            for flight_id, seat_id in seat_ids_to_free:
                fsa = Flight_Seat_Availability.query.get((flight_id, seat_id))
                if fsa and fsa.Availability_Status == 'Reserved':
                    fsa.Availability_Status = 'Available'

            if payment:    
                # (4. Payment 상태 'Refunded' 및 '오는 편' 환불금 계산)
                payment.status = 'Refunded'
            
                # (R4 요청: '오는 편' 가격은 '결제금액의 50%')
                inbound_base_amount = total_amount * 0.5 
            
                refund_for_inbound = get_refund_amount(
                    inbound_base_amount, 
                    inbound_flight.Departure_Time, 
                    now
                )
            
                # (기존 환불액이 0.00이므로, 그냥 덮어씀)
                payment.refunded_amount = refund_for_inbound
                db.session.add(payment)

        # --- (취소 불가) ---
        else:
            flash('이미 여정이 시작되었거나 완료되어 취소가 불가능합니다.')
            db.session.rollback() # (변경 사항 없음)
            return redirect(url_for('reservation.details', booking_id=booking_id))
        
        # (최종 커밋)
        db.session.commit()
        flash(f'예약이 [ {booking.Status} ] 상태로 변경되었습니다.')
        
    except Exception as e:
        db.session.rollback()
        flash(f'예약 취소 중 오류가 발생했습니다: {e}')
        
    return redirect(url_for('reservation.details', booking_id=booking_id))