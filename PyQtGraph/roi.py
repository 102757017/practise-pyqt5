import sys
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
from PIL import Image

class ROIExample(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQtGraph ROI Demo - 2025.04.16")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建主部件和布局
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        layout = QtWidgets.QVBoxLayout(main_widget)
        
        # 创建图形显示区域
        self.plot = pg.PlotWidget()
        self.plot.showAxis('bottom', show=False)  # 隐藏底部坐标轴
        self.plot.showAxis('left', show=False)    # 隐藏左侧坐标轴
        self.plot.setMenuEnabled(False)  # 禁用右键菜单
        self.img_item = pg.ImageItem()
        self.plot.addItem(self.img_item)
        layout.addWidget(self.plot)
        
        # 创建统计信息显示
        self.stats_label = QtWidgets.QLabel("ROI统计信息:")
        self.stats_table = QtWidgets.QTableWidget(0, 2)
        self.stats_table.setHorizontalHeaderLabels(["指标", "值"])
        layout.addWidget(self.stats_label)
        layout.addWidget(self.stats_table)
        
        # 初始化ROI相关参数
        self.roi_items = []
        self.current_roi = None
        
        # 加载示例图像
        self.load_image()
        
        # 创建不同类型的ROI
        self.create_roi('rect', pos=(100, 100), size=(80, 60))


    def load_image(self):
        """加载示例图像[1](@ref)"""
        img = Image.open("sample_image.jpg")  # 替换为你的图片路径
        img_array = np.array(img)
        self.img_item.setImage(img_array)
        self.plot.setRange(xRange=[0, img_array.shape[1]], yRange=[0, img_array.shape[0]])

    def create_roi(self, roi_type,**kwargs):
        """创建指定类型的ROI[1,2](@ref)"""
        if roi_type == 'rect':
            roi = pg.RectROI(
                pos=kwargs.get('pos', [0, 0]), # 初始位置
                size=kwargs.get('size', [100, 100]), # 初始大小
                pen={'color': 'r', 'width': 2},
                movable=True,
                rotatable=False,
                removable=True    #当选择删除ROI的菜单时，ROI会发出sigRemoveRequested 信号
            )
            #pg.RectROI 的本地坐标系是以其左下角为原点 (0, 0)，右上角为 (1, 1)。第二个参数是缩放的参考点。
            roi.addScaleHandle((1, 0), (0, 1)) # 右上角
            roi.addScaleHandle((0, 1), (1, 0)) # 左上角
            roi.addScaleHandle((0, 0), (1, 1)) # 左下角


        
        roi.sigRegionChanged.connect(self.update_stats)
        self.plot.addItem(roi)
        self.roi_items.append(roi)

    def update_stats(self):
        """实时更新ROI区域统计信息[1](@ref)"""
        if not self.roi_items:
            return
        
        stats = []
        for roi in self.roi_items:
            # 获取ROI区域数据[2](@ref)
            data = roi.getArrayRegion(self.img_item.image, self.img_item)
            
            if data is not None:
                # 计算统计指标
                stats.append({
                    "类型": roi.__class__.__name__,
                    "最小值": np.nanmin(data),
                    "最大值": np.nanmax(data),
                    "均值": np.nanmean(data),
                    "面积": np.count_nonzero(~np.isnan(data))
                })
        
        # 更新表格显示
        self.stats_table.setRowCount(len(stats))
        for row, stat in enumerate(stats):
            self.stats_table.setItem(row, 0, QtWidgets.QTableWidgetItem(stat["类型"]))
            self.stats_table.setItem(row, 1, QtWidgets.QTableWidgetItem(
                f"Min:{stat['最小值']:.1f} Max:{stat['最大值']:.1f}\n"
                f"Mean:{stat['均值']:.1f} Area:{stat['面积']}"
            ))

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ROIExample()
    window.show()
    sys.exit(app.exec_())
