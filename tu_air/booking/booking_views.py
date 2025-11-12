# TU_Air/tu_air/booking/booking_views.py
# (!!! 새 파일 !!!)

from . import booking_bp
from ..extensions import db
from ..models import Flight, Member, Guest, Airport, Seat, Flight_Seat_Availability, Booking, Passenger, Payment
from flask import render_template, request, flash, redirect, url_for, jsonify, session, g
import datetime
from functools import wraps
import re # (좌석 번호 파싱을 위해 추가)
import random # (!!! 1. random 임포트 추가 !!!)
import string # (!!! 2. string 임포트 추가 !!!)


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
                
                # (날짜 변환은 finalize에서 수행, 세션에는 문자열로 저장)
                guest_details = {
                    "name": guest_name,
                    "nationality": guest_nationality,
                    "dob_year": guest_dob_year,
                    "dob_month": guest_dob_month,
                    "dob_day": guest_dob_day,
                    "email": guest_email,
                    "phone": guest_phone
                }
                session['pending_booking']['guest_details'] = guest_details

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
                    "dob_str": form_dob.isoformat(),
                    "member_id": member_id_to_save
                })

            # (TODO: 이 passenger_details 리스트를 사용하여
            #  Booking 생성 -> Booking_ID 획득 -> Passenger 테이블에 INSERT...)

            session['pending_booking']['passengers'] = passenger_details
            session.modified = True # (세션 딕셔너리 내부 변경 알림)
            
            return redirect(url_for('booking.select_seat', direction='outbound'))
        
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

