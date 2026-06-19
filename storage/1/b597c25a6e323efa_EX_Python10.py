import random
Count = 0
MyNum = 0
RandomNum = random.randint(1,9)
while MyNum != RandomNum:
    MyNum = int(input("ทายตัวเลข : "))
    Count = Count+1
print("ทายถูกต้อง! คุณได้ทายตัวเลขไป :",Count, "ครั้ง")
print("ตัวเลขที่ถูกต้องคือ ", RandomNum)