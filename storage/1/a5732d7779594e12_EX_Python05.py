User = input("Login name : ")
Pass = input("Password : ")
if User == "admin":
    if Pass == "admin1234":
        print("เข้าสู่ระบบสำเร็จ")
    else:
        print("รหัสผ่านผิดพลาด")
else:
    print("ชื่อผู้ใช้ไม่ถูกต้อง")