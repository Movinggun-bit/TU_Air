# TU_Air/tu_air/booking/booking_views.py
# (!!! 새 파일 !!!)

from . import booking_bp
from ..extensions import db
from ..models import Flight # (향후 Flight 정보 조회용)
from flask import render_template, request, flash, redirect, url_for, jsonify, session, g
import datetime
from ..models import Member

@booking_bp.route('/select', methods=['POST'])
def select_flights():
    """
    search_results.html 폼에서 요금을 선택한 후 호출됩니다.
    선택 정보를 세션에 저장하고, 로그인 상태에 따라 분기합니다.
    """
    
    # 1. 폼에서 데이터 받기
    passenger_count = int(request.form.get('passenger_count', 1))
    seat_class = request.form.get('seat_class')
    action = request.form.get('action') # (proceed, guest, member_login)
    
    outbound_data = request.form.get('outbound_flight') # (예: "FL001|150000.0")
    inbound_data = request.form.get('inbound_flight')   # (예: "FL002|160000.0" 또는 None)

    # 2. 세션에 저장할 'pending_booking'(임시 예약) 객체 생성
    # (세션은 항상 비우고 시작)
    session.pop('pending_booking', None) 
    
    if not outbound_data:
        flash('가는 편 항공권을 선택해야 합니다.')
        # (TODO: 원래 검색 결과 페이지로 돌아가야 하나, 지금은 홈으로)
        return redirect(url_for('main.home')) 
        
    out_flight_id, out_price = outbound_data.split('|')
    
    pending_booking = {
        "passenger_count": passenger_count,
        "seat_class": seat_class,
        "outbound_flight_id": out_flight_id,
        "outbound_price": float(out_price),
        "inbound_flight_id": None,
        "inbound_price": 0.0,
        "total_price": 0.0
    }

    total_price = float(out_price)

    if inbound_data:
        in_flight_id, in_price = inbound_data.split('|')
        pending_booking["inbound_flight_id"] = in_flight_id
        pending_booking["inbound_price"] = float(in_price)
        total_price += float(in_price)

    pending_booking["total_price"] = total_price * passenger_count

    # 3. 세션에 임시 예약 정보 저장
    session['pending_booking'] = pending_booking
    
    # 4. 로그인 상태에 따라 분기
    
    # (1) 이미 로그인되어 있음 ('탑승객 정보 입력' 클릭)
    if g.user:
        # (TODO: 다음 단계인 '탑승객 정보' 페이지로 리다이렉트)
        return redirect(url_for('booking.passenger_info')) # (임시로 홈으로)

    # (2) 로그인 안 됨
    else:
        # (2a) '비회원으로 진행' 클릭
        if action == 'guest':
            session['is_guest'] = True # (게스트임을 표시)
            # (TODO: 다음 단계인 '탑승객 정보' 페이지로 리다이렉트)
            return redirect(url_for('booking.passenger_info')) # (임시로 홈으로)
        
        # (2b) '회원으로 진행' 클릭
        elif action == 'member_login':
            session['is_guest'] = False
            # (예약 정보를 세션에 들고, 로그인 페이지로 보냄)
            return redirect(url_for('auth.login'))

    return redirect(url_for('main.home'))

