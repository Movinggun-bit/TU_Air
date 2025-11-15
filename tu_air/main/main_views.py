# TU_Air/tu_air/main/main_views.py
# (최종본)

from . import main_bp
from ..extensions import db
from flask import render_template, request, jsonify
from sqlalchemy import text
import datetime

@main_bp.route('/')
def home():
    """홈페이지 (index.html)를 렌더링합니다."""
    return render_template('index.html')

@main_bp.route('/booking')
def booking():
    """
    '항공권 예매' 탭 클릭 시 (booking.html)
    (이 페이지는 검색 폼만 있고, 공항 목록이 필요 없습니다. 
     공항 목록은 index/booking.html의 JS가 /get_airports로 불러옵니다.)
    """
    # (참고: main.js가 /get_airports를 AJAX로 호출하므로,
    #  여기서 airports를 전달할 필요가 없습니다.)
    return render_template('booking.html')

@main_bp.route('/get_airports')
def get_airports():
    """
    공항 선택 모달(AJAX)을 위한 공항 목록을
    '대한민국'과 '대륙별'로 구분하여 JSON으로 반환합니다.
    """
    airports_data = {'korea': [], 'continents': {}}
    try:
        query_korea = text("SELECT Airport_Code, City FROM airport WHERE Country = '대한민국' ORDER BY City")
        result_korea = db.session.execute(query_korea).mappings().fetchall()
        airports_data['korea'] = [dict(row) for row in result_korea]
        
        query_others = text("SELECT Continent, Country, City, Airport_Code FROM airport WHERE Country != '대한민국' ORDER BY Continent, Country, City")
        result_others = db.session.execute(query_others).mappings().fetchall()
        
        for row in result_others:
            continent = row['Continent']
            country = row['Country']
            if continent not in airports_data['continents']:
                airports_data['continents'][continent] = {}
            if country not in airports_data['continents'][continent]:
                airports_data['continents'][continent][country] = []
            airports_data['continents'][continent][country].append({'City': row['City'], 'Airport_Code': row['Airport_Code']})
    
    except Exception as e:
        print(f"--- /get_airports AJAX 오류 ---: {e}")
        return jsonify({"error": str(e)}), 500
        
    return jsonify(airports_data)

