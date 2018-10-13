#!/usr/bin/python
# -*- coding: UTF-8 -*-
from PyQt5 import  QtWidgets
import sys
from PyQt5.uic import loadUi
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import numpy as np

import matplotlib
matplotlib.use("Qt5Agg")  # 声明使用QT5
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


#创建一个matplotlib图形绘制类
class MyFigure(FigureCanvas):
    def __init__(self,width=5, height=4, dpi=100):
        #第一步：创建一个创建Figure
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        #第二步：在父类中激活Figure窗口
        super(MyFigure,self).__init__(self.fig) #此句必不可少，否则不能显示图形
        #第三步：创建一个子图，用于绘制图形用，111表示子图编号，如matlab的subplot(1,1,1)
        self.axes = self.fig.add_subplot(111)

    #第四步：就是画图，【可以在此类中画，也可以在其它类中画】
    def plotsin(self):
        self.axes0 = self.fig.add_subplot(111)
        t = np.arange(0.0, 3.0, 0.01)
        s = np.sin(2 * np.pi * t)
        self.axes0.plot(t, s)


class MainWindow(QtWidgets.QMainWindow):
	def __init__(self, parent=None):
		super(MainWindow, self).__init__(parent)
		loadUi('form1.ui', self)

		#建立画板
		self.graphicsView.scene = QGraphicsScene(self)
		self.graphicsView.setScene(self.graphicsView.scene)
		self.graphicsView.draw=""
		self.graphicsView.flag=False
		

		# 将按钮点击事件和calc槽函数绑定
		self.pushButton.clicked.connect(self.show_table)
		
	# 定义槽函数
	def show_table(self):
		#设置图形的大小
		self.F = MyFigure(width=8, height=3, dpi=100)
		self.F.plotsin()
		# 将图形元素添加到场景中
		self.graphicsView.scene.addWidget(self.F)
		self.graphicsView.show()






if __name__ == "__main__":
	# 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
	app = QtWidgets.QApplication(sys.argv)
	# #创建一个我们生成的那个窗口，注意把类名修改为MainWindow
	mainWindow = MainWindow()
	mainWindow.show()
	sys.exit(app.exec_())