@booking_bp.route('/passenger_info', methods=['GET', 'POST'])
def passenger_info():
    """ (신규) 탑승객 정보 입력 페이지 """
    
    # 1. 세션에서 임시 예약 정보 가져오기
    booking_info = session.get('pending_booking')
    if not booking_info:
        flash('항공편을 먼저 선택해 주세요.')
        return redirect(url_for('main.home'))

    is_guest = session.get('is_guest', False)
    if g.user and session.get('user_type') == 'member':
        is_guest = False

    # 2. POST (폼 제출) 처리
    if request.method == 'POST':
        try:
            # (1. 비회원 예약자 정보 - R1)
            if is_guest:
                guest_name = request.form.get('guest_name')
                guest_email = request.form.get('guest_email')
                guest_phone = request.form.get('guest_phone')
                guest_nationality = request.form.get('guest_nationality')
                guest_dob_year = request.form.get('guest_dob_year')
                guest_dob_month = request.form.get('guest_dob_month')
                guest_dob_day = request.form.get('guest_dob_day')
                
                # (비회원 생년월일 조합)
                guest_dob = datetime.date(int(guest_dob_year), int(guest_dob_month), int(guest_dob_day))
                
                # (TODO: 이 정보를 Guest 테이블에 INSERT...)

            # (2. 탑승객 정보 - R3)
            pax_count = booking_info.get('passenger_count', 0)
            
            # (이름을 '성'과 '이름'으로 분리해서 받음)
            pax_surnames_en = request.form.getlist('pax_surname_en')
            pax_given_names_en = request.form.getlist('pax_given_name_en')
            pax_dob_years = request.form.getlist('pax_dob_year')
            pax_dob_months = request.form.getlist('pax_dob_month')
            pax_dob_days = request.form.getlist('pax_dob_day')
            pax_airlines = request.form.getlist('pax_airline') # (새 폼 필드)
            pax_member_ids = request.form.getlist('pax_member_id_text') # (새 폼 필드)

            passenger_details = []
            for i in range(pax_count):
                form_name_en = f"{pax_surnames_en[i].upper()} {pax_given_names_en[i].upper()}"
                form_dob = datetime.date(int(pax_dob_years[i]), int(pax_dob_months[i]), int(pax_dob_days[i]))
                gender = request.form.get(f'pax_gender_{i}')
                member_id_to_save = pax_member_ids[i].strip() if pax_airlines[i] == 'TU_AIR' else None

                # (검증 통과 또는 미입력 시 리스트에 추가)
                passenger_details.append({
                    "gender": gender,
                    "name": form_name_en,
                    "dob": form_dob,
                    "member_id": member_id_to_save
                })

            # (TODO: 이 passenger_details 리스트를 사용하여
            #  Booking 생성 -> Booking_ID 획득 -> Passenger 테이블에 INSERT...)

            # (예약 완료 후 세션 비우기)
            session.pop('pending_booking', None)
            session.pop('is_guest', None)
            
            flash('예약 처리가 완료되었습니다! (결제 기능 구현 필요)')
            return redirect(url_for('mypage.mypage')) # (임시로 마이페이지로)
        
        except Exception as e:
            flash(f'정보 제출 중 오류가 발생했습니다: {e}')
            # (오류 발생 시 폼 페이지 다시 로드)
            return redirect(url_for('booking.passenger_info'))


    # 3. GET (페이지 최초 로드)
    return render_template('passenger_info.html', 
                           booking_info=booking_info, 
                           is_guest=is_guest)

@booking_bp.route('/validate_passenger', methods=['POST'])
def validate_passenger():
    """ (신규) AJAX 요청으로 탑승객 1명의 회원 정보를 검증합니다. """
    data = request.get_json()
    if not data:
        return jsonify({"valid": False, "message": "잘못된 요청입니다."}), 400

    member_id = data.get('member_id', '').strip()
    surname_en = data.get('surname_en', '').upper()
    given_name_en = data.get('given_name_en', '').upper()
    form_name_en = f"{surname_en} {given_name_en}"
    
    try:
        form_dob = datetime.date(
            int(data.get('dob_year')),
            int(data.get('dob_month')),
            int(data.get('dob_day'))
        )
    except Exception:
        return jsonify({"valid": False, "message": "생년월일 형식이 올바르지 않습니다."}), 400

    # (DB 검증)
    member = Member.query.get(member_id)

    if not member:
        return jsonify({"valid": False, "message": f"회원 아이디 '{member_id}'를 찾을 수 없습니다."})

    if member.eng_Name != form_name_en or member.Date_OF_Birth != form_dob:
        return jsonify({
            "valid": False, 
            "message": f"입력한 정보(영문 이름, 생년월일)가 회원 아이디 '{member_id}'의 정보와 일치하지 않습니다."
        })

    # (모두 통과)
    return jsonify({"valid": True})