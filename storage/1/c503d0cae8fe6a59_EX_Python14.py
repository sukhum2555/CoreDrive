Score_Stu = []
for i in range(10):
    print("คะแนนคนที่",i+1,end='')
    Score_Stu.append(int(input("= ")))
print(Score_Stu)

Grade_Stu = []
for i in range(10):
    if Score_Stu[i] >= 80:
        Grade_Stu.append('A')
    elif Score_Stu[i] >= 70:
        Grade_Stu.append('B')
    elif Score_Stu[i] >= 60:
        Grade_Stu.append('C')
    elif Score_Stu[i] >= 50:
        Grade_Stu.append('D')
    else:
        Grade_Stu.append('F')
print(Grade_Stu)

for i in range(10):
    print("นักเรียนคนที่",i+1,"ได้คะแนน",Score_Stu[i],"ได้เกรด",Grade_Stu[i])