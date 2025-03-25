from PyQt5 import QtWidgets
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsLineItem, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt5.uic import loadUi
import sys
import os
import traceback

def excepthook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.exit(1)

sys.excepthook = excepthook  # 重写异常钩子



#将绘图逻辑封装到一个单独的类中，然后在每个 QGraphicsView 中实例化这个类。这样每个 QGraphicsView 都可以独立使用绘图功能。
class GraphicsViewDrawer:
    def __init__(self, graphics_view):
        self.graphics_view = graphics_view

        #建立画板
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        self.draw_mode = ""
        self.current_item = None
        self.start_point = None

        # 连接鼠标事件
        self.graphics_view.mousePressEvent = self.mouse_press_event
        self.graphics_view.mouseMoveEvent = self.mouse_move_event
        self.graphics_view.mouseReleaseEvent = self.mouse_release_event

    def set_draw_mode(self, mode):
        self.draw_mode = mode

    def clear_scene(self):
        for item in self.scene.items():
            self.scene.removeItem(item)
        self.scene.update()
        self.draw_mode = ""

    '''
    物体坐标系：以物体的中心为原点（0,0），物体的位置是指物体的中心点，在它的父物体坐标系中的坐标（父物体原点是父物体的中心），没有parent的物体，场景scene就是该物体的parent
    场景坐标：所有物体相对于Scene的坐标，Scene可以理解为矩形的画布，Scene的中心为原点
                当scene<GraphicsView时，scene与GraphicsView的默认对齐方式为居中对齐，当scene长宽均>GraphicsViews时，scene与GraphicsView的默认对齐方式为左上角对齐。
                向scene中addItem时使用的坐标为场景坐标。
    视图坐标：所有物体相对于GraphicsView的坐标(与窗口相同)，GraphicsView可以理解为画布上的一个可移动的小小的镜头，始终以窗口左上角为原点，正方向x朝右，y朝下。视图坐标是可以移动的
                鼠标移动、点击事件返回的坐标均是视图坐标，因此addItem时必须使用mapToScene（）将视图坐标转换为场景坐标
    '''
    # 重写鼠标按下事件
    def mouse_press_event(self, event):
        print("mousePressEvent", event.button())
        if self.draw_mode:
            #鼠标返回的是视图坐标，将视图坐标转换为场景坐标
            self.start_point = self.graphics_view.mapToScene(event.pos())
            if self.draw_mode == "Line":
                self.current_item = QGraphicsLineItem(self.start_point.x(), self.start_point.y(), self.start_point.x(), self.start_point.y())
            elif self.draw_mode == "Rect":
                # 前两个参数为坐标，后两个参数为长宽
                self.current_item = QGraphicsRectItem(self.start_point.x(), self.start_point.y(), 0, 0)
                #设置边框为红色
                self.current_item.setPen(QColor(255, 0, 0))
            elif self.draw_mode == "Ellipse":
                # 前两个参数为坐标，后两个参数为长宽
                self.current_item = QGraphicsEllipseItem(self.start_point.x(), self.start_point.y(), 0, 0)
            elif self.draw_mode == "Text":
                self.current_item = QGraphicsTextItem("hello world")
                #设置文本的颜色
                self.current_item.setDefaultTextColor(QColor(255, 0, 0))
                self.current_item.setPos(self.start_point)
            if self.current_item:
                self.scene.addItem(self.current_item)

    # 定义鼠标移动事件
    def mouse_move_event(self, event):
        if self.draw_mode and self.current_item:
            print("mouseMoveEvent：", self.graphics_view.mapToScene(event.pos()))
            end_point = self.graphics_view.mapToScene(event.pos())
            if self.draw_mode == "Line":
                self.current_item.setLine(self.start_point.x(), self.start_point.y(), end_point.x(), end_point.y())
            elif self.draw_mode == "Rect":
                # 修改矩形大小
                self.current_item.setRect(self.start_point.x(), self.start_point.y(), end_point.x() - self.start_point.x(), end_point.y() - self.start_point.y())
            elif self.draw_mode == "Ellipse":
                self.current_item.setRect(self.start_point.x(), self.start_point.y(), end_point.x() - self.start_point.x(), end_point.y() - self.start_point.y())

    # 定义鼠标释放事件
    def mouse_release_event(self, event):
        print("mouseReleaseEvent", event.button())
        self.current_item = None


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        loadUi('form1.ui', self)

        # 为每个 QGraphicsView 创建绘图工具
        self.drawer1 = GraphicsViewDrawer(self.graphicsView)
        #self.drawer2 = GraphicsViewDrawer(self.graphicsView2)

        # 连接按钮点击事件
        self.pushButton.clicked.connect(self.open_image)
        self.pushButton_4.clicked.connect(lambda: self.drawer1.set_draw_mode("Text"))
        self.pushButton_3.clicked.connect(lambda: self.drawer1.set_draw_mode("Rect"))
        self.pushButton_2.clicked.connect(lambda: self.drawer1.set_draw_mode("Line"))
        self.pushButton_5.clicked.connect(lambda: self.drawer1.set_draw_mode("Ellipse"))
        self.pushButton_6.clicked.connect(self.drawer1.clear_scene)

    def open_image(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "请打开文件", "", "Images (*.jpg *.bmp)")
        if file_name:
            self.lineEdit.setText(file_name)
            pixmap = QPixmap(file_name)
            item = QtWidgets.QGraphicsPixmapItem(pixmap)
            self.drawer1.scene.addItem(item)


if __name__ == "__main__":
    os.chdir(sys.path[0])
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
