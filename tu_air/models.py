# TU_Air/tu_air/models.py
# (파일 전체를 덮어쓰세요)

from .extensions import db
# (Member, Staff의 해시 함수는 사용자의 이전 요청에 따라 제거된 상태입니다)

class Member(db.Model):
    __tablename__ = 'member'
    Member_ID = db.Column(db.String(20), primary_key=True)
    passwd = db.Column(db.String(20), nullable=False) 
    Name = db.Column(db.String(25), nullable=False)
    eng_Name = db.Column(db.String(30), nullable=False)
    Nationality = db.Column(db.String(20), nullable=False)
    Date_OF_Birth = db.Column(db.DATE, nullable=False)
    Phone = db.Column(db.String(20), nullable=False)
    Email = db.Column(db.String(30), nullable=False)
    mileage = db.Column(db.DECIMAL(10, 2), nullable=False, default=0.00)

    # --- [관계 설정 1] ---
    # Member(1)가 Booking(N)을 가질 수 있습니다.
    # 'bookings'라는 이름으로 Member의 예약 목록을 불러올 수 있습니다.
    bookings = db.relationship('Booking', back_populates='member', lazy=True)

    def __repr__(self):
        return f"<Member {self.Member_ID} ({self.Name})>"

class Guest(db.Model):
    __tablename__ = 'guest'
    Guest_ID = db.Column(db.INT, primary_key=True, autoincrement=True)
    Name = db.Column(db.String(25), nullable=False)
    Nationality = db.Column(db.String(20), nullable=False)
    Date_OF_Birth = db.Column(db.DATE, nullable=False)
    Email = db.Column(db.String(30), nullable=False)
    Phone = db.Column(db.String(20), nullable=False)

    # (관계: 1명의 비회원은 N개의 예약을 가질 수 있음)
    bookings = db.relationship('Booking', back_populates='guest', lazy=True)

class Staff(db.Model):
    __tablename__ = 'staff' 
    Staff_ID = db.Column(db.String(15), primary_key=True)
    Passwd = db.Column(db.String(20), nullable=False) 
    Name = db.Column(db.String(25), nullable=False)
    Role = db.Column(db.Enum('Pilot', 'Co-Pilot', 'Cabin Crew', 'Engineer', 'HR', 'Scheduler', 'CEO'), nullable=False)
    Department = db.Column(db.String(50), nullable=True)
    def __repr__(self):
        return f"<Staff {self.Staff_ID} ({self.Name})>"

# --- [신규] Airport 모델 ---
class Airport(db.Model):
    __tablename__ = 'airport'
    Airport_Code = db.Column(db.String(5), primary_key=True)
    City = db.Column(db.String(20), nullable=False)
    Country = db.Column(db.String(20), nullable=False)
    Continent = db.Column(db.String(10), nullable=False)

# --- [신규] Flight 모델 (Airport와 관계 설정) ---
class Flight(db.Model):
    __tablename__ = 'flight'
    Flight_ID = db.Column(db.String(15), primary_key=True)
    Flight_No = db.Column(db.String(10), nullable=False)
    Aircraft_ID = db.Column(db.String(10), nullable=False) # (Aircraft 모델은 생략)
    Departure_Airport_Code = db.Column(db.String(5), db.ForeignKey('airport.Airport_Code'), nullable=False)
    Departure_Time = db.Column(db.DATETIME, nullable=False)
    Arrival_Airport_Code = db.Column(db.String(5), db.ForeignKey('airport.Airport_Code'), nullable=False)
    Arrival_Time = db.Column(db.DATETIME, nullable=False)
    Flight_Status = db.Column(db.Enum('On_Time', 'Delayed', 'Canceled'), nullable=False, default='On_Time')
    
    # --- [관계 설정 2] ---
    # Flight가 Airport를 'departure_airport'와 'arrival_airport'로 참조합니다.
    departure_airport = db.relationship('Airport', foreign_keys=[Departure_Airport_Code])
    arrival_airport = db.relationship('Airport', foreign_keys=[Arrival_Airport_Code])
    seat_availabilities = db.relationship('Flight_Seat_Availability', back_populates='flight')

# --- [신규] Booking 모델 (Member, Flight와 관계 설정) ---
class Booking(db.Model):
    __tablename__ = 'booking'
    Booking_ID = db.Column(db.String(15), primary_key=True)
    Member_ID = db.Column(db.String(20), db.ForeignKey('member.Member_ID'), nullable=True)
    Guest_ID = db.Column(db.INT, db.ForeignKey('guest.Guest_ID'), nullable=True)
    Outbound_Flight_ID = db.Column(db.String(15), db.ForeignKey('flight.Flight_ID'), nullable=False)
    Return_Flight_ID = db.Column(db.String(15), db.ForeignKey('flight.Flight_ID'), nullable=True)
    Booking_Date = db.Column(db.DATETIME, nullable=False)
    Status = db.Column(db.Enum('Reserved', 'Check-In', 'Canceled', 'Partial_Canceled'), nullable=False, default='Reserved')
    Passenger_num = db.Column(db.INT, nullable=False)

    # --- [관계 설정 3] ---
    # Booking(N)이 Member(1)에 속합니다.
    member = db.relationship('Member', back_populates='bookings')
    guest = db.relationship('Guest', back_populates='bookings')
    # Booking(1)이 Flight(N)를 참조합니다.
    outbound_flight = db.relationship('Flight', foreign_keys=[Outbound_Flight_ID])
    return_flight = db.relationship('Flight', foreign_keys=[Return_Flight_ID])
    
    # Booking(1)이 Payment(N)와 Passenger(N)를 가집니다.
    payments = db.relationship('Payment', back_populates='booking', lazy=True)
    passengers = db.relationship('Passenger', back_populates='booking', lazy=True)

