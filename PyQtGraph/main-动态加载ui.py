# 导入必要的库
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, QTimer, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from skimage.feature import graycomatrix, graycoprops #计算灰度共生矩阵
from PyQt5.uic import loadUi
import pyqtgraph as pg  # 强大的绘图库
import sys
import os
import cv2  # OpenCV库，用于图像处理
import numpy as np
from typing import Optional, Tuple, Dict, Any, List  # 类型提示
import toml
import pprint

# QStandardItem的自定义数据角色
class CustomRoles:
    """定义自定义数据角色，用于在QStandardItem中存储额外数据"""
    GroupIdRole = QtCore.Qt.UserRole + 1 # 目前未使用，但可保留备用
    RoiIdRole = QtCore.Qt.UserRole + 2

class ROIManager(QtCore.QObject):
    """ROI管理器，负责ROI的创建、删除和状态跟踪"""
    roi_selected = pyqtSignal(object)  # 当ROI被选中时发射信号
    group_selected = pyqtSignal(object) # 当Group被选中时发射信号，修改为object以允许None

    def __init__(self, plot_widget: pg.PlotWidget, tree_model: QStandardItemModel, image_item: pg.ImageItem):
        super().__init__()
        self.plot = plot_widget  # 绘图区域
        self.tree_model = tree_model  # ROI列表的数据模型 (现在是QTreeView的模型)
        self.image_item = image_item  # 图像项
        self.current_image: Optional[np.ndarray] = None  # 当前显示的图像 (已校正方向的图像)
        self.active_roi: Optional['RectROI'] = None  # 当前活动的ROI对象
        self.rois: Dict[int, 'RectROI'] = {}  # 存储所有ROI的字典，键是ROI的ID
        self.active_group_item: Optional[QStandardItem] = None # 当前选中的QStandardItem (组项)

    def set_active_group_item(self, item: Optional[QStandardItem]) -> None:
        """设置当前激活的组节点"""
        self.active_group_item = item
        # 无论 item 是否为 None，都发出信号，由接收方处理 Optional[QStandardItem]
        self.group_selected.emit(item) 

    def add_group(self, group_name: Optional[str] = None) -> QStandardItem:
        """添加一个新的组节点到QTreeView的根目录"""
        if group_name is None: 
            # 自动生成组名
            existing_groups = [self.tree_model.item(i, 0).text() for i in range(self.tree_model.rowCount())]
            i = 1
            while f"Group {i}" in existing_groups:
                i += 1
            group_name = f"Group {i}"

        group_item = QStandardItem(group_name)
        group_item.setEditable(True) # 组名可编辑
        self.tree_model.appendRow(group_item)
        return group_item

    def add_roi(self, x=50, y=50, w=100, h=100, unique_id: Optional[int] = None, name: Optional[str] = None) -> Optional['RectROI']:
        """添加新的ROI到当前选中的组下"""
        if self.active_group_item is None:
            QtWidgets.QMessageBox.warning(None, "提示", "请先选中一个分组再添加ROI！")
            return None

        roi = RectROI(
            image_item=self.image_item,  # 传递图像项引用
            pos=[x, y],  # 初始位置
            size=[w, h],  # 初始大小
            unique_id=unique_id, # 传递 unique_id 给 RectROI
            name=name,           # 传递 name 给 RectROI
            pen={'color': 'r', 'width': 1},  # 红色边框
            movable=True,  # 可移动
            rotatable=False,  # 不可旋转
            removable=True  # 可移除
        )
        roi.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton) # 设置接受鼠标左键事件
        self.plot.addItem(roi)  # 将ROI添加到绘图区域
        self._setup_roi_handles(roi)  # 设置ROI的控制点
        self._connect_roi_signals(roi)  # 连接信号槽
        self._update_roi_list(roi, self.active_group_item)  # 更新ROI列表，添加到当前组下
        return roi

    def _setup_roi_handles(self, roi: pg.RectROI) -> None:
        """配置ROI的缩放控制点"""
        roi.addScaleHandle((1, 0), (0, 1))  # 右上角控制点
        roi.addScaleHandle((0, 1), (1, 0))  # 左上角控制点
        roi.addScaleHandle((0, 0), (1, 1))  # 左下角控制点

    def _connect_roi_signals(self, roi: 'RectROI') -> None:
        """连接ROI的信号槽"""
        roi.sigRegionChanged.connect(lambda: self._on_roi_changed(roi))  # ROI区域变化信号
        roi.sigRemoveRequested.connect(lambda: self.remove_roi_obj(roi))  # ROI移除请求信号 (从UI右键菜单触发)
        roi.sigClicked.connect(lambda: self._on_roi_clicked(roi))  # ROI点击信号 (为了在UI中激活选中)
        

    def _update_roi_list(self, roi: 'RectROI', parent_item: QStandardItem) -> None:
        """更新ROI列表 (QTreeView)"""
        self.rois[roi.unique_id] = roi  # 将ROI对象添加到字典

        # 创建ROI名称和ID的QStandardItem
        roi_name_item = QStandardItem(roi.name)
        roi_name_item.setEditable(True) # ROI名称可编辑
        roi_id_item = QStandardItem(str(roi.unique_id))
        roi_id_item.setEditable(False) # ROI ID不可编辑

        # 将ROI对象本身存储在roi_name_item的UserRole中，方便查找
        roi_name_item.setData(roi.unique_id, CustomRoles.RoiIdRole)
        
        # 将ROI添加到父组项下
        parent_item.appendRow([roi_name_item, roi_id_item])

    def remove_roi_obj(self, roi: 'RectROI') -> None:
        """从绘图区域和内部数据结构中删除指定ROI对象"""
        self.plot.removeItem(roi)  # 从绘图区域移除
        if roi.unique_id in self.rois:
            del self.rois[roi.unique_id]  # 从字典中删除
            self._remove_from_tree_model(roi.unique_id) # 从QTreeView模型中删除

    def remove_roi_by_id(self, roi_id: int) -> None:
        """通过ROI ID删除ROI"""
        if roi_id in self.rois:
            roi = self.rois[roi_id]
            self.remove_roi_obj(roi)
        else:
            print(f"警告: 未找到ID为 {roi_id} 的ROI。")

    def _remove_from_tree_model(self, roi_id: int) -> None:
        """从QTreeView模型中移除指定ROI的QStandardItem"""
        # 遍历所有顶级项 (组)
        for group_row in range(self.tree_model.rowCount()):
            group_item = self.tree_model.item(group_row, 0)
            if group_item:
                # 遍历组下的所有子项 (ROI)
                for roi_row in range(group_item.rowCount()):
                    roi_name_item = group_item.child(roi_row, 0)
                    if roi_name_item and roi_name_item.data(CustomRoles.RoiIdRole) == roi_id:
                        group_item.removeRow(roi_row)
                        return # 找到并删除后即可返回

    def clear_all_items(self) -> None:
        """清除所有组和ROI"""
        for roi in list(self.rois.values()):
            self.plot.removeItem(roi)  # 逐个移除绘图区域的ROI
        self.rois.clear()  # 清空ROI字典
        self.tree_model.clear()  # 清空QTreeView模型
        self.tree_model.setHorizontalHeaderLabels(["名称", "ID"]) # 重新设置表头
        self.active_group_item = None
        self.active_roi = None

    def _on_roi_changed(self, roi: 'RectROI') -> None:
        """处理ROI区域变化事件"""
        if self.current_image is not None:
            roi.update_image_stats(self.current_image)  # 更新ROI内的图像统计信息
        
        # 如果当前活动的ROI就是这个ROI，则更新属性表
        if self.active_roi == roi:
            self.roi_selected.emit(roi) 
        
        # 更新QTreeView中ROI的名称 (如果名称是动态变化的，这里需要实现)
        # 例如，如果ROI名称包含位置信息，这里可以更新对应的QStandardItem
        # (当前 RectROI 的 name 是固定的，只有用户手动修改才会变)

    def _on_roi_clicked(self, roi: 'RectROI') -> None:
        """处理ROI在PlotWidget中被点击的事件"""
        self._update_selection(roi) # 更新选中状态
        # 还要在QTreeView中选中对应的项
        # 这需要在MainWindow中处理，因为ROIManager没有QTreeView的引用
        # 而是通过信号通知MainWindow
        self.roi_selected.emit(roi) # 重新发射信号以触发主窗口的UI更新

    def _update_selection(self, selected_roi: 'RectROI') -> None:
        """更新ROI选中状态（边框颜色）"""
        self.active_roi = selected_roi  # 设置当前活动ROI
        # 遍历所有ROI，设置边框颜色（选中为绿色，未选中为红色）
        for roi in self.rois.values():
            roi.setPen('g' if roi == selected_roi else 'r')
        # 不需要再次发射 roi_selected 信号，因为 _on_roi_clicked 已经发射过了

    def update_image_data(self, image: np.ndarray) -> None:
        """更新当前图像数据
        image: 已经经过方向校正的NumPy数组
        """
        self.current_image = image
        # 更新所有ROI的图像统计信息
        for roi in self.rois.values():
            roi.update_image_stats(image)


