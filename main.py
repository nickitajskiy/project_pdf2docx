import tkinter as tk
from tkinter import filedialog as fd
from pdf2docx import parse
import pathlib

root = tk.Tk()
root.title("Конвертер PDF в DOCX")
root.geometry("500x500+480+180")
root.resizable(width=False, height=False)
root['bg'] = "white"

root.mainloop()