# [!!!] (신규) 좌석 선택 페이지 뷰 (GET/POST) [!!!]
@booking_bp.route('/seat', methods=['GET', 'POST'])
def select_seat():
    """ (신규) 좌석 선택 페이지 """
    
    # 1. 세션 정보 로드
    booking_info = session.get('pending_booking')
    if not booking_info or 'passengers' not in booking_info:
        flash('탑승객 정보를 먼저 입력해 주세요.')
        return redirect(url_for('booking.passenger_info'))

    # (GET/POST 모두에서 현재 방향(direction)을 확인)
    if request.method == 'POST':
        direction = request.form.get('direction', 'outbound')
    else:
        direction = request.args.get('direction', 'outbound')

    # (세션에서 이 방향에 맞는 비행 ID와 좌석 등급을 가져옴)
    is_round_trip = booking_info.get('inbound_flight_id') is not None
    seat_class = booking_info.get('seat_class') # (예: 'Economy')
    outbound_flight_id = booking_info.get('outbound_flight_id')
    inbound_flight_id = booking_info.get('inbound_flight_id')
    
    # [!!!] (수정) 2. 탭 UI를 위해 *모든* 항공편 객체 로드 [!!!]
    outbound_flight = Flight.query.get(outbound_flight_id)
    inbound_flight = Flight.query.get(inbound_flight_id) if is_round_trip else None
    
    if direction == 'inbound':
        current_flight_id = inbound_flight_id
        current_flight = inbound_flight
    else:
        current_flight_id = outbound_flight_id
        current_flight = outbound_flight
        
    if not current_flight:
        flash('선택한 항공편 정보가 없습니다.')
        return redirect(url_for('main.home'))
    
    # 2. POST (좌석 선택 완료)
    if request.method == 'POST':
        selected_seats = request.form.getlist('selected_seat') # (JS가 채워줄 hidden input)
        passengers = booking_info.get('passengers', [])

        if len(selected_seats) != len(passengers):
            flash('모든 탑승객의 좌석을 선택해야 합니다.')
            return redirect(url_for('booking.select_seat', direction=direction))
        
        # (세션에 이 방향의 좌석 선택 결과 저장)
        if direction == 'outbound':
            session['pending_booking']['outbound_seats'] = selected_seats
        else:
            session['pending_booking']['inbound_seats'] = selected_seats
        
        session.modified = True

        # (다음 단계로 이동)
        if is_round_trip and direction == 'outbound':
            # (왕복이고 '가는 편'이 끝났으면 -> '오는 편'으로)
            return redirect(url_for('booking.select_seat', direction='inbound'))
        else:
            # [!!!] (수정) (편도이거나, 왕복의 '오는 편'이 끝났으면 -> '예약 확인' 페이지로) [!!!]
            return redirect(url_for('booking.review_booking'))
            
            # (임시: DB 저장 로직)
            # (TODO: 
            #  1. DB 트랜잭션 시작
            #  2. Booking 테이블 INSERT
            #  3. Passenger 테이블 INSERT (세션 정보 + outbound_seats/inbound_seats)
            #  4. Payment 테이블 INSERT (결제)
            #  5. flight_seat_availability 상태 'Reserved'로 UPDATE
            #  6. 트랜잭션 커밋)

    # 3. GET (좌석 맵 페이지 로드)
    
    # (DB에서 이 항공편의 모든 좌석 정보와 상태를 가져옴)
    # (Seat.Seat_No가 '1A', '10K' 등 위치 정보를 포함한다고 가정)
    # [!!!] (수정) 쿼리 변경: Seat.Class를 함께 조회 [!!!]
    seat_query = db.session.query(
            Seat.Seat_ID, Seat.Seat_No, Seat.Class, 
            Flight_Seat_Availability.Availability_Status
        ).join(
            Flight_Seat_Availability, Seat.Seat_ID == Flight_Seat_Availability.Seat_ID
        ).filter(
            Flight_Seat_Availability.Flight_ID == current_flight_id
        )
    
    all_seats = seat_query.all()

    # (가져온 데이터를 템플릿이 쓰기 좋은 '행(Row)' 기반 딕셔너리로 가공)
    # 예: seat_map = {1: [{'no': '1A', ...}, {'no': '1K', ...}], 10: [...]}
    seat_map = {}
    seat_cols = set() # (모든 컬럼명, 예: 'A', 'D', 'K')
    
    for seat in all_seats:
        # (정규식으로 '10A' -> '10'과 'A'로 분리)
        match = re.match(r'(\d+)([A-Z])$', seat.Seat_No)
        if not match: 
            continue # (유효하지 않은 좌석 번호)
            
        row_num_str = match.group(1)
        col_char = match.group(2)
        
        row_num = int(row_num_str)
        seat_cols.add(col_char)
        
        if row_num not in seat_map:
            seat_map[row_num] = []
            
        seat_map[row_num].append({
            "id": seat.Seat_ID,
            "col": col_char,
            "status": seat.Availability_Status, # ('Available', 'Reserved', 'Unavailable')
            "class": seat.Class
        })

    # (컬럼명 정렬, 예: A, D, E, F, G, K)
    sorted_cols = sorted(list(seat_cols))
    # (행 번호 정렬)
    sorted_rows = sorted(seat_map.keys())

    # (템플릿에 전달할 최종 데이터)
    final_seat_map = {
        "columns": sorted_cols, # ['A', 'D', 'E', 'F', 'G', 'K']
        "rows": sorted_rows,    # [1, 2, 3, 4, 5, 6, 7]
        "seats": seat_map       # {1: [{'id': ...}, ...], ...}
    }
    
    # (세션에서 탑승객 정보 가져오기)
    passengers = booking_info.get('passengers', [])

    # [!!!] (R1) (신규) 3b. 세션에서 *이미 선택한* 좌석 정보 로드 [!!!]
    existing_selections = {}
    saved_seat_ids = []
    
    if direction == 'outbound' and 'outbound_seats' in booking_info:
        saved_seat_ids = booking_info['outbound_seats']
    elif direction == 'inbound' and 'inbound_seats' in booking_info:
        saved_seat_ids = booking_info['inbound_seats']

    # (JS가 사용할 딕셔너리 형태로 재생성)
    for i in range(len(passengers)):
        if i < len(saved_seat_ids) and saved_seat_ids[i]:
            seat_id = saved_seat_ids[i]
            seat_obj = Seat.query.get(seat_id) # (DB 조회)
            if seat_obj:
                existing_selections[str(i)] = {'id': seat_obj.Seat_ID, 'no': seat_obj.Seat_No}
            else:
                existing_selections[str(i)] = None
        else:
            existing_selections[str(i)] = None
    
    # (3c. 템플릿 렌더링)
    return render_template('select_seat.html', 
                           current_flight=current_flight, 
                           outbound_flight=outbound_flight, 
                           inbound_flight=inbound_flight,   
                           passengers=passengers,
                           seat_map=final_seat_map,
                           seat_class=seat_class, 
                           direction=direction,
                           booking_info=booking_info,
                           existing_selections=existing_selections) # (!!! 추가 !!!)

