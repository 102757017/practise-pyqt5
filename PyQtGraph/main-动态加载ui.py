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

# Custom data roles for QStandardItem
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
        self.current_image: Optional[np.ndarray] = None  # 当前显示的图像
        self.active_roi: Optional['RectROI'] = None  # 当前活动的ROI对象
        self.rois: Dict[int, 'RectROI'] = {}  # 存储所有ROI的字典，键是ROI的ID
        self.active_group_item: Optional[QStandardItem] = None # 当前选中的QStandardItem (group item)

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
        group_item.setEditable(True)
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
        roi.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)
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
            print(f"Warning: ROI with ID {roi_id} not found.")

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
        self.roi_selected.emit(roi) # Re-emit to trigger UI update in main window

    def _update_selection(self, selected_roi: 'RectROI') -> None:
        """更新ROI选中状态（边框颜色）"""
        self.active_roi = selected_roi  # 设置当前活动ROI
        # 遍历所有ROI，设置边框颜色（选中为绿色，未选中为红色）
        for roi in self.rois.values():
            roi.setPen('g' if roi == selected_roi else 'r')
        # 不需要再次emit roi_selected，因为 _on_roi_clicked 已经emit了

    def update_image_data(self, image: np.ndarray) -> None:
        """更新当前图像数据"""
        self.current_image = image
        # 更新所有ROI的图像统计信息
        for roi in self.rois.values():
            roi.update_image_stats(image)


