# 导入必要的库
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.uic import loadUi
import pyqtgraph as pg  # 强大的绘图库
import sys
import os
import cv2  # OpenCV库，用于图像处理
import numpy as np
from typing import Optional, Tuple, Dict, Any  # 类型提示


class ROIManager(QtCore.QObject):
    """ROI管理器，负责ROI的创建、删除和状态跟踪"""
    roi_selected = pyqtSignal(object)  # 当ROI被选中时发射信号

    def __init__(self, plot_widget: pg.PlotWidget, list_model: QStandardItemModel, image_item: pg.ImageItem):
        super().__init__()
        self.plot = plot_widget  # 绘图区域
        self.list_model = list_model  # ROI列表的数据模型
        self.image_item = image_item  # 图像项
        self.current_image: Optional[np.ndarray] = None  # 当前显示的图像
        self.active_roi: Optional[RectROI] = None  # 当前活动的ROI
        self.rois: Dict[int, RectROI] = {}  # 存储所有ROI的字典，键是ROI的ID

    def add_roi(self) -> None:
        """添加新的ROI"""
        roi = RectROI(
            image_item=self.image_item,  # 传递图像项引用
            pos=[10, 10],  # 初始位置
            size=[100, 100],  # 初始大小
            pen={'color': 'r', 'width': 1},  # 红色边框
            movable=True,  # 可移动
            rotatable=False,  # 不可旋转
            removable=True  # 可移除
        )
        roi.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton) #ROI默认情况下禁用点击以防止从后面的对象中窃取点击。要手动启用点击支持
        self.plot.addItem(roi)  # 将ROI添加到绘图区域
        self._setup_roi_handles(roi)  # 设置ROI的控制点
        self._connect_roi_signals(roi)  # 连接信号槽
        self._update_roi_list(roi)  # 更新ROI列表

    def _setup_roi_handles(self, roi: pg.RectROI) -> None:
        """配置ROI的缩放控制点"""
        roi.addScaleHandle((1, 0), (0, 1))  # 右上角控制点
        roi.addScaleHandle((0, 1), (1, 0))  # 左上角控制点
        roi.addScaleHandle((0, 0), (1, 1))  # 左下角控制点

    def _connect_roi_signals(self, roi: 'RectROI') -> None:
        """连接ROI的信号槽"""
        roi.sigRegionChanged.connect(lambda: self._on_roi_changed(roi))  # ROI区域变化信号
        roi.sigRemoveRequested.connect(lambda: self.remove_roi(roi))  # ROI移除请求信号
        roi.sigClicked.connect(lambda: self._on_roi_changed(roi))  # ROI点击信号
        

    def _update_roi_list(self, roi: 'RectROI') -> None:
        """更新ROI列表"""
        self.rois[roi.unique_id] = roi  # 将ROI添加到字典
        # 在列表模型中添加ROI的名称和ID
        self.list_model.appendRow([
            QStandardItem(roi.name),
            QStandardItem(str(roi.unique_id))
        ])

    def remove_roi(self, roi: 'RectROI') -> None:
        """删除指定ROI"""
        self.plot.removeItem(roi)  # 从绘图区域移除
        del self.rois[roi.unique_id]  # 从字典中删除
        self._remove_from_list(roi.unique_id)  # 从列表模型中删除

    def _remove_from_list(self, roi_id: int) -> None:
        """从列表模型中移除指定ROI"""
        for row in range(self.list_model.rowCount()):
            if self.list_model.item(row, 1).text() == str(roi_id):
                self.list_model.removeRow(row)  # 删除对应行
                break

    def clear_all_rois(self) -> None:
        """清除所有ROI"""
        for roi in list(self.rois.values()):
            self.plot.removeItem(roi)  # 逐个移除
        self.rois.clear()  # 清空字典
        self.list_model.clear()  # 清空列表模型

    def _on_roi_changed(self, roi: 'RectROI') -> None:
        """处理ROI变化事件"""
        if self.current_image is not None:
            roi.update_image_stats(self.current_image)  # 更新ROI内的图像统计信息
        self._update_selection(roi)  # 更新选中状态

    def _update_selection(self, selected_roi: 'RectROI') -> None:
        """更新选中状态"""
        self.active_roi = selected_roi  # 设置当前活动ROI
        # 遍历所有ROI，设置边框颜色（选中为绿色，未选中为红色）
        for roi in self.rois.values():
            roi.setPen('g' if roi == selected_roi else 'r')
        self.roi_selected.emit(selected_roi)  # 发射选中信号

    def update_image_data(self, image: np.ndarray) -> None:
        """更新当前图像数据"""
        self.current_image = image
        # 更新所有ROI的图像统计信息
        for roi in self.rois.values():
            roi.update_image_stats(image)


