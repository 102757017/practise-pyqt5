from PyQt5 import  QtWidgets
import sys
import os
from PyQt5.uic import loadUi
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import cv2
import numpy as np

class MainWindow(QtWidgets.QMainWindow):
	def __init__(self, parent=None):
		super(MainWindow, self).__init__(parent)
		loadUi('form1.ui', self)

		#建立画板
		self.graphicsView.scene = QGraphicsScene(self)
		self.graphicsView.setScene(self.graphicsView.scene)



		# 将按钮点击事件和槽函数绑定
		self.pushButton.clicked.connect(self.open)

	# 定义槽函数
	def open(self):
		# 设置文件扩展名过滤,
		fileName, filetype = QtWidgets.QFileDialog.getOpenFileName(self,"请打开文件", "G:\WindowsXP高清晰图片1025乘768[够酷]（想要什么这里都能找到！）", "Text Files (*.jpg;*.bmp;*.jpeg)")
		self.lineEdit.setText(fileName)
		

		img = cv2.imdecode(np.fromfile(fileName, dtype=np.uint8), 1)
		height,width,bytesPerComponet=img.shape
		bytesPerLine=3*width
		# opencv读取到图像后，图像彩色的组织顺序是‘BGR’的，面QImage的顺序是‘RGB’。所以首先要做一下顺序调整：
		cv2.cvtColor(img,cv2.COLOR_BGR2RGB,img)

		#bytesPerLine = 3 * width,当1个像素占3个字节，此时图像为真彩色图像
		#QImage.Format_RGB888表示的是图像存储使用8-8-8 24位RGB格式
		Qimg = QImage(img.data,width, height,bytesPerLine, QImage.Format_RGB888)
		pixmap=QPixmap.fromImage(Qimg)
		item=QtWidgets.QGraphicsPixmapItem(pixmap)
		self.graphicsView.scene.addItem(item)



if __name__ == "__main__":
        os.chdir(sys.path[0])
        # 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
        app = QtWidgets.QApplication(sys.argv)
        # 创建一个我们生成的那个窗口，注意把类名修改为MainWindow
        mainWindow = MainWindow()
        mainWindow.show()
        sys.exit(app.exec_())

