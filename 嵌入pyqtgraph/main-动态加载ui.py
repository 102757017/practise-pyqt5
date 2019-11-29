#!/usr/bin/python
# -*- coding: UTF-8 -*-
from PyQt5 import  QtWidgets
import sys
from PyQt5.uic import loadUi
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import numpy as np
import pyqtgraph as pg


class MainWindow(QtWidgets.QMainWindow):
    
    def __init__(self, parent=None):
	    super(MainWindow, self).__init__(parent)
	    loadUi('form1.ui', self)

            #由于在QT Designer中已经将self.graphicsView已经将graphicsView提升为PlotWidget，因graphicsView此可以继承PlotWidget的plot()对象
	    self.pg1=self.graphicsView.plot()
	    #设置画笔的颜色
	    self.pg1.setPen((200,200,100))
		

	    # 将按钮点击事件和calc槽函数绑定
	    self.pushButton.clicked.connect(self.show_table)
		
    # 定义槽函数
    def show_table(self):
        t = np.arange(0.0, 3.0, 0.01)
        s = np.sin(2 * np.pi * t)
        self.pg1.clear()
        self.pg1.setData(t, s)
        



if __name__ == "__main__":
	# 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
	app = QtWidgets.QApplication(sys.argv)
	# #创建一个我们生成的那个窗口，注意把类名修改为MainWindow
	mainWindow = MainWindow()
	mainWindow.show()
	sys.exit(app.exec_())