# [!!!] (신규) 4. 예약 확인 페이지 (GET) [!!!]
@booking_bp.route('/review', methods=['GET'])
def review_booking():
    """ 예약 확인(Review) 페이지. 결제 전 최종 정보를 보여줍니다. """
    
    booking_info = session.get('pending_booking')
    if not booking_info:
        flash('예약 정보가 없습니다.')
        return redirect(url_for('main.home'))

    # (세션의 ID들로 DB에서 실제 객체/정보 로드)
    passengers = booking_info.get('passengers', [])
    outbound_flight = Flight.query.get(booking_info['outbound_flight_id'])
    outbound_seats_ids = booking_info.get('outbound_seats', [])
    # (좌석 ID 리스트로 좌석 번호(Seat_No) 리스트 조회)
    outbound_seats_nos = [Seat.query.get(sid).Seat_No for sid in outbound_seats_ids]
    
    inbound_flight = None
    inbound_seats_nos = []
    if booking_info.get('inbound_flight_id'):
        inbound_flight = Flight.query.get(booking_info['inbound_flight_id'])
        inbound_seats_ids = booking_info.get('inbound_seats', [])
        inbound_seats_nos = [Seat.query.get(sid).Seat_No for sid in inbound_seats_ids]

    return render_template('review_booking.html',
                           booking_info=booking_info,
                           passengers=passengers,
                           outbound_flight=outbound_flight,
                           outbound_seats=outbound_seats_nos,
                           inbound_flight=inbound_flight,
                           inbound_seats=inbound_seats_nos,
                           is_guest=session.get('is_guest', False))

# [!!!] (신규) 3. 예약 번호 생성 헬퍼 함수 (finalize_booking 위에 추가) [!!!]
def generate_unique_booking_id(length=15):
    """
    요청사항: 15자리의 영문 대문자(A-Z)와 숫자(0-9)로 구성된
    중복되지 않는 랜덤 예약 번호를 생성합니다.
    """
    characters = string.ascii_uppercase + string.digits
    while True:
        # (1. 15자리 랜덤 문자열 생성)
        new_id = ''.join(random.choice(characters) for _ in range(length))
        
        # (2. DB의 Booking 테이블에 이 ID가 이미 있는지 확인)
        if not Booking.query.get(new_id):
            # (3. 없으면 (unique하면) 이 ID를 반환)
            return new_id