@main_bp.route('/search_flights')
def search_flights():
    """
    항공편 검색 로직 (왕복/편도 분리)
    index.html, booking.html, search_results.html의 폼에서 호출됩니다.
    """
    
    # 1. 폼(Form)에서 사용자가 입력한 값 받기 (GET 파라미터)
    trip_type = request.args.get('trip_type')
    dep_airport = request.args.get('departure_airport')
    arr_airport = request.args.get('arrival_airport')
    dep_date_str = request.args.get('departure_date')
    return_date_str = request.args.get('return_date')
    passenger_count_str = request.args.get('passenger_count', '1')
    seat_class = request.args.get('seat_class')

    # (공항 코드로 City 이름을 조회하는 헬퍼 함수)
    def get_city_name(airport_code):
        if not airport_code:
            return ""
        try:
            result = db.session.execute(text("SELECT City FROM airport WHERE Airport_Code = :code"), {"code": airport_code}).scalar()
            return result if result else airport_code
        except Exception:
            return airport_code

    dep_city = get_city_name(dep_airport)
    arr_city = get_city_name(arr_airport)

    # (search_results.html의 상단 폼을 위한 search_info 딕셔너리)
    search_info = {
        "dep_city": dep_city, 
        "arr_city": arr_city,
        "departure_airport_code": dep_airport, 
        "arrival_airport_code": arr_airport,
        "dep_date": dep_date_str, 
        "return_date": return_date_str,
        "passengers": passenger_count_str, 
        "class": seat_class,
        "trip_type": trip_type
    }
    
    try:
        passenger_count = int(passenger_count_str)
        dep_date = datetime.datetime.strptime(dep_date_str, '%Y-%m-%d').date()
        if trip_type == 'round_trip':
            if not return_date_str:
                 return render_template(
                    'search_results.html', 
                    error="왕복 여정은 오는 날을 선택해야 합니다.", 
                    search_info=search_info,
                    flights_outbound=[],
                    flights_inbound=[]
                )
            return_date = datetime.datetime.strptime(return_date_str, '%Y-%m-%d').date()
    except Exception:
        return render_template(
            'search_results.html', 
            error="입력 값이 올바르지 않습니다.", 
            search_info=search_info,
            flights_outbound=[],
            flights_inbound=[]
        )

    
    # 2. 항공편을 조회하는 공통 쿼리 (SQL 함수)
    def fetch_flights(departure_apt, arrival_apt, flight_date, p_count, s_class):
        # ( ... 이 함수 내부는 수정할 필요 없음 ... )
        sql_query = text("""
            SELECT 
                f.Flight_ID, f.Flight_No, f.Departure_Time, f.Arrival_Time,
                fp.Price, sa_sub.available_seats
            FROM flight AS f
            JOIN flight_price AS fp ON f.Flight_ID = fp.Flight_ID AND fp.Class = :seat_class
            JOIN (
                SELECT 
                    fsa.Flight_ID, s.Class, COUNT(fsa.Seat_ID) AS available_seats
                FROM flight_seat_availability AS fsa
                JOIN seat AS s ON fsa.Seat_ID = s.Seat_ID
                WHERE fsa.Availability_Status = 'Available'
                GROUP BY fsa.Flight_ID, s.Class
            ) AS sa_sub ON f.Flight_ID = sa_sub.Flight_ID AND sa_sub.Class = :seat_class
            WHERE 
                f.Departure_Airport_Code = :dep_airport
                AND f.Arrival_Airport_Code = :arr_airport
                AND DATE(f.Departure_Time) = :flight_date
                AND sa_sub.available_seats >= :passenger_count
                AND f.Flight_Status = 'On_Time'
            ORDER BY 
                f.Departure_Time;
        """)
        params = {"seat_class": s_class, "dep_airport": departure_apt, "arr_airport": arrival_apt, "flight_date": flight_date, "passenger_count": p_count}
        result = db.session.execute(sql_query, params).mappings().fetchall()
        return [dict(row) for row in result]

    # 3. 왕복 / 편도 분기 처리
    try:
        flights_outbound = []
        flights_inbound = []

        flights_outbound = fetch_flights(dep_airport, arr_airport, dep_date, passenger_count, seat_class)

        if trip_type == 'round_trip':
            flights_inbound = fetch_flights(arr_airport, dep_airport, return_date, passenger_count, seat_class)

        # (모든 검사 통과 - 성공)
        return render_template(
            'search_results.html', 
            flights_outbound=flights_outbound,
            flights_inbound=flights_inbound,
            search_info=search_info,
            error=None
        )

    except Exception as e:
        # (SQL 쿼리 자체의 문법 오류 등 심각한 에러 발생 시)
        print(f"--- 항공편 검색 쿼리 오류 ---: {e}")
        return render_template(
            'search_results.html', 
            error="항공편 조회 중 오류가 발생했습니다.", 
            search_info=search_info,
            flights_outbound=[],
            flights_inbound=[]
        )

    
    # 2. 항공편을 조회하는 공통 쿼리 (SQL 함수)
    def fetch_flights(departure_apt, arrival_apt, flight_date, p_count, s_class):
        """
        복잡한 SQL 쿼리를 실행하여,
        요청한 인원수(p_count)보다 'Available' 좌석이 많은 항공편을 조회합니다.
        """
        sql_query = text("""
            SELECT 
                f.Flight_ID, f.Flight_No, f.Departure_Time, f.Arrival_Time,
                fp.Price, sa_sub.available_seats
            FROM flight AS f
            JOIN flight_price AS fp ON f.Flight_ID = fp.Flight_ID AND fp.Class = :seat_class
            JOIN (
                SELECT 
                    fsa.Flight_ID, s.Class, COUNT(fsa.Seat_ID) AS available_seats
                FROM flight_seat_availability AS fsa
                JOIN seat AS s ON fsa.Seat_ID = s.Seat_ID
                WHERE fsa.Availability_Status = 'Available'
                GROUP BY fsa.Flight_ID, s.Class
            ) AS sa_sub ON f.Flight_ID = sa_sub.Flight_ID AND sa_sub.Class = :seat_class
            WHERE 
                f.Departure_Airport_Code = :dep_airport
                AND f.Arrival_Airport_Code = :arr_airport
                AND DATE(f.Departure_Time) = :flight_date
                AND sa_sub.available_seats >= :passenger_count
                AND f.Flight_Status = 'On_Time'
            ORDER BY 
                f.Departure_Time;
        """)
        
        params = {
            "seat_class": s_class, 
            "dep_airport": departure_apt,
            "arr_airport": arrival_apt, 
            "flight_date": flight_date,
            "passenger_count": p_count
        }
        result = db.session.execute(sql_query, params).mappings().fetchall()
        return [dict(row) for row in result]

    # 3. 왕복 / 편도 분기 처리
    try:
        flights_outbound = []
        flights_inbound = []

        # (1) 가는 편 조회
        flights_outbound = fetch_flights(dep_airport, arr_airport, dep_date, passenger_count, seat_class)

        if trip_type == 'round_trip':
            # (2) 왕복일 경우, 오는 편도 조회 (출발/도착지 반대로)
            flights_inbound = fetch_flights(arr_airport, dep_airport, return_date, passenger_count, seat_class)
            
            # (왕복일 때는 둘 다 없어야 '결과 없음' 처리 - 한 쪽만 없어도 일단 보여줌)
            if not flights_outbound and not flights_inbound:
                 return render_template(
                    'search_results.html', 
                    error="선택하신 날짜에 왕복 항공편이 없습니다.",
                    search_info=search_info
                 )
        
        # (편도일 경우)
        elif not flights_outbound:
             return render_template(
                'search_results.html', 
                error="선택하신 날짜에 항공편이 없습니다.",
                search_info=search_info
             )

        # 4. 검색 결과 페이지로 렌더링 (성공)
        return render_template(
            'search_results.html', 
            flights_outbound=flights_outbound,
            flights_inbound=flights_inbound,
            search_info=search_info
        )

    except Exception as e:
        # (SQL 쿼리 자체의 문법 오류 등 심각한 에러 발생 시)
        print(f"--- 항공편 검색 쿼리 오류 ---: {e}")
        return render_template(
            'search_results.html', 
            error="항공편 조회 중 오류가 발생했습니다.", 
            search_info=search_info
        )