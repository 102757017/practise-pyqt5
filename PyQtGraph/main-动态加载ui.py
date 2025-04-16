from PyQt5 import QtWidgets
import sys
from PyQt5.uic import loadUi
from PyQt5.QtGui import QStandardItemModel, QStandardItem
import pyqtgraph as pg
import os
import cv2

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        loadUi('form.ui', self)
        self.setWindowTitle("ROI管理器")

        # 将 QGraphicsView 替换为 PlotWidget
        self.plot = pg.PlotWidget()
        self.horizontalLayout.addWidget(self.plot)
        self.horizontalLayout.setStretch(1, 4)  # 设置水平布局的比例
        self.plot.setBackground('w')  # 设置背景颜色为白色
        self.plot.showAxis('bottom', show=False)  # 隐藏底部坐标轴
        self.plot.showAxis('left', show=False)    # 隐藏左侧坐标轴
        self.plot.setMenuEnabled(False)           # 禁用右键菜单
        self.img_item = pg.ImageItem()
        self.plot.addItem(self.img_item)

        # 创建列表的数据模型
        self.listViewModel = QStandardItemModel()
        self.listViewModel.setColumnCount(2)
        self.listViewModel.setHorizontalHeaderLabels(["ROI名称", "索引id"])  # 设置表头
        self.listView.setModel(self.listViewModel)

        # 创建属性数据模型
        self.model = QStandardItemModel()  
        self.model.setColumnCount(2)       # 设置列数
        self.model.setHorizontalHeaderLabels(["属性", "值"])  # 设置表头
        self.tableView.setModel(self.model)  # 将模型设置到 QTableView

        # 加载图像
        self.actionOpenImage.triggered.connect(self.load_image)  
        self.actionOpenCamera.triggered.connect(self.open_camera)
        self.pushButton_1.clicked.connect(self.add_roi)
        self.pushButton_2.clicked.connect(self.clear_roi)
        self.listView.clicked.connect(self.listViewClicked)  # 连接列表视图的点击事件

    def listViewClicked(self, index):
        # 获取索引id列的项
        item = self.listViewModel.itemFromIndex(index.siblingAtColumn(1))
        if item:
            roi_id = int(item.text())
            for roi in RectROI.members:
                if roi.unique_id == roi_id:
                    # ROI颜色改变
                    roi.setPen('g')
                else:
                    roi.setPen('r')
    def add_roi(self):
        roi = RectROI(
            pos=[10, 10],  # 初始位置
            size=[100, 100],  # 初始大小
            pen={'color': 'r', 'width': 1},
            movable=True,
            rotatable=False,
            removable=True    # 当选择删除ROI的菜单时，ROI会发出sigRemoveRequested 信号
        )
        roi.addScaleHandle((1, 0), (0, 1))  # 右上角
        roi.addScaleHandle((0, 1), (1, 0))  # 左上角
        roi.addScaleHandle((0, 0), (1, 1))  # 左下角
        self.plot.addItem(roi)
        roi.sigRegionChanged.connect(self.update_stats)
        roi.sigRemoveRequested.connect(self.remove_roi)  # 连接删除信号到槽函数

        # 更新列表视图
        self.listViewModel.appendRow([QStandardItem(roi.name), QStandardItem(str(roi.unique_id))])

    def remove_roi(self):
        roi = self.sender()
        self.plot.removeItem(roi)

        # 从列表视图中删除对应的行
        for i in range(self.listViewModel.rowCount()):
            if self.listViewModel.item(i, 1).text() == str(roi.unique_id):
                self.listViewModel.removeRow(i)
                break

    def clear_roi(self):
        for i in range(self.listViewModel.rowCount()):
            item = self.listViewModel.item(i, 1)
            if item:
                roi_id = int(item.text())
                for roi in RectROI.members:
                    if roi.unique_id == roi_id:
                        self.plot.removeItem(roi)
                        RectROI.members.remove(roi)
                        break
        self.listViewModel.clear()
        RectROI.counter = 0  # 重置计数器


    def update_stats(self):
        roi = self.sender()

        row = 0
        for attr, value in vars(roi).items():
            if attr in ['unique_id', 'Position', 'RectSize']:
                self.model.setItem(row, 0, QStandardItem(attr))
                self.model.setItem(row, 1, QStandardItem(str(value)))
                row += 1

    def load_image(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "请打开文件", "", "Images (*.jpg *.bmp)")
        if file_name:
            img = cv2.imread(file_name)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.img_item.setImage(img)
            self.plot.setRange(xRange=[0, img.shape[1]], yRange=[0, img.shape[0]])

    def open_camera(self):
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)  # 顺时针旋转 90 度
            self.img_item.setImage(frame)
            self.plot.setRange(xRange=[0, frame.shape[1]], yRange=[0, frame.shape[0]])
        cap.release()

class RectROI(pg.RectROI):
    counter = 0
    members = []

    def __init__(self, *args, **kwargs):
        super(RectROI, self).__init__(*args, **kwargs)
        self.unique_id = RectROI.counter  # 生成唯一 ID
        RectROI.counter += 1  # 增加计数器
        self.name = "ROI" + str(self.unique_id)
        RectROI.members.append(self)  # 存储 RectROI 实例本身
        self.Position = [self.pos().x(), self.pos().y()]
        self.RectSize = [self.size().x(), self.size().y()]
        self.sigRegionChanged.connect(self.update_position)  # 连接信号到槽函数

    def update_position(self):
        self.Position = [round(self.pos().x(), 2), round(self.pos().y(), 2)]
        self.RectSize = [round(self.size().x(), 2), round(self.size().y(), 2)]

if __name__ == "__main__":
    os.chdir(sys.path[0])
    # 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
    app = QtWidgets.QApplication(sys.argv)
    # 创建一个我们生成的那个窗口，注意把类名修改为MainWindow
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())