class RectROI(pg.RectROI):
    """自定义矩形ROI，支持图像统计功能"""
    _counter = 0  # 类变量，用于生成唯一ID

    def __init__(self, image_item: pg.ImageItem, *args, **kwargs): 
        super().__init__(*args,**kwargs)
        self.image_item = image_item  # 关联的图像项
        self.unique_id = self._generate_id()  # 唯一标识符
        self.name = f"ROI{self.unique_id}"  # ROI名称
        # 图像统计信息字典
        self.image_stats: Dict[str, float] = {
            'GrayMax': 0,  # 最大灰度值
            'GrayMin': 0,  # 最小灰度值
            'GrayMean': 0,  # 平均灰度值
            'GrayRange': 0  # 灰度范围
        }
        self._position = (0.0, 0.0)  # ROI位置
        self._dimensions = (0.0, 0.0)  # ROI尺寸

    @classmethod
    def _generate_id(cls) -> int:
        """生成唯一ID"""
        cls._counter += 1
        return cls._counter

    def update_image_stats(self, image: np.ndarray) -> None:
        """更新图像统计信息"""
        try:
            # 获取ROI区域内的图像数据
            region = self.getArrayRegion(image, self.image_item)
            # 转换为8位无符号整数类型（OpenCV常用类型）
            region = region.astype(np.uint8)
            if region is None or region.size == 0:
                return
            
            # 如果是彩色图像，转换为灰度
            if len(region.shape) == 3:
                region = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)

            # 计算并更新统计信息
            self.image_stats = {
                'GrayMax': np.max(region),
                'GrayMin': np.min(region),
                'GrayMean': np.mean(region),
                'GrayRange': np.max(region)-np.min(region)
                }
            
            # 更新位置和尺寸信息
            self._position = (round(self.pos().x(), 2), round(self.pos().y(), 2))
            size = super().size()  # 显式调用父类的size方法
            self._dimensions = (round(size.x(), 2), round(size.y(), 2))
            
        except Exception as e:
            print(f"Error updating image stats: {str(e)}")

    @property
    def stats_formatted(self) -> Dict[str, str]:
        """格式化后的统计信息（保留两位小数）"""
        return {k: f"{v:.2f}" for k, v in self.image_stats.items()}

    @property
    def position(self) -> Tuple[float, float]:
        """当前ROI位置"""
        return self._position

    @property
    def dimensions(self) -> Tuple[float, float]:
        """当前ROI尺寸"""
        return self._dimensions


class ImageViewer(pg.PlotWidget):
    """图像显示组件"""
    def __init__(self):
        super().__init__()
        self._setup_view()  # 初始化视图设置
        self.image_item = pg.ImageItem()  # 创建图像项
        self.addItem(self.image_item)  # 添加到绘图区域

    def _setup_view(self) -> None:
        """初始化视图设置"""
        self.setBackground('w')  # 白色背景
        self.showAxis('bottom', False)  # 隐藏底部坐标轴
        self.showAxis('left', False)  # 隐藏左侧坐标轴
        self.setMenuEnabled(False)  # 禁用右键菜单

    def update_image(self, image: np.ndarray) -> None:
        """更新显示图像"""
        self.image_item.setImage(image)  # 设置图像数据
        # 设置显示范围匹配图像尺寸
        self.setRange(xRange=[0, image.shape[1]], yRange=[0, image.shape[0]])


