from PyQt5 import  QtWidgets
import sys
import os
from PyQt5.uic import loadUi
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from types import MethodType


class MainWindow(QtWidgets.QMainWindow):
	def __init__(self, parent=None):
		super(MainWindow, self).__init__(parent)
		loadUi('form1.ui', self)

		'''
                物体坐标系：以物体的中心为原点（0,0），物体的位置是指物体的中心点，在它的父物体坐标系中的坐标（父物体原点是父物体的中心），没有parent的物体，场景scene就是该物体的parent
                场景坐标：所有物体相对于Scene的坐标，Scene可以理解为矩形的画布，Scene的中心为原点
                          当scene<GraphicsView时，scene与GraphicsView的默认对齐方式为居中对齐，当scene长宽均>GraphicsViews时，scene与GraphicsView的默认对齐方式为左上角对齐。
                          向scene中addItem时使用的坐标为场景坐标。
                视图坐标：所有物体相对于GraphicsView的坐标(与窗口相同)，GraphicsView可以理解为画布上的一个可移动的小小的镜头，始终以窗口左上角为原点，正方向x朝右，y朝下。视图坐标是可以移动的
                          鼠标移动、点击事件返回的坐标均是视图坐标，因此addItem时必须使用mapToScene（）将视图坐标转换为场景坐标
                '''

		#建立画板
		self.graphicsView.scene = QGraphicsScene(self)
		self.graphicsView.setScene(self.graphicsView.scene)
		self.graphicsView.draw=""
		self.graphicsView.flag=False


		# 重写鼠标按下事件
		def mousePressEvent(self, e):
			print("mousePressEvent", e.button())
			self.flag = True
			#鼠标返回的是视图坐标，将视图坐标转换为场景坐标
			self.x0 = self.mapToScene(e.pos()).x()
			self.y0 = self.mapToScene(e.pos()).y()
			# 主窗口中如果不使用grabMouse()，将只能响应mousepress事件而不能响应mouserelease事件以及mousemove事件
			#self.grabMouse()

			# 添加line的子函数
			if self.draw == "Line":
				self.line = QGraphicsLineItem(self.x0, self.y0, self.x0, self.y0)
				self.scene.addItem(self.line)

			# 添加Rect的子函数
			if self.draw == "Rect":
				# 前两个参数为坐标，后两个参数为长宽
				self.rect = QGraphicsRectItem(self.x0, self.y0, 0, 0)
				# 设置为可选择，可拖拽
				self.rect.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
				#设置边框为红色
				self.rect.setPen(QColor(255, 0, 0))
				#设置填充色为透明
				self.rect.setBrush(QColor(255, 255, 255, 0))
				self.scene.addItem(self.rect)

			# 添加椭圆的子函数
			if self.draw == "Ellipse":
				# 前两个参数为坐标，后两个参数为长宽
				self.ellipse = QGraphicsEllipseItem(self.x0, self.y0, 0, 0)
				# 设置为可选择，可拖拽
				self.ellipse.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
				self.scene.addItem(self.ellipse)

			# 添加文字的子函数
			if self.draw == "Text":
				self.text = QGraphicsTextItem("hello world")
				self.text.setPos(QPoint(self.x0, self.y0))
				#设置文本的颜色
				self.text.setDefaultTextColor(QColor(255, 0, 0))
				self.scene.addItem(self.text)

			self.scene.update()

		# 定义鼠标移动事件
		def mouseMoveEvent(self, e):
			print("mouseMoveEvent：", self.mapToScene(e.pos()))
			self.x2 = self.mapToScene(e.pos()).x()
			self.y2 = self.mapToScene(e.pos()).y()

			# 修改矩形大小
			if hasattr(self, "rect") and self.draw == "Rect" and self.flag == True:
				self.rect.setRect(self.x0, self.y0, self.x2 - self.x0, self.y2 - self.y0)

			# 修改直线终点
			if hasattr(self, "line") and self.draw == "Line" and self.flag == True:
				self.line.setLine(self.x0, self.y0, self.x2, self.y2)

			# 修改椭圆大小
			if hasattr(self, "ellipse") and self.draw == "Ellipse" and self.flag == True:
				self.ellipse.setRect(self.x0, self.y0, self.x2 - self.x0, self.y2 - self.y0)

			self.scene.update()

		# 定义鼠标释放事件
		def mouseReleaseEvent(self, e):
			print("mouseReleaseEvent", e.button())
			self.flag = False
			self.x1 = self.mapToScene(e.pos()).x()
			self.y1 = self.mapToScene(e.pos()).y()
			print("鼠标释放坐标：", e.x(), e.y())
			#self.releaseMouse()



		#使用MethodType将函数转换为方法，再绑定到实例上去
		self.graphicsView.mousePressEvent=MethodType(mousePressEvent,self.graphicsView)
		self.graphicsView.mouseMoveEvent = MethodType(mouseMoveEvent, self.graphicsView)
		self.graphicsView.mouseReleaseEvent = MethodType(mouseReleaseEvent, self.graphicsView)


		# 将按钮点击事件和槽函数绑定
		self.pushButton.clicked.connect(self.open)
		self.pushButton_4.clicked.connect(self.addText)
		self.pushButton_3.clicked.connect(self.addRect)
		self.pushButton_2.clicked.connect(self.addLine)
		self.pushButton_5.clicked.connect(self.addEllipse)
		self.pushButton_6.clicked.connect(self.deletAll)

	# 定义槽函数
	def open(self):
		# 设置文件扩展名过滤,
		fileName, filetype = QtWidgets.QFileDialog.getOpenFileName(self,"请打开文件", "G:\WindowsXP高清晰图片1025乘768[够酷]（想要什么这里都能找到！）", "Text Files (*.jpg;*.bmp)")
		self.lineEdit.setText(fileName)

		pixmap=QPixmap()
		pixmap.load(fileName)
		item=QtWidgets.QGraphicsPixmapItem(pixmap)
		self.graphicsView.scene.addItem(item)

	def addText(self):
		self.graphicsView.draw="Text"

	def addRect(self):
		self.graphicsView.draw = "Rect"

	def addLine(self):
		self.graphicsView.draw = "Line"

	def addEllipse(self):
		self.graphicsView.draw = "Ellipse"

	def deletAll(self):
		item_list=self.graphicsView.scene.items()
		for item in item_list:
			self.graphicsView.scene.removeItem(item)
		self.graphicsView.scene.update()
		self.draw = ""



if __name__ == "__main__":
        os.chdir(sys.path[0])
        # 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
        app = QtWidgets.QApplication(sys.argv)
        #创建一个我们生成的那个窗口，注意把类名修改为MainWindow
        mainWindow = MainWindow()
        mainWindow.show()
        sys.exit(app.exec_())
