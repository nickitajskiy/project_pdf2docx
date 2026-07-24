import tkinter as tk
from tkinter import filedialog as fd
from pdf2docx import parse
import pathlib

root = tk.Tk()
root.title("Конвертер PDF в DOCX")
root.geometry("500x500+480+180")
root.resizable(width=False, height=False)
root['bg'] = "white"

def callback():
    name = fd.askopenfilename()
    ePath.config(state='normal')
    ePath.delete('1', tk.END)
    ePath.insert('1', name)
    ePath.config(state='readonly')

def convert():
    pdf_file = ePath.get()
    docx_file = pathlib.Path(pdf_file)
    docx_file = docx_file.stem + '.docx'
    parse(pdf_file, docx_file)
    tk.Label(root, text='Конвертация завершена', fg='white', bg='black', font='Arial 15 bold').pack(pady=10)




tk.Button(root, text='Выбрать PDF файл', font='Arial 15 bold',
          fg='black', bg='white', command=callback).pack(pady=15)

lbPath = tk.Label(root, text='Путь к файлу:', font='Arial 15 bold',
                  fg='black', bg='white')
lbPath.pack()

ePath = tk.Entry(root, width=50, state='readonly')
ePath.pack(pady=15)

btnConvert = tk.Button(root, text='Конвертировать', font='Arial 15 bold',
                       fg='black', bg='white', command=convert)
btnConvert.pack(pady=15)



root.mainloop()