class MainWindow(QtWidgets.QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        loadUi('form.ui', self)  # 加载UI文件
        self.setWindowTitle("ROI管理器")  # 设置窗口标题
        self._setup_ui()  # 初始化UI组件
        self._setup_camera()  # 初始化摄像头相关组件
        self._connect_signals()  # 连接信号槽

    def _setup_ui(self) -> None:
        """初始化界面组件"""
        self.image_viewer = ImageViewer()  # 创建图像显示组件
        self.horizontalLayout.addWidget(self.image_viewer)  # 添加到布局
        self.horizontalLayout.setStretch(1, 4)  # 设置布局拉伸因子

        # 初始化ROI列表模型
        self.roi_list_model = QStandardItemModel()
        self.roi_list_model.setHorizontalHeaderLabels(["ROI名称", "ID"])
        self.listView.setModel(self.roi_list_model)

        # 初始化属性表格模型
        self.property_model = QStandardItemModel()
        self.property_model.setHorizontalHeaderLabels(["属性", "值"])
        self.tableView.setModel(self.property_model)

        # 初始化ROI管理器
        self.roi_manager = ROIManager(
            self.image_viewer,
            self.roi_list_model,
            self.image_viewer.image_item
        )
        self.roi_manager.roi_selected.connect(self._update_property_table)

    def _setup_camera(self) -> None:
        """初始化摄像头相关组件"""
        self.capture = cv2.VideoCapture()  # 创建视频捕获对象
        self.timer = QTimer()  # 创建定时器
        self.timer.timeout.connect(self._update_camera_frame)  # 定时器超时信号

    def _connect_signals(self) -> None:
        """连接信号槽"""
        self.actionOpenImage.triggered.connect(self.load_image)  # 打开图像菜单
        self.actionOpenCamera.triggered.connect(self.toggle_camera)  # 打开摄像头菜单
        self.pushButton_1.clicked.connect(self.roi_manager.add_roi)  # 添加ROI按钮
        self.pushButton_2.clicked.connect(self.roi_manager.clear_all_rois)  # 清除所有ROI按钮
        self.listView.clicked.connect(self._on_list_clicked)  # ROI列表点击事件

    def load_image(self) -> None:
        """加载图像文件"""
        try:
            # 打开文件对话框选择图像
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "打开图像", "", "Images (*.jpg *.png *.bmp)")
            if not path:
                return

            # 读取图像文件
            image = cv2.imread(path)
            if image is None:
                raise ValueError("无法读取图像文件")

            # 转换颜色空间(BGR转RGB)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            self._process_image(image)  # 处理并显示图像
        except Exception as e:
            self._show_error(f"加载图像失败: {str(e)}")  # 显示错误信息

    def _process_image(self, image: np.ndarray) -> None:
        """处理并显示图像"""
        self.image_viewer.update_image(image)  # 更新图像显示
        self.roi_manager.update_image_data(image)  # 更新ROI管理器中的图像数据

    def toggle_camera(self) -> None:
        """切换摄像头状态"""
        if self.timer.isActive():
            self._stop_camera()  # 如果定时器在运行，停止摄像头
        else:
            self._start_camera()  # 否则启动摄像头

    def _start_camera(self) -> None:
        """启动摄像头"""
        if not self.capture.open(0):  # 尝试打开默认摄像头
            self._show_error("无法打开摄像头")
            return
        self.timer.start(30)  # 启动定时器，30ms刷新一次

    def _stop_camera(self) -> None:
        """停止摄像头"""
        self.timer.stop()  # 停止定时器
        self.capture.release()  # 释放摄像头资源

    def _update_camera_frame(self) -> None:
        """更新摄像头帧"""
        ret, frame = self.capture.read()  # 读取一帧
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # 转换颜色空间
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)  # 旋转90度
            self._process_image(frame)  # 处理并显示图像

    def _on_list_clicked(self, index: QtCore.QModelIndex) -> None:
        """处理列表点击事件"""
        # 获取点击项的ID列数据
        item = self.roi_list_model.itemFromIndex(index.siblingAtColumn(1))
        if item:
            roi_id = int(item.text())  # 获取ROI ID
            if roi_id in self.roi_manager.rois:
                # 更新选中状态
                self.roi_manager._update_selection(self.roi_manager.rois[roi_id])

    def _update_property_table(self, roi: RectROI) -> None:
        """更新属性表格"""
        self.property_model.clear()  # 清空表格
        # 准备要显示的属性数据
        properties = {
            "ID": roi.unique_id,
            "位置": roi.position,
            "尺寸": roi.dimensions,
            "最大灰度值": roi.stats_formatted.get('GrayMax', 'N/A'),
            "最小灰度值": roi.stats_formatted.get('GrayMin', 'N/A'),
            "平均灰度值": roi.stats_formatted.get('GrayMean', 'N/A'),
            "灰度值极差": roi.stats_formatted.get('GrayRange', 'N/A')
        }

        # 逐行添加属性数据
        for row, (key, value) in enumerate(properties.items()):
            self.property_model.setItem(row, 0, QStandardItem(str(key)))
            self.property_model.setItem(row, 1, QStandardItem(str(value)))

    def _show_error(self, message: str) -> None:
        """显示错误信息"""
        QtWidgets.QMessageBox.critical(self, "错误", message)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """窗口关闭事件处理"""
        self._stop_camera()  # 确保摄像头被正确释放
        super().closeEvent(event)


if __name__ == "__main__":
    os.chdir(sys.path[0])  # 切换到脚本所在目录
    app = QtWidgets.QApplication(sys.argv)  # 创建应用实例
    window = MainWindow()  # 创建主窗口实例
    window.show()  # 显示窗口
    sys.exit(app.exec_())  # 进入主事件循环