# (DB 스키마의 오타를 바로잡습니다)
class Passenger(db.Model):
    # [!!!] (수정) 테이블 이름을 'passenger'로 변경 [!!!]
    __tablename__ = 'passenger'
    
    Booking_ID = db.Column(db.String(15), db.ForeignKey('booking.Booking_ID'), primary_key=True)
    Flight_ID = db.Column(db.String(15), db.ForeignKey('flight.Flight_ID'), primary_key=True)
    Seat_ID = db.Column(db.String(25), db.ForeignKey('seat.Seat_ID'), primary_key=True)
    
    Gender = db.Column(db.Enum('M', 'F'), nullable=False)
    Name = db.Column(db.String(30), nullable=False) 
    Date_OF_Birth = db.Column(db.DATE, nullable=False)
    Nationality = db.Column(db.String(20), nullable=True, default=None)
    Passport_No = db.Column(db.String(20), nullable=True, default=None)
    Phone = db.Column(db.String(20), nullable=True, default=None)
    Mileage_Earned = db.Column(db.DECIMAL(10, 2), nullable=True, default=None)

    # --- [관계 설정] ---
    booking = db.relationship('Booking', back_populates='passengers')
    boarding_pass = db.relationship('Boarding_Pass', uselist=False, back_populates='passenger')
    flight = db.relationship('Flight', foreign_keys=[Flight_ID])
    seat = db.relationship('Seat', foreign_keys=[Seat_ID])
    
# --- [신규] Payment 모델 (Booking과 관계 설정) ---
class Payment(db.Model):
    __tablename__ = 'payment'
    Payment_ID = db.Column(db.INT, primary_key=True, autoincrement=True)
    Booking_ID = db.Column(db.String(15), db.ForeignKey('booking.Booking_ID'), nullable=False)
    Amount = db.Column(db.DECIMAL(10, 2), nullable=False)
    Payment_Date = db.Column(db.DATETIME, nullable=False)
    status = db.Column(db.Enum('Paid', 'Refunded'), nullable=False, default='Paid')
    refunded_amount = db.Column(db.DECIMAL(10, 2), nullable=False, default=0.00)
    # --- [관계 설정 5] ---
    booking = db.relationship('Booking', back_populates='payments')

# --- [신규] Boarding_Pass 모델 (Passenger와 관계 설정) ---
class Boarding_Pass(db.Model):
    __tablename__ = 'boarding_pass'
    Booking_ID = db.Column(db.String(15), primary_key=True)
    Flight_ID = db.Column(db.String(15), primary_key=True)
    Seat_ID = db.Column(db.String(25), primary_key=True)
    Boarding_Time = db.Column(db.DATETIME, nullable=False)
    Status = db.Column(db.Enum('Valid', 'Used', 'Canceled'), nullable=False, default='Valid')
    
    # --- [관계 설정 6] ---
    # Boarding_Pass가 Passenger의 복합 키를 참조합니다.
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['Booking_ID', 'Flight_ID', 'Seat_ID'],
            ['passenger.Booking_ID', 'passenger.Flight_ID', 'passenger.Seat_ID']
        ),
    )
    passenger = db.relationship('Passenger', back_populates='boarding_pass')

# --- [신규] Aircraft 모델 ---
class Aircraft(db.Model):
    __tablename__ = 'aircraft'
    Aircraft_ID = db.Column(db.String(10), primary_key=True)
    Model = db.Column(db.String(35), nullable=False)
    Manufacturer = db.Column(db.String(35), nullable=False)
    Seat_Capacity = db.Column(db.INT, nullable=False)
    
    # (관계: 1대의 항공기는 N개의 좌석을 가짐)
    seats = db.relationship('Seat', back_populates='aircraft')

# --- [신규] Seat 모델 (Aircraft와 관계 설정) ---
class Seat(db.Model):
    __tablename__ = 'seat'
    Seat_ID = db.Column(db.String(25), primary_key=True)
    Aircraft_ID = db.Column(db.String(10), db.ForeignKey('aircraft.Aircraft_ID'), nullable=False)
    Seat_No = db.Column(db.String(5), nullable=False)
    Class = db.Column(db.Enum('Economy', 'Business', 'First'), nullable=False)

    # (관계: 1개의 좌석은 1대의 항공기에 속함)
    aircraft = db.relationship('Aircraft', back_populates='seats')
    
    # (관계: 1개의 좌석은 N개의 비행편에서 가용 상태를 가짐)
    flight_availabilities = db.relationship('Flight_Seat_Availability', back_populates='seat')

# --- [신규] Flight_Seat_Availability 모델 (Flight, Seat와 관계 설정) ---
class Flight_Seat_Availability(db.Model):
    __tablename__ = 'flight_seat_availability'
    Flight_ID = db.Column(db.String(15), db.ForeignKey('flight.Flight_ID'), primary_key=True)
    Seat_ID = db.Column(db.String(25), db.ForeignKey('seat.Seat_ID'), primary_key=True)
    Availability_Status = db.Column(db.Enum('Available', 'Reserved', 'Unavailable'), nullable=False, default='Available')

    # (관계: N:1)
    flight = db.relationship('Flight', back_populates='seat_availabilities')
    seat = db.relationship('Seat', back_populates='flight_availabilities')