class RectROI(pg.RectROI):
    """自定义矩形ROI，支持图像统计功能"""
    _counter = 0  # 类变量，用于生成唯一ID

    def __init__(self, image_item: pg.ImageItem, unique_id: Optional[int] = None, name: Optional[str] = None, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.image_item = image_item  # 关联的图像项

        # 根据是否提供了 unique_id 来设置
        if unique_id is not None:
            self.unique_id = unique_id
            # 更新类计数器，确保新生成的ID不会与已加载的ID冲突
            RectROI._counter = max(RectROI._counter, unique_id) # Ensure counter is always ahead
        else:
            self.unique_id = self._generate_id()  # 唯一标识符
        # 根据是否提供了 name 来设置
        if name is not None:
            self.name = name
        else:
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

    @classmethod
    def reset_counter(cls, start_value: int = 0) -> None:
        """重置计数器，用于加载数据时避免ID冲突"""
        cls._counter = start_value

    def update_image_stats(self, image: np.ndarray) -> None:
        """更新图像统计信息"""
        try:
            # 获取ROI区域内的图像数据
            # getArrayRegion will return None if the ROI is outside image bounds or 0-sized
            region = self.getArrayRegion(image, self.image_item)
            
            if region is None or region.size == 0 or region.shape[0] == 0 or region.shape[1] == 0:
                # print("ROI region is empty or invalid, cannot calculate stats.")
                # Optionally, reset stats to 0 or leave them as they are
                self.image_stats = {k: 0 for k in self.image_stats}
                self._position = (round(self.pos().x(), 2), round(self.pos().y(), 2))
                size = super().size()
                self._dimensions = (round(size.x(), 2), round(size.y(), 2))
                return
            
            # 转换为8位无符号整数类型（OpenCV常用类型）
            if region.dtype != np.uint8:
                region = region.astype(np.uint8)
            
            # 如果是彩色图像，转换为灰度
            if len(region.shape) == 3:
                region = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)


            # GLCM calculation
            # Only compute GLCM if region is large enough (at least 2x2 pixels)
            # and has some variation (not all pixels are the same)
            if region.shape[0] >= 2 and region.shape[1] >= 2 and np.std(region) > 0:
                levels = 8  # GLCM的灰度级数
                # Quantize region to desired levels. Essential for GLCM on continuous data.
                quantized_region = (region // (256 // levels)).astype(np.uint8)
                
                # Check for unique values in quantized region, if only one, GLCM fails
                if len(np.unique(quantized_region)) > 1:
                    glcm = graycomatrix(
                        quantized_region, 
                        distances=[1], 
                        angles=[0],
                        levels=levels, 
                        symmetric=True, 
                        normed=True # Normalized GLCM for prop calculation
                        )
                    
                    # Calculate texture features
                    energy = graycoprops(glcm, 'energy')[0, 0]
                    correlation = graycoprops(glcm, 'correlation')[0, 0]
                    homogeneity = graycoprops(glcm, 'homogeneity')[0, 0]
                    contrast = graycoprops(glcm, 'contrast')[0, 0]
                else:
                    energy, correlation, homogeneity, contrast = 0.0, 0.0, 0.0, 0.0
            else:
                energy, correlation, homogeneity, contrast = 0.0, 0.0, 0.0, 0.0

            # Calculate and update statistical information
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
            
            # Update position and dimensions information
            self._position = (round(self.pos().x(), 2), round(self.pos().y(), 2))
            size = super().size()  # Explicitly call parent's size method
            self._dimensions = (round(size.x(), 2), round(size.y(), 2))
            
        except Exception as e:
            # print(f"Error updating image stats for ROI {self.name}: {str(e)}")
            # If an error occurs, set stats to 0 or N/A
            self.image_stats = {k: 0 for k in self.image_stats} # Reset on error
            self._position = (round(self.pos().x(), 2), round(self.pos().y(), 2))
            size = super().size()
            self._dimensions = (round(size.x(), 2), round(size.y(), 2))

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

    def to_dict(self) -> Dict[str, Any]:
        """
        返回 ROI 可序列化的字典表示，用于保存到 TOML 文件。
        """
        pos = self.pos()
        size = self.size()
        return {
            "unique_id": self.unique_id,
            "name": self.name,
            "pos_x": round(pos.x(), 2),
            "pos_y": round(pos.y(), 2),
            "size_x": round(size.x(), 2),
            "size_y": round(size.y(), 2),
        }

# GroupItem class is removed as it's no longer necessary for the new TOML structure.


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

        # 初始化ROI列表模型 (现在是QTreeView)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["名称", "ID"]) # 注意：这里是“名称”而不是“ROI名称”了
        self.treeView.setModel(self.tree_model)

        # 初始化属性表格模型
        self.property_model = QStandardItemModel()
        self.property_model.setHorizontalHeaderLabels(["属性", "值"])
        self.tableView.setModel(self.property_model)

        # 初始化ROI管理器
        self.roi_manager = ROIManager(
            self.image_viewer,
            self.tree_model,
            self.image_viewer.image_item
        )
        self.roi_manager.roi_selected.connect(self._on_roi_selected_update_ui)
        self.roi_manager.group_selected.connect(self._on_group_selected_update_ui)

        # 设置Add ROI按钮初始状态 (未选中分组时禁用)
        self.pushButton_1.setEnabled(False) 
        self.delGroupButton.setEnabled(False) # 初始时，DelGroup按钮也禁用

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
        # 仅处理第一列（名称）的数据变化
        if item.column() == 0:
            new_name = item.text()
            
            # 检查是否是ROI项
            roi_id = item.data(CustomRoles.RoiIdRole)
            if roi_id is not None:
                if roi_id in self.roi_manager.rois:
                    roi = self.roi_manager.rois[roi_id]
                    roi.name = new_name
                    # print(f"ROI ID {roi_id} 的名称已更新为: {new_name}")
            else: # 可能是组名，目前组名没有对应对象，不需要额外处理
                # print(f"Group name updated to: {new_name}")
                pass 

    def _on_tree_selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """
        处理QTreeView中选中项的变化。
        根据选中项是组还是ROI，更新按钮状态和属性表格。
        """
        self._update_property_table(None) # Clear property table first

        if not current.isValid():
            # Nothing selected
            self.roi_manager.set_active_group_item(None) 
            self.roi_manager._update_selection(None) # De-select all ROIs in plot
            self.pushButton_1.setEnabled(False) # Add ROI button disabled
            self.delGroupButton.setEnabled(False) # Del Group/ROI button disabled
            return

        item = self.tree_model.itemFromIndex(current)
        if item is None: 
            return

        # Check if the selected item is a group (top-level item)
        if not current.parent().isValid():
            # This is a group item
            self.roi_manager.set_active_group_item(item)
            self.roi_manager._update_selection(None) # De-select any active ROI in plot
            self.pushButton_1.setEnabled(True) # Enable Add ROI button
            self.delGroupButton.setEnabled(True) # Enable Del Group button
            self._update_property_table(None) # No ROI selected, clear table
        else:
            # This is an ROI item (child of a group)
            roi_id = item.data(CustomRoles.RoiIdRole)
            if roi_id is not None and roi_id in self.roi_manager.rois:
                roi = self.roi_manager.rois[roi_id]
                self.roi_manager._update_selection(roi) # Select this ROI in plot
                self.roi_manager.set_active_group_item(item.parent()) # Set parent group as active
                self.pushButton_1.setEnabled(True) # Still enable Add ROI (can add to parent group)
                self.delGroupButton.setEnabled(True) # Enable Del ROI button
            else:
                # Should not happen if items are managed correctly
                self.roi_manager.set_active_group_item(None)
                self.roi_manager._update_selection(None)
                self.pushButton_1.setEnabled(False)
                self.delGroupButton.setEnabled(False)
    
    def _on_roi_selected_update_ui(self, roi: Optional['RectROI']) -> None:
        """当ROIManager发出roi_selected信号时，更新属性表并选中树视图中的对应项"""
        self._update_property_table(roi)
        if roi:
            # Find and select the item in the treeView
            for group_row in range(self.tree_model.rowCount()):
                group_item = self.tree_model.item(group_row, 0)
                if group_item:
                    for roi_row in range(group_item.rowCount()):
                        roi_name_item = group_item.child(roi_row, 0)
                        if roi_name_item and roi_name_item.data(CustomRoles.RoiIdRole) == roi.unique_id:
                            index = self.tree_model.indexFromItem(roi_name_item)
                            # Only set current if not already current to avoid recursion
                            if index != self.treeView.currentIndex():
                                self.treeView.selectionModel().setCurrentIndex(
                                    index, QtCore.QItemSelectionModel.ClearAndSelect
                                )
                            return
        else:
            # If roi is None, clear treeView selection as well
            self.treeView.selectionModel().clearSelection()


    def _on_group_selected_update_ui(self, group_item: Optional[QStandardItem]) -> None:
        """当ROIManager发出group_selected信号时，主要用于调试或未来扩展"""
        # print(f"Group selected in ROIManager: {group_item.text() if group_item else 'None'}")
        pass # UI state is mostly handled by _on_tree_selection_changed

    def _add_group(self) -> None:
        """添加一个新组"""
        group_item = self.roi_manager.add_group()
        # Automatically select the newly created group
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

        # Determine if it's a group or an ROI
        if not current_index.parent().isValid():
            # This is a group node
            reply = QtWidgets.QMessageBox.question(
                self, "删除确认", f"确定要删除分组 '{item.text()}' 及其下的所有ROI吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                # Iterate through children (ROIs) and remove them from ROIManager
                rois_to_delete = []
                for row in range(item.rowCount()):
                    roi_name_item = item.child(row, 0)
                    if roi_name_item:
                        roi_id = roi_name_item.data(CustomRoles.RoiIdRole)
                        if roi_id is not None:
                            rois_to_delete.append(roi_id)
                
                for roi_id in rois_to_delete:
                    self.roi_manager.remove_roi_by_id(roi_id)
                
                # Finally, remove the group from the model
                self.tree_model.removeRow(current_index.row())
                # After deletion, clear selection states
                self.roi_manager.set_active_group_item(None) 
                self.roi_manager._update_selection(None) 
                self._update_property_table(None) 
                QtWidgets.QMessageBox.information(self, "删除成功", f"分组 '{item.text()}' 及其下的ROI已删除。")

        else:
            # This is an ROI node
            reply = QtWidgets.QMessageBox.question(
                self, "删除确认", f"确定要删除ROI '{item.text()}' 吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                roi_id = item.data(CustomRoles.RoiIdRole)
                if roi_id is not None:
                    self.roi_manager.remove_roi_by_id(roi_id)
                    # The remove_roi_by_id will trigger _remove_from_tree_model
                    # which handles removing the item from its parent.
                    # After deletion, clear ROI selection states
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
            print("未选择保存路径")
            return

        # This will be a dictionary where keys are group names and values are lists of ROI dictionaries
        rois_by_group_data: Dict[str, List[Dict[str, Any]]] = {}

        # Iterate through top-level items (groups) in the QTreeView model
        for group_row in range(self.tree_model.rowCount()):
            group_item = self.tree_model.item(group_row, 0) # Get the QStandardItem for the group name
            if group_item:
                group_name = group_item.text()
                current_group_rois_list: List[Dict[str, Any]] = []

                # Iterate through children (ROIs) of the current group
                for roi_child_row in range(group_item.rowCount()):
                    roi_name_item = group_item.child(roi_child_row, 0) # Get the QStandardItem for ROI name
                    if roi_name_item:
                        roi_id = roi_name_item.data(CustomRoles.RoiIdRole) # Retrieve ROI ID from custom role
                        if roi_id is not None and roi_id in self.roi_manager.rois:
                            roi_obj = self.roi_manager.rois[roi_id]
                            current_group_rois_list.append(roi_obj.to_dict()) # Add ROI's serializable dict

                rois_by_group_data[group_name] = current_group_rois_list

        try:
            # Wrap rois_by_group_data in a dictionary with a top-level key "rois"
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
            print("未选择加载路径")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = toml.load(f)
            
            # Clear existing data before loading new
            self.roi_manager.clear_all_items()
            RectROI.reset_counter(0) # Reset ROI ID counter before loading

            # Get the top-level 'rois' table, which is expected to be a dictionary
            # where keys are group names and values are lists of ROI dictionaries.
            rois_by_group_data = config_data.get("rois", {}) 
            if not isinstance(rois_by_group_data, dict):
                raise ValueError("TOML file 'rois' section is not a dictionary or is missing.")

            max_roi_id = 0
            
            # Iterate through the groups (keys of rois_by_group_data)
            for group_name, rois_list_for_group in rois_by_group_data.items():
                group_item = self.roi_manager.add_group(group_name=group_name) # Add group to model

                # Temporarily set the active_group_item for the ROIManager
                # so that subsequent calls to roi_manager.add_roi correctly associate the ROI
                # with this specific group_item in the tree model.
                self.roi_manager.set_active_group_item(group_item) 
                
                if not isinstance(rois_list_for_group, list):
                    print(f"Warning: ROIs for group '{group_name}' is not a list. Skipping.")
                    continue

                for roi_dict in rois_list_for_group:
                    if not isinstance(roi_dict, dict):
                        print(f"Warning: ROI item in group '{group_name}' is not a dictionary. Skipping.")
                        continue

                    unique_id = roi_dict.get('unique_id')
                    name = roi_dict.get('name')
                    pos_x = roi_dict.get('pos_x', 50)
                    pos_y = roi_dict.get('pos_y', 50)
                    size_x = roi_dict.get('size_x', 100)
                    size_y = roi_dict.get('size_y', 100)
                    
                    if unique_id is not None:
                        max_roi_id = max(max_roi_id, unique_id)

                    # roi_manager.add_roi uses self.roi_manager.active_group_item internally
                    self.roi_manager.add_roi(
                        x=pos_x, 
                        y=pos_y, 
                        w=size_x, 
                        h=size_y, 
                        unique_id=unique_id, 
                        name=name
                    )
                
            # After all groups and ROIs are loaded, clear any selection state in the UI.
            self.treeView.selectionModel().clearSelection()
            self.roi_manager.set_active_group_item(None) # Ensure ROIManager's active group is clear
            self.roi_manager._update_selection(None) # Ensure plot ROIs are deselected
            self._update_property_table(None) # Clear property table
            self.pushButton_1.setEnabled(False) # Add ROI button disabled
            self.delGroupButton.setEnabled(False) # Del Group/ROI button disabled


            # After loading all ROIs, ensure the counter is correctly set for future new ROIs
            RectROI.reset_counter(max_roi_id + 1) # Set counter to max_roi_id + 1 for next unique ID
            QtWidgets.QMessageBox.information(self, "加载成功", "ROI配置已成功加载！")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "加载失败", f"加载ROI配置失败: {e}")
            print(f"ROI配置文件读取失败: {e}")


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
        # 尝试打开默认摄像头，或者根据需要指定摄像头索引
        if not self.capture.open(0):  
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
            # frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)  # 旋转90度 (根据需要调整)
            self._process_image(frame)  # 处理并显示图像

    def _update_property_table(self, roi: Optional[RectROI]) -> None:
        """更新属性表格"""
        self.property_model.clear()  # 清空表格
        self.property_model.setHorizontalHeaderLabels(["属性", "值"]) # 重新设置表头

        if roi is None:
            return

        # 准备要显示的属性数据
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
