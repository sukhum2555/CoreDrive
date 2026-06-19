Check = True
iSum = 0
while Check:
    Num_n = int(input("ป้อนค่าตัวเลข : "))
    iSum = iSum + Num_n
    print(iSum)
    Str = input("กดปุ่ม y เพื่อป้อนค่าต่อ // กดปุ่มใดๆเพื่อออก : ")
    if Str != 'y':
        Check = False
print("ค่าของ iSum = ",iSum)