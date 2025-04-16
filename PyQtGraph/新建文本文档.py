import sys
import os
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
from pyqtgraph import RectROI, EllipseROI, PolyLineROI, TextItem

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.current_mode = None
        self.selected_roi = None
        self.start_pos = None

    def setup_ui(self):
        self.setWindowTitle("ROI绘图工具")
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        # 创建绘图视图
        self.graphics_view = pg.GraphicsView()
        self.view = pg.ViewBox()
        self.graphics_view.setCentralItem(self.view)
        layout.addWidget(self.graphics_view)

        # 状态显示标签
        self.status_label = QtWidgets.QLabel("就绪 - 右键单击选择操作")
        layout.addWidget(self.status_label)

        # 初始化图像显示
        self.image_item = pg.ImageItem()
        self.view.addItem(self.image_item)
        self.view.setAspectLocked(True)

        # 设置右键菜单策略
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # 禁用子控件的默认右键菜单
        self.graphics_view.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.view.setMenuEnabled(False)

    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QtWidgets.QMenu(self)
        
        # 创建操作菜单项
        create_menu = menu.addMenu("创建")
        create_menu.addAction("矩形", lambda: self.set_create_mode('rect'))
        create_menu.addAction("椭圆", lambda: self.set_create_mode('ellipse'))
        create_menu.addAction("线段", lambda: self.set_create_mode('line'))
        create_menu.addAction("文本", lambda: self.set_create_mode('text'))
        
        # 功能操作菜单项
        menu.addSeparator()
        menu.addAction("清除所有", self.clear_all)
        menu.addAction("打开图片", self.open_image)
        
        # 显示菜单
        menu.exec_(self.mapToGlobal(pos))

    def set_create_mode(self, mode):
        """设置ROI创建模式"""
        self.current_mode = mode
        mode_names = {
            'rect': '矩形', 
            'ellipse': '椭圆',
            'line': '线段',
            'text': '文本'
        }
        self.status_label.setText(f"准备创建 {mode_names[mode]} - 左键单击放置")

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        scene_pos = self.graphics_view.mapToScene(event.pos())
        view_pos = self.view.mapSceneToView(scene_pos)
        
        if event.button() == QtCore.Qt.LeftButton:
            if self.current_mode:
                # 创建新ROI
                self.create_roi(view_pos)
            else:
                # 选择现有ROI
                self.select_roi(scene_pos, view_pos)
        
        super().mousePressEvent(event)

    def create_roi(self, pos):
        """根据当前模式创建ROI"""
        if self.current_mode == 'rect':
            roi = RectROI(pos, [1, 1], pen='r', movable=False,
                         resizable=False, rotatable=False)
        elif self.current_mode == 'ellipse':
            roi = EllipseROI(pos, [1, 1], pen='g', movable=False,
                            resizable=False, rotatable=False)
        elif self.current_mode == 'line':
            roi = PolyLineROI([pos, pos], pen='b', closed=False,
                             movable=False, rotatable=False)
        elif self.current_mode == 'text':
            text = TextItem("双击编辑文本", color='w', anchor=(0, 0))
            text.setPos(pos.x(), pos.y())
            self.view.addItem(text)
            self.current_mode = None
            self.status_label.setText("就绪 - 右键单击选择操作")
            return
        
        self.view.addItem(roi)
        self.current_mode = None
        self.status_label.setText("就绪 - 右键单击选择操作")

    def select_roi(self, scene_pos, view_pos):
        """选择并准备移动现有ROI"""
        items = self.view.scene().items(scene_pos)
        for item in items:
            if isinstance(item, (RectROI, EllipseROI, PolyLineROI, TextItem)):
                self.selected_roi = item
                self.start_pos = (view_pos.x(), view_pos.y())
                self.status_label.setText(f"已选择 {type(item).__name__} - 拖动移动")
                break

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件（用于拖动ROI）"""
        if self.selected_roi and self.start_pos:
            scene_pos = self.graphics_view.mapToScene(event.pos())
            current_pos = self.view.mapSceneToView(scene_pos)
            
            dx = current_pos.x() - self.start_pos[0]
            dy = current_pos.y() - self.start_pos[1]
            
            if isinstance(self.selected_roi, TextItem):
                new_pos = (self.selected_roi.pos().x() + dx,
                          self.selected_roi.pos().y() + dy)
                self.selected_roi.setPos(new_pos)
            elif hasattr(self.selected_roi, 'setPos'):
                new_pos = (self.selected_roi.pos().x() + dx,
                          self.selected_roi.pos().y() + dy)
                self.selected_roi.setPos(new_pos)
            
            self.start_pos = (current_pos.x(), current_pos.y())
        
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """结束ROI移动操作"""
        if event.button() == QtCore.Qt.LeftButton and self.selected_roi:
            self.selected_roi = None
            self.start_pos = None
            self.status_label.setText("就绪 - 右键单击选择操作")
        
        super().mouseReleaseEvent(event)

    def clear_all(self):
        """清除所有ROI和文本"""
        for item in self.view.addedItems:
            if isinstance(item, (RectROI, EllipseROI, PolyLineROI, TextItem)):
                self.view.removeItem(item)
        self.status_label.setText("已清除所有内容")

    def open_image(self):
        """打开图片文件"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "打开图片", "", "图片文件 (*.png *.jpg *.bmp *.tif)")
        if path:
            try:
                from PIL import Image
                img = Image.open(path)
                self.image_item.setImage(np.array(img))
                self.status_label.setText(f"已加载: {os.path.basename(path)}")
            except Exception as e:
                self.status_label.setText(f"错误: {str(e)}")

if __name__ == "__main__":
    # 配置pyqtgraph全局选项
    pg.setConfigOptions(antialias=True, imageAxisOrder='row-major')
    
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
