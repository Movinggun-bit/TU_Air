# TU_Air/create_staff_accounts.py
# 테스트용 직원 계정 생성 스크립트

from tu_air import create_app
from tu_air.extensions import db
from tu_air.models import Staff

def create_test_staff():
    """테스트용 직원 계정 생성"""
    app = create_app()
    
    with app.app_context():
        # 기존 직원이 있는지 확인
        existing_staff = Staff.query.first()
        if existing_staff:
            print("이미 직원 데이터가 존재합니다.")
            print("기존 직원 목록:")
            all_staff = Staff.query.all()
            for staff in all_staff:
                print(f"  - {staff.Staff_ID} ({staff.Name}, {staff.Role})")
            return
        
        # 테스트용 직원 계정 생성
        test_staff = [
            {'Staff_ID': 'pilot001', 'Passwd': 'pilot123', 'Name': '김파일럿', 'Role': 'Pilot', 'Department': '운항팀'},
            {'Staff_ID': 'copilot001', 'Passwd': 'copilot123', 'Name': '이코파일럿', 'Role': 'Co-Pilot', 'Department': '운항팀'},
            {'Staff_ID': 'cabin001', 'Passwd': 'cabin123', 'Name': '박승무원', 'Role': 'Cabin Crew', 'Department': '서비스팀'},
            {'Staff_ID': 'engineer001', 'Passwd': 'engineer123', 'Name': '최엔지니어', 'Role': 'Engineer', 'Department': '정비팀'},
            {'Staff_ID': 'ground001', 'Passwd': 'ground123', 'Name': '정그라운드', 'Role': 'Ground Staff', 'Department': '지상팀'},
            {'Staff_ID': 'hr001', 'Passwd': 'hr123', 'Name': '강인사', 'Role': 'HR', 'Department': '인사팀'},
            {'Staff_ID': 'scheduler001', 'Passwd': 'schedule123', 'Name': '윤스케줄러', 'Role': 'Scheduler', 'Department': '운영팀'},
            {'Staff_ID': 'ceo001', 'Passwd': 'ceo123', 'Name': '임대표', 'Role': 'CEO', 'Department': '경영진'},
            {'Staff_ID': 'marketer001', 'Passwd': 'market123', 'Name': '한마케터', 'Role': 'marketer', 'Department': '마케팅팀'},
        ]
        
        try:
            for staff_data in test_staff:
                staff = Staff(
                    Staff_ID=staff_data['Staff_ID'],
                    Passwd=staff_data['Passwd'],
                    Name=staff_data['Name'],
                    Role=staff_data['Role'],
                    Department=staff_data['Department']
                )
                db.session.add(staff)
            
            db.session.commit()
            print("=" * 60)
            print("테스트용 직원 계정이 생성되었습니다!")
            print("=" * 60)
            print("\n생성된 직원 계정:")
            print("-" * 60)
            for staff_data in test_staff:
                print(f"직업: {staff_data['Role']:15} | ID: {staff_data['Staff_ID']:15} | 비밀번호: {staff_data['Passwd']}")
            print("-" * 60)
            print("\n로그인 방법:")
            print("1. 로그인 페이지에서 '직원 로그인' 라디오 버튼 선택")
            print("2. 위의 ID와 비밀번호로 로그인")
            print("=" * 60)
            
        except Exception as e:
            db.session.rollback()
            print(f"오류 발생: {e}")

if __name__ == '__main__':
    create_test_staff()

