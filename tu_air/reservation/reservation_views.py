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

    return render_template('reservation_details.html', booking=booking)


@reservation_bp.route('/<string:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    """ 예약 취소 처리 (POST) """
    
    booking = Booking.query.get_or_404(booking_id)

    # (비회원 예약인데, 다른 사람이 로그인해서 취소하려는 경우 방지)
    if booking.Member_ID and (not g.user or booking.Member_ID != g.user.Member_ID):
        flash('본인의 예약만 취소할 수 있습니다.')
        return redirect(url_for('main.home'))

    try:
        # (1. Booking 상태 변경)
        booking.Status = 'Canceled'

        # (2. Payment 상태 변경)
        payments = Payment.query.filter_by(Booking_ID=booking_id).all()
        for p in payments:
            p.status = 'Refunded'
            # (TODO: 환불 금액 계산 로직...)

        # (3. 좌석 상태 'Available'로 원복)
        passengers = Passenger.query.filter_by(Booking_ID=booking_id).all()
        seat_ids_to_free = [(p.Flight_ID, p.Seat_ID) for p in passengers]
        
        for flight_id, seat_id in seat_ids_to_free:
            fsa = Flight_Seat_Availability.query.get((flight_id, seat_id))
            if fsa and fsa.Availability_Status == 'Reserved':
                fsa.Availability_Status = 'Available'
        
        db.session.commit()
        flash(f'예약 번호 {booking_id}이(가) 성공적으로 취소되었습니다.')
        
    except Exception as e:
        db.session.rollback()
        flash(f'예약 취소 중 오류가 발생했습니다: {e}')
        return redirect(url_for('reservation.details', booking_id=booking_id))

    return redirect(url_for('reservation.index'))