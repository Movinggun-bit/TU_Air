# TU_Air/check_staff_data.py
# Staff 데이터 확인 스크립트

from tu_air import create_app
from tu_air.extensions import db
from tu_air.models import Staff

def check_staff():
    """Staff 데이터 확인"""
    app = create_app()
    
    with app.app_context():
        try:
            all_staff = Staff.query.all()
            
            if not all_staff:
                print("=" * 60)
                print("⚠️  Staff 데이터가 없습니다!")
                print("=" * 60)
                print("\n다음 중 하나를 실행하세요:")
                print("1. python create_staff_accounts.py")
                print("2. MySQL에서 insert_staff_data.sql 실행")
                print("=" * 60)
            else:
                print("=" * 60)
                print(f"✅ Staff 데이터가 {len(all_staff)}개 있습니다.")
                print("=" * 60)
                print("\n등록된 직원 목록:")
                print("-" * 60)
                for staff in all_staff:
                    print(f"ID: {staff.Staff_ID:15} | 이름: {staff.Name:10} | 직업: {staff.Role:15} | 비밀번호: {staff.Passwd}")
                print("-" * 60)
                print("\n로그인 테스트:")
                print("1. 로그인 페이지에서 '직원 로그인' 라디오 버튼 선택")
                print("2. 위의 ID와 비밀번호로 로그인")
                print("=" * 60)
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            print("\n데이터베이스 연결을 확인하세요.")

if __name__ == '__main__':
    check_staff()