# [!!!] (신규) 5. 최종 결제 및 DB 저장 (POST) [!!!]
@booking_bp.route('/finalize', methods=['POST'])
def finalize_booking():
    """ '결제' 버튼 클릭 시 호출. DB에 모든 정보를 저장. """
    
    booking_info = session.get('pending_booking')
    if not booking_info:
        flash('예약 정보가 만료되었습니다.')
        return redirect(url_for('main.home'))
    
    is_guest_booking = session.get('is_guest', False)

    try:
        guest_id_to_save = None
        
        # [!!!] (R3) 1. (비회원일 경우) Guest 테이블 INSERT [!!!]
        if is_guest_booking:
            guest_data = booking_info.get('guest_details')
            if not guest_data:
                raise Exception("비회원 예약자 정보가 세션에 없습니다.")
            
            guest_dob = datetime.date(
                int(guest_data['dob_year']), 
                int(guest_data['dob_month']), 
                int(guest_data['dob_day'])
            )
            
            new_guest = Guest(
                Name=guest_data['name'],
                Nationality=guest_data['nationality'],
                Date_OF_Birth=guest_dob,
                Email=guest_data['email'],
                Phone=guest_data['phone']
            )
            db.session.add(new_guest)
            # (DB에 flush하여 auto-increment된 Guest_ID를 미리 가져옴)
            db.session.flush()
            guest_id_to_save = new_guest.Guest_ID

        # (2. Booking 테이블 INSERT)
        new_booking_id = generate_unique_booking_id(15)
        new_booking = Booking(
            Booking_ID=new_booking_id,
            Member_ID=g.user.Member_ID if g.user and not session.get('is_guest', False) else None,
            Guest_ID=None, # (TODO: 비회원 예약자 정보 저장 시 ID 연결)
            Outbound_Flight_ID=booking_info['outbound_flight_id'],
            Return_Flight_ID=booking_info.get('inbound_flight_id'),
            Booking_Date=datetime.datetime.now(),
            Status='Reserved', # (요청사항)
            Passenger_num=booking_info['passenger_count']
        )
        db.session.add(new_booking)

        # (2. Passenger 테이블 INSERT)
        passengers_data = booking_info.get('passengers', [])
        outbound_seats = booking_info.get('outbound_seats', [])
        
        for i, pax_data in enumerate(passengers_data):
            # (R4: 마일리지 계산)
            mileage_to_earn_out = 0.0
            if pax_data.get('member_id'): # (회원 ID가 검증되었으면)
                mileage_to_earn_out = booking_info['outbound_price'] * 0.10
            pax_out = Passenger(
                Booking_ID=new_booking_id,
                Flight_ID=booking_info['outbound_flight_id'],
                Seat_ID=outbound_seats[i],
                Gender=pax_data['gender'],
                Name=pax_data['name'],
                Date_OF_Birth=datetime.date.fromisoformat(pax_data['dob_str']),
                Mileage_Earned=mileage_to_earn_out # (계산된 마일리지)
            )
            db.session.add(pax_out)

        # (왕복일 경우 오는 편도 저장)
        if booking_info.get('inbound_flight_id'):
            inbound_seats = booking_info.get('inbound_seats', [])
            for i, pax_data in enumerate(passengers_data):
                mileage_to_earn_in = 0.0
                if pax_data.get('member_id'):
                    mileage_to_earn_in = booking_info['inbound_price'] * 0.10
                pax_in = Passenger(
                    Booking_ID=new_booking_id,
                    Flight_ID=booking_info['inbound_flight_id'],
                    Seat_ID=inbound_seats[i],
                    Gender=pax_data['gender'],
                    Name=pax_data['name'],
                    Date_OF_Birth=datetime.date.fromisoformat(pax_data['dob_str']),
                    Mileage_Earned=mileage_to_earn_in # (계산된 마일리지)
                )
                db.session.add(pax_in)

        # (3. Payment 테이블 INSERT)
        new_payment = Payment(
            Booking_ID=new_booking_id,
            Amount=booking_info['total_price'],
            Payment_Date=datetime.datetime.now(),
            status='Paid' # (결제 성공으로 간주)
        )
        db.session.add(new_payment)

        # (4. Flight_Seat_Availability 테이블 UPDATE)
        for seat_id in outbound_seats:
            seat_to_update = Flight_Seat_Availability.query.get((booking_info['outbound_flight_id'], seat_id))
            if seat_to_update and seat_to_update.Availability_Status == 'Available':
                seat_to_update.Availability_Status = 'Reserved' # (요청사항)
            else:
                raise Exception(f"좌석 {seat_id}를 예약할 수 없습니다.") # (중복 예약 방지)
        
        if booking_info.get('inbound_flight_id'):
            inbound_seats = booking_info.get('inbound_seats', [])
            for seat_id in inbound_seats:
                seat_to_update = Flight_Seat_Availability.query.get((booking_info['inbound_flight_id'], seat_id))
                if seat_to_update and seat_to_update.Availability_Status == 'Available':
                    seat_to_update.Availability_Status = 'Reserved'
                else:
                    raise Exception(f"좌석 {seat_id}를 예약할 수 없습니다.")
        
        # (5. DB 커밋)
        db.session.commit()
        
        # (6. 세션 정리)
        session.pop('pending_booking', None)
        session.pop('is_guest', None)
        
        if is_guest_booking:
            # (R1, R2) 비회원은 예약 완료 페이지로 (예약 번호 전달)
            return redirect(url_for('booking.booking_complete', booking_id=new_booking_id))
        else:
            # (회원은 마이페이지로)
            flash('항공권 예약 및 결제가 성공적으로 완료되었습니다.')
            return redirect(url_for('mypage.mypage'))

    except Exception as e:
        db.session.rollback() # (오류 발생 시 모든 작업 롤백)
        flash(f'예약 처리 중 심각한 오류가 발생했습니다: {e}')
        return redirect(url_for('booking.review_booking'))
    
# [!!!] (신규) 6. 비회원 예약 완료 페이지 (GET) [!!!]
@booking_bp.route('/complete/<string:booking_id>', methods=['GET'])
def booking_complete(booking_id):
    """ (R1, R2) 비회원 예약 완료 시 예약 번호와 메시지를 보여줍니다. """
    
    booking = Booking.query.get(booking_id)
    if not booking:
        # (잘못된 접근 시, 예약 번호 없이 페이지만 표시)
        return render_template('booking_complete.html', booking_id=None)
        
    return render_template('booking_complete.html', booking_id=booking.Booking_ID)