class RectROI(pg.RectROI):
    """自定义矩形ROI, 支持图像统计功能"""
    _counter = 0  # 类变量，用于生成唯一ID

    def __init__(self, image_item: pg.ImageItem, unique_id: Optional[int] = None, name: Optional[str] = None, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.image_item = image_item  # 关联的图像项

        if unique_id is not None:
            self.unique_id = unique_id
            RectROI._counter = max(RectROI._counter, unique_id) 
        else:
            self.unique_id = self._generate_id()  
        if name is not None: 
            self.name = name
        else:
            self.name = f"ROI{self.unique_id}"  

        self.image_stats: Dict[str, float] = {
            'GrayMax': 0,  
            'GrayMin': 0,  
            'GrayMean': 0,  
            'GrayRange': 0  
        }
        self._position = (0.0, 0.0)  # ROI位置 (这里我们希望存储左上角为原点的坐标)
        self._dimensions = (0.0, 0.0)  # ROI尺寸

    @classmethod
    def _generate_id(cls) -> int:
        """生成唯一ID"""
        cls._counter += 1
        return cls._counter

    @classmethod
    def reset_counter(cls, start_value: int = 0) -> None:
        """重置计数器，用于加载数据时避免ID冲突"""
        cls._counter = start_value

    def update_image_stats(self, image: np.ndarray) -> None:
        """更新图像统计信息"""
        try:
            # --- 核心修改：更新位置和尺寸信息，现在PlotWidget的Y轴已经颠倒 (Y向下) ---
            # get current position and size of ROI in pyqtgraph's PlotWidget coordinate system.
            # since ViewBox.invertY(True) is set, (0,0) is top-left, and Y increases downwards.
            current_pos_pg = self.pos() # ROI's bottom-left corner
            current_size_pg = super().size() # ROI's width and height

            # In a Y-down coordinate system where pos() is bottom-left,
            x_display_top_left_origin = current_pos_pg.x()
            y_display_top_left_origin = current_pos_pg.y() 
            
            self._position = (round(x_display_top_left_origin, 2), round(y_display_top_left_origin, 2))
            self._dimensions = (round(current_size_pg.x(), 2), round(current_size_pg.y(), 2))
            # ----------------------------------------------------------------------
            
            # 后续是图像统计信息计算，与坐标显示逻辑独立，保持不变
            region = self.getArrayRegion(image, self.image_item)
            
            if region is None or region.size == 0 or region.shape[0] == 0 or region.shape[1] == 0:
                self.image_stats = {k: 0 for k in self.image_stats}
                return 
            
            if region.dtype != np.uint8:
                region = region.astype(np.uint8)
            
            if len(region.shape) == 3:
                region = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)

            if region.shape[0] >= 2 and region.shape[1] >= 2 and np.std(region) > 0:
                levels = 32  
                quantized_region = (region // (256 // levels)).astype(np.uint8)
                
                if len(np.unique(quantized_region)) > 1:
                    glcm = graycomatrix(quantized_region, distances=[1], angles=[0], levels=levels, symmetric=True, normed=True)
                    energy = graycoprops(glcm, 'energy')[0, 0]
                    correlation = graycoprops(glcm, 'correlation')[0, 0]
                    homogeneity = graycoprops(glcm, 'homogeneity')[0, 0]
                    contrast = graycoprops(glcm, 'contrast')[0, 0]
                else: 
                    energy, correlation, homogeneity, contrast = 0.0, 0.0, 0.0, 0.0
            else: 
                energy, correlation, homogeneity, contrast = 0.0, 0.0, 0.0, 0.0
                

            self.image_stats = {
                'GrayMax': np.max(region),
                'GrayMin': np.min(region),
                'GrayMean': np.mean(region),
                'GrayRange': np.max(region)-np.min(region),
                'Energy': energy,
                'Correlation': correlation,
                'Homogeneity': homogeneity,
                'Contrast': contrast
                }
            
        except Exception as e:
            self.image_stats = {k: 0 for k in self.image_stats} 
            # 错误时，位置和尺寸的更新已在函数开头处理，这里只处理统计信息错误

    @property
    def stats_formatted(self) -> Dict[str, str]:
        """格式化后的统计信息（保留两位小数）"""
        return {k: f"{v:.2f}" for k, v in self.image_stats.items()}

    @property
    def position(self) -> Tuple[float, float]:
        """当前ROI位置 (左上角为原点, Y轴向下), 这将用于显示在表格中。"""
        return self._position

    @property
    def dimensions(self) -> Tuple[float, float]:
        """当前ROI尺寸"""
        return self._dimensions

    def to_dict(self) -> Dict[str, Any]:
        """
        返回 ROI 可序列化的字典表示，用于保存到 TOML 文件。
        注意：此处保存的是 pyqtgraph 内部的左下角为原点、Y轴向下（因为invertY=True）的坐标系统中的 Y 坐标，
        以便加载时能正确重建 ROI 对象。
        """
        pos = self.pos() # 获取 pyqtgraph 内部的左下角坐标
        size = self.size()
        return {
            "unique_id": self.unique_id,
            "name": self.name,
            "pos_x": round(pos.x(), 2),
            "pos_y": round(pos.y(), 2), # 保存 pyqtgraph 内部的 Y 坐标 (现在已经是Y向下)
            "size_x": round(size.x(), 2),
            "size_y": round(size.y(), 2),
        }


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
        self.setAspectLocked(True) # 确保无论窗口如何调整大小，图像的X和Y轴比例都将保持一致。
        
        # --- 核心修改：显式地反转Y轴，使(0,0)在顶部，Y向下增加 ---
        self.getPlotItem().getViewBox().invertY(True)


    def update_image(self, image: np.ndarray) -> None:
        """更新显示图像。
        这里的'image'已经是经过方向校正的NumPy数组。
        """
        self.image_item.setImage(image)  # 设置图像数据
        # 设置显示范围匹配图像尺寸
        # 现在PlotWidget的(0,0)是左上角，Y向下增加。
        # 所以setRange的y范围应该是(0, image.shape[0])
        self.setRange(xRange=[0, image.shape[1]], yRange=[0, image.shape[0]])
 


class MainWindow(QtWidgets.QMainWindow):
    """主窗口"""
    # 定义一个字典来存储属性名和它们的提示文本
    PROPERTY_TOOLTIPS = {
        "ID": "ROI的唯一标识符，系统自动生成。",
        "名称": "ROI的自定义名称，可以在树视图中双击修改。",
        "位置": "ROI左上角的X, Y坐标，表示ROI在图像中的起始位置。",
        "尺寸": "ROI的宽度和高度，表示ROI的像素大小。",
        "最大灰度值": "ROI区域内像素的最大灰度值，反映区域中最亮的点。",
        "最小灰度值": "ROI区域内像素的最小灰度值，反映区域中最暗的点。",
        "平均灰度值": "ROI区域内像素的平均灰度值，反映区域的整体亮度。",
        "灰度值极差": "ROI区域内像素的最大灰度值与最小灰度值之差，反映区域的灰度分布范围。",
        "能量": "衡量图像纹理的均匀性和局部秩序。能量值越大，表示纹理越均匀、越细致，变化越小。",
        "相关性": "衡量像素灰度级之间空间依赖关系的线性度。值越大，表示灰度级之间相关性越强，纹理越粗糙、规律性越强。",
        "均匀性": "衡量图像纹理的局部均匀性。值越大，表示灰度级差异越小，纹理越均匀、越平坦。",
        "对比度": "反映图像纹理的对比度或局部灰度级差异的大小。值越大，表示纹理越深、越粗糙，灰度变化越剧烈。"
    }

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

        # 初始化ROI列表模型 (现在是QTreeView)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["名称", "ID"]) 
        self.treeView.setModel(self.tree_model)

        # 初始化属性表格模型
        self.property_model = QStandardItemModel()
        self.property_model.setHorizontalHeaderLabels(["属性", "值"])
        self.tableView.setModel(self.property_model)
        # 调整表格列宽，使第一列拉伸以适应内容，第二列内容自适应
        self.tableView.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tableView.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)


        # 初始化ROI管理器
        self.roi_manager = ROIManager(
            self.image_viewer,
            self.tree_model,
            self.image_viewer.image_item
        )
        self.roi_manager.roi_selected.connect(self._on_roi_selected_update_ui)
        self.roi_manager.group_selected.connect(self._on_group_selected_update_ui)

        # 设置“添加ROI”按钮初始状态 (未选中分组时禁用)
        self.pushButton_1.setEnabled(False) 
        self.delGroupButton.setEnabled(False) # 初始时，“删除组/ROI”按钮也禁用

    def _setup_camera(self) -> None:
        """初始化摄像头相关组件"""
        self.capture = cv2.VideoCapture()  # 创建视频捕获对象
        self.timer = QTimer()  # 创建定时器
        self.timer.timeout.connect(self._update_camera_frame)  # 定时器超时信号

    def _connect_signals(self) -> None:
        """连接信号槽"""
        self.actionOpenImage.triggered.connect(self.load_image)  # 打开图像菜单
        self.actionOpenCamera.triggered.connect(self.toggle_camera)  # 打开摄像头菜单
        self.actionSaveRoi.triggered.connect(self.save_config)  # 保存ROI配置菜单
        self.actionLoadRoi.triggered.connect(self.load_config)  # 加载ROI配置菜单
        
        self.addGroupButton.clicked.connect(self._add_group) # 添加组按钮
        self.delGroupButton.clicked.connect(self._del_selected_item) # 删除组/ROI按钮
        
        self.pushButton_1.clicked.connect(self._add_roi_to_selected_group)  # 添加ROI按钮
        self.pushButton_2.clicked.connect(self.roi_manager.clear_all_items)  # 清除所有组和ROI按钮
        
        # 树视图选中项变化信号
        self.treeView.selectionModel().currentChanged.connect(self._on_tree_selection_changed)
        # 树视图项数据变化信号（用于修改名称）
        self.tree_model.itemChanged.connect(self._on_item_name_changed)

    def _on_item_name_changed(self, item: QStandardItem) -> None:
        """处理QTreeView中项目名称被手动修改的事件"""
        if item.column() == 0:
            new_name = item.text()
            roi_id = item.data(CustomRoles.RoiIdRole)
            if roi_id is not None and roi_id in self.roi_manager.rois:
                self.roi_manager.rois[roi_id].name = new_name
            
    def _on_tree_selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """
        处理QTreeView中选中项的变化。
        根据选中项是组还是ROI，更新按钮状态和属性表格。
        """
        self._update_property_table(None) # 首先清空属性表

        if not current.isValid():
            # 未选中任何项
            self.roi_manager.set_active_group_item(None) 
            self.roi_manager._update_selection(None) # 取消选中绘图区所有ROI
            self.pushButton_1.setEnabled(False) # 禁用“添加ROI”按钮
            self.delGroupButton.setEnabled(False) # 禁用“删除组/ROI”按钮
            return

        item = self.tree_model.itemFromIndex(current)
        if item is None: 
            return

        # 检查选中项是否为组（顶级项）
        if not current.parent().isValid():
            # 这是组项
            self.roi_manager.set_active_group_item(item)
            self.roi_manager._update_selection(None) # 取消选中绘图区任何活动的ROI
            self.pushButton_1.setEnabled(True) # 启用“添加ROI”按钮
            self.delGroupButton.setEnabled(True) # 启用“删除组”按钮
            self._update_property_table(None) # 未选中ROI，清空表格
        else:
            # 这是ROI项（组的子项）
            roi_id = item.data(CustomRoles.RoiIdRole)
            if roi_id is not None and roi_id in self.roi_manager.rois:
                roi = self.roi_manager.rois[roi_id]
                self.roi_manager._update_selection(roi) # 在绘图区选中此ROI
                self.roi_manager.set_active_group_item(item.parent()) # 将父组设为活动组
                self.pushButton_1.setEnabled(True) # 仍然启用“添加ROI”（可以添加到父组）
                self.delGroupButton.setEnabled(True) # 启用“删除ROI”按钮
            else:
                self.roi_manager.set_active_group_item(None)
                self.roi_manager._update_selection(None)
                self.pushButton_1.setEnabled(False)
                self.delGroupButton.setEnabled(False)
    
    def _on_roi_selected_update_ui(self, roi: Optional['RectROI']) -> None:
        """当ROIManager发出roi_selected信号时，更新属性表并选中树视图中的对应项"""
        self._update_property_table(roi)
        if roi:
            for group_row in range(self.tree_model.rowCount()):
                group_item = self.tree_model.item(group_row, 0)
                if group_item:
                    for roi_row in range(group_item.rowCount()):
                        roi_name_item = group_item.child(roi_row, 0)
                        if roi_name_item and roi_name_item.data(CustomRoles.RoiIdRole) == roi.unique_id:
                            index = self.tree_model.indexFromItem(roi_name_item)
                            if index != self.treeView.currentIndex():
                                self.treeView.selectionModel().setCurrentIndex(
                                    index, QtCore.QItemSelectionModel.ClearAndSelect
                                )
                            return
        else:
            self.treeView.selectionModel().clearSelection()


    def _on_group_selected_update_ui(self, group_item: Optional[QStandardItem]) -> None:
        pass 

    def _add_group(self) -> None:
        """添加一个新组"""
        group_item = self.roi_manager.add_group()
        index = self.tree_model.indexFromItem(group_item)
        self.treeView.selectionModel().setCurrentIndex(
            index, QtCore.QItemSelectionModel.ClearAndSelect
        )

    def _del_selected_item(self) -> None:
        """删除QTreeView中当前选中的组或ROI"""
        current_index = self.treeView.currentIndex()
        if not current_index.isValid():
            QtWidgets.QMessageBox.warning(self, "删除失败", "请先选中一个组或ROI节点！")
            return

        item = self.tree_model.itemFromIndex(current_index)
        if item is None:
            return

        if not current_index.parent().isValid():
            reply = QtWidgets.QMessageBox.question(
                self, "删除确认", f"确定要删除分组 '{item.text()}' 及其下的所有ROI吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                rois_to_delete = []
                for row in range(item.rowCount()):
                    roi_name_item = item.child(row, 0)
                    if roi_name_item:
                        roi_id = roi_name_item.data(CustomRoles.RoiIdRole)
                        if roi_id is not None:
                            rois_to_delete.append(roi_id)
                
                for roi_id in rois_to_delete:
                    self.roi_manager.remove_roi_by_id(roi_id)
                
                self.tree_model.removeRow(current_index.row())
                self.roi_manager.set_active_group_item(None) 
                self.roi_manager._update_selection(None) 
                self._update_property_table(None) 
                QtWidgets.QMessageBox.information(self, "删除成功", f"分组 '{item.text()}' 及其下的ROI已删除。")

        else:
            reply = QtWidgets.QMessageBox.question(
                self, "删除确认", f"确定要删除ROI '{item.text()}' 吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                roi_id = item.data(CustomRoles.RoiIdRole)
                if roi_id is not None:
                    self.roi_manager.remove_roi_by_id(roi_id)
                    self.roi_manager._update_selection(None) 
                    self._update_property_table(None) 
                    QtWidgets.QMessageBox.information(self, "删除成功", f"ROI '{item.text()}' 已删除。")
                else:
                    QtWidgets.QMessageBox.warning(self, "删除失败", "无法获取选中ROI的ID。")

    def _add_roi_to_selected_group(self) -> None:
        """添加ROI到当前选中的组"""
        if self.roi_manager.active_group_item:
            self.roi_manager.add_roi()
        else:
            QtWidgets.QMessageBox.warning(self, "添加ROI失败", "请先在左侧树视图中选中一个分组，再添加ROI。")


    def save_config(self) -> None:
        """保存ROI配置到文件 (包含组信息)"""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存配置", "", "ROI配置 (*.toml)"
        )
        if not path:
            return

        rois_by_group_data: Dict[str, List[Dict[str, Any]]] = {}

        for group_row in range(self.tree_model.rowCount()):
            group_item = self.tree_model.item(group_row, 0) 
            if group_item:
                group_name = group_item.text()
                current_group_rois_list: List[Dict[str, Any]] = []

                for roi_child_row in range(group_item.rowCount()):
                    roi_name_item = group_item.child(roi_child_row, 0) 
                    if roi_name_item:
                        roi_id = roi_name_item.data(CustomRoles.RoiIdRole) 
                        if roi_id is not None and roi_id in self.roi_manager.rois:
                            roi_obj = self.roi_manager.rois[roi_id]
                            current_group_rois_list.append(roi_obj.to_dict()) 

                rois_by_group_data[group_name] = current_group_rois_list

        try:
            toml_data = {"rois": rois_by_group_data}
            
            with open(path, "w", encoding="utf-8") as f:
                toml.dump(toml_data, f)
            QtWidgets.QMessageBox.information(self, "保存成功", "ROI配置已成功保存！")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "保存失败", f"保存ROI配置失败: {e}")
            print(f"ROI配置文件写入失败: {e}")

    def load_config(self) -> None:
        """加载ROI配置文件 (包含组信息)"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "加载配置", "", "ROI配置 (*.toml)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = toml.load(f)
            
            self.roi_manager.clear_all_items()
            RectROI.reset_counter(0) 

            rois_by_group_data = config_data.get("rois", {}) 
            if not isinstance(rois_by_group_data, dict):
                raise ValueError("TOML文件中的'rois'部分不是字典或缺失。")

            max_roi_id = 0
            
            for group_name, rois_list_for_group in rois_by_group_data.items():
                group_item = self.roi_manager.add_group(group_name=group_name) 
                
                self.roi_manager.set_active_group_item(group_item) 
                
                if not isinstance(rois_list_for_group, list):
                    print(f"警告: 组 '{group_name}' 的ROI不是列表。跳过。")
                    continue

                for roi_dict in rois_list_for_group:
                    if not isinstance(roi_dict, dict):
                        print(f"警告: 组 '{group_name}' 中的ROI项不是字典。跳过。")
                        continue

                    unique_id = roi_dict.get('unique_id')
                    name = roi_dict.get('name')
                    pos_x = roi_dict.get('pos_x', 50)
                    pos_y = roi_dict.get('pos_y', 50) # 这个pos_y现在也是Y向下坐标系了
                    size_x = roi_dict.get('size_x', 100)
                    size_y = roi_dict.get('size_y', 100)
                    
                    if unique_id is not None:
                        max_roi_id = max(max_roi_id, unique_id)

                    self.roi_manager.add_roi(
                        x=pos_x, 
                        y=pos_y, 
                        w=size_x, 
                        h=size_y, 
                        unique_id=unique_id, 
                        name=name
                    )
                
            self.treeView.selectionModel().clearSelection()
            self.roi_manager.set_active_group_item(None) 
            self.roi_manager._update_selection(None) 
            self._update_property_table(None) 
            self.pushButton_1.setEnabled(False) 
            self.delGroupButton.setEnabled(False) 

            RectROI.reset_counter(max_roi_id + 1) 
            QtWidgets.QMessageBox.information(self, "加载成功", "ROI配置已成功加载！")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "加载失败", f"加载ROI配置失败: {e}")
            print(f"ROI配置文件读取失败: {e}")


    def load_image(self) -> None:
        """加载图像文件"""
        try:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "打开图像", "", "Images (*.jpg *.png *.bmp)")
            if not path:
                return

            image = cv2.imread(path)
            if image is None:
                raise ValueError("无法读取图像文件")

            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            self._process_image(image)  
        except Exception as e:
            self._show_error(f"加载图像失败: {str(e)}")  

    def _process_image(self, image: np.ndarray) -> None:
        """
        处理并显示图像。
        此方法现在包含对图像进行方向校正的逻辑。
        """
        # pyqtgraph在您的环境中会默认逆时针旋转图片90度，所以需要顺时针90度抵消。
        # 旋转后，图像的形状会从 (H, W) 变为 (W, H)。
        corrected_image = np.rot90(image, k=-1)

        self.image_viewer.update_image(corrected_image)  
        # 更新ROI管理器中的图像数据，统计计算基于校正后的图像。
        # 因为ImageItem的Y轴已经颠倒，ROI现在会在正确的方向进行计算。
        self.roi_manager.update_image_data(corrected_image)  

    def toggle_camera(self) -> None:
        """切换摄像头状态"""
        if self.timer.isActive():
            self._stop_camera()  
        else:
            self._start_camera()  

    def _start_camera(self) -> None:
        """启动摄像头"""
        if not self.capture.open(0):  
            self._show_error("无法打开摄像头")
            return
        self.timer.start(30)  

    def _stop_camera(self) -> None:
        """停止摄像头"""
        self.timer.stop()  
        self.capture.release()  

    def _update_camera_frame(self) -> None:
        """更新摄像头帧"""
        ret, frame = self.capture.read()  
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  
            self._process_image(frame)  

    def _update_property_table(self, roi: Optional[RectROI]) -> None:
        """更新属性表格"""
        self.property_model.clear()  
        self.property_model.setHorizontalHeaderLabels(["属性", "值"]) 

        if roi is None:
            return

        properties = {
            "ID": roi.unique_id,
            "名称": roi.name,
            "位置": f"({roi.position[0]}, {roi.position[1]})", 
            "尺寸": f"({roi.dimensions[0]}, {roi.dimensions[1]})",
            "最大灰度值": roi.stats_formatted.get('GrayMax', 'N/A'),
            "最小灰度值": roi.stats_formatted.get('GrayMin', 'N/A'),
            "平均灰度值": roi.stats_formatted.get('GrayMean', 'N/A'),
            "灰度值极差": roi.stats_formatted.get('GrayRange', 'N/A'),
            "能量": roi.stats_formatted.get('Energy', 'N/A'),
            "相关性": roi.stats_formatted.get('Correlation', 'N/A'),
            "均匀性": roi.stats_formatted.get('Homogeneity', 'N/A'),
            "对比度": roi.stats_formatted.get('Contrast', 'N/A')
        }

        for row, (key, value) in enumerate(properties.items()):
            key_item = QStandardItem(str(key))
            tooltip_text = self.PROPERTY_TOOLTIPS.get(key, "") 
            if tooltip_text: 
                key_item.setToolTip(tooltip_text)
            
            value_item = QStandardItem(str(value))

            self.property_model.setItem(row, 0, key_item)
            self.property_model.setItem(row, 1, value_item)

    def _show_error(self, message: str) -> None:
        """显示错误信息"""
        QtWidgets.QMessageBox.critical(self, "错误", message)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """窗口关闭事件处理"""
        self._stop_camera()  
        super().closeEvent(event)


if __name__ == "__main__":
    os.chdir(sys.path[0])  
    app = QtWidgets.QApplication(sys.argv)  
    window = MainWindow()  
    window.show()  
    sys.exit(app.exec_())  

