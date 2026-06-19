import random
Count = 0
MyNum = 0
Check = True
RandomNum = random.randint(1,9)
while Check:
    MyNum = int(input("ทายตัวเลข : "))
    Count = Count+1
    if MyNum == RandomNum:
        Check = False
print("ทายถูกต้อง! คุณได้ทายตัวเลขไป :",Count, "ครั้ง")
print("ตัวเลขที่ถูกต้องคือ ", RandomNum)