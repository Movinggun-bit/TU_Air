from tu_air import create_app
from tu_air.extensions import db
from tu_air.models import Staff

def insert_staff_data():
    app = create_app()
    app.app_context().push()

    # 샘플 데이터
    staff_data = [
        {"Staff_ID": "P001", "Passwd": "password1", "Name": "김기장", "Role": "Pilot", "Department": "Flight"},
        {"Staff_ID": "CP001", "Passwd": "password2", "Name": "이부기장", "Role": "Co-Pilot", "Department": "Flight"},
        {"Staff_ID": "CC001", "Passwd": "password3", "Name": "박승무원", "Role": "Cabin Crew", "Department": "Cabin"},
        {"Staff_ID": "CC002", "Passwd": "password4", "Name": "최승무원", "Role": "Cabin Crew", "Department": "Cabin"}
    ]

    for staff in staff_data:
        if not Staff.query.get(staff["Staff_ID"]):
            new_staff = Staff(
                Staff_ID=staff["Staff_ID"],
                Passwd=staff["Passwd"],
                Name=staff["Name"],
                Role=staff["Role"],
                Department=staff["Department"]
            )
            db.session.add(new_staff)

    db.session.commit()
    print("샘플 직원 데이터가 성공적으로 추가되었습니다.")

if __name__ == "__main__":
    insert_staff_data()