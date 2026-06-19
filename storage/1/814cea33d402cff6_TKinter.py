import tkinter as tk

def click(event):
    text = event.widget.cget("text")
    if text == "=":
        try:
            result = str(eval(str(entry_var.get())))
            entry_var.set(result)
        except Exception as e:
            entry_var.set("Error")
    elif text == "C":
        entry_var.set("")
    else:
        entry_var.set(entry_var.get() + text)

# สร้างหน้าต่าง
root = tk.Tk()
root.title("เครื่องคิดเลข")
root.geometry("300x400")

# สร้างตัวแปรที่เชื่อมกับ Entry
entry_var = tk.StringVar()

# ช่องแสดงผล
entry = tk.Entry(root, textvar=entry_var, font="Arial 20", justify='right')
entry.pack(fill=tk.BOTH, ipadx=8, pady=10, padx=10)

# ปุ่มต่าง ๆ
button_frame = tk.Frame(root)
button_frame.pack()

# รายการปุ่ม (4x4)
buttons = [
    ['7', '8', '9', '/'],
    ['4', '5', '6', '*'],
    ['1', '2', '3', '-'],
    ['C', '0', '=', '+']
]

# สร้างปุ่ม
for row in buttons:
    row_frame = tk.Frame(button_frame)
    row_frame.pack(expand=True, fill='both')
    for btn_text in row:
        button = tk.Button(row_frame, text=btn_text, font="Arial 18")
        button.pack(side='left', expand=True, fill='both', padx=2, pady=2)
        button.bind("<Button-1>", click)

root.mainloop()