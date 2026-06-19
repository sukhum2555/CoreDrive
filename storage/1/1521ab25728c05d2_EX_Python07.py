Num1 = int(input("กรุณาใส่แม่สูตรคูณ : "))
Num2 = int(input("กรุณาใส่จำนวนรอบ : "))
for MT in range(1,Num2+1):
    Ans = Num1 * MT
    print(Num1,"x",MT," = ",Ans)