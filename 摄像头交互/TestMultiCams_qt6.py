import sys
import os
os.environ["QT_MEDIA_BACKEND"] = "windows" # 设置环境变量,否则可能导致摄像头列表为空
import math
from datetime import datetime
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QPushButton, QMessageBox, QMenu, QSizePolicy
)
from PyQt6.QtGui import QImage, QAction, QPainter
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect

from PyQt6.QtMultimedia import (
    QCamera, QCameraDevice, QMediaDevices,
    QImageCapture, QMediaCaptureSession, QCameraFormat
)
from PyQt6.QtMultimediaWidgets import QVideoWidget

# --- 配置参数 ---
# 这不再是预览窗口的固定尺寸，而是期望的宽高比和照片尺寸
PHOTO_WIDTH = 800
PHOTO_HEIGHT = 600
START_CAMERA_INDEX = 0
END_CAMERA_INDEX = 8 # 增加数量以测试布局
SAVE_IMAGE_DIR = "captured_images_pyqt6"


class CopyableLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_action = QAction("复制", self)
        copy_action.setEnabled(self.hasSelectedText())
        copy_action.triggered.connect(self.copy_selection)
        menu.addAction(copy_action)
        menu.exec(event.globalPos())

    def copy_selection(self):
        if self.hasSelectedText():
            QApplication.clipboard().setText(self.selectedText())


class VideoContainer(QWidget):
    """
    一个可以缩放的容器，但能强制其内部的QVideoWidget保持固定的宽高比。
    """
    def __init__(self, aspect_w, aspect_h, parent=None):
        super().__init__(parent)
        self.aspect_ratio = aspect_w / aspect_h
        
        # 设置尺寸策略为可扩展，这样它才能在布局中缩放
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # 创建真正的视频显示控件，作为这个容器的子控件
        self._video_widget = QVideoWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")

    def video_widget(self) -> QVideoWidget:
        """返回内部的QVideoWidget实例，以便外部连接。"""
        return self._video_widget

    def resizeEvent(self, event):
        """当容器大小改变时，重新计算内部VideoWidget的大小和位置。"""
        super().resizeEvent(event)
        
        container_size = self.size()
        w = container_size.width()
        h = container_size.height()

        if w / h > self.aspect_ratio:  # 容器太宽
            new_h = h
            new_w = int(h * self.aspect_ratio)
            x_offset = (w - new_w) // 2
            y_offset = 0
        else:  # 容器太高
            new_w = w
            new_h = int(w / self.aspect_ratio)
            x_offset = 0
            y_offset = (h - new_h) // 2
            
        # 将内部的video_widget居中放置并设置正确的大小
        self._video_widget.setGeometry(x_offset, y_offset, new_w, new_h)

    def sizeHint(self):
        """提供一个合理的初始建议尺寸。"""
        return QSize(PHOTO_WIDTH, PHOTO_HEIGHT)

# --- 单个摄像头界面和逻辑封装 ---
class CameraWidget(QWidget):
    activated = pyqtSignal()
    activation_failed = pyqtSignal(str)

    def __init__(self, camera_device: QCameraDevice, app_camera_index: int, parent=None):
        super().__init__(parent)
        self.camera_device = camera_device
        self.app_camera_index = app_camera_index
        self.camera_description = camera_device.description()
        
        raw_id = camera_device.id().data().decode('utf-8', 'ignore')
        self.device_id_str = self.parse_device_id(raw_id)

        self.camera = None
        self.image_capture = None
        self.capture_session = None
        self.viewfinder = None # 这将指向VideoContainer内部的QVideoWidget
        self._is_capturing_photo = False
        self.last_capture_timestamp = ""
        
        self.init_ui()

    def parse_device_id(self, raw_id: str) -> str:
        try:
            parts = raw_id.split('#')
            if len(parts) >= 3:
                return (parts[1] + '#' + parts[2]).upper()
        except Exception:
            return raw_id.strip('\\?').split('{')[0]
        return raw_id.upper()
        
    def init_ui(self):
        # 主布局，让所有内容垂直排列
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(5) # 视频和标签之间的一点间距

        # 1. 创建并添加我们新的、可缩放的VideoContainer
        #    它将负责保持视频的4:3宽高比
        self.video_container = VideoContainer(PHOTO_WIDTH, PHOTO_HEIGHT)
        self.video_container.setStyleSheet("border: 2px solid gray; background-color: #111;")
        self.layout.addWidget(self.video_container)

        # 2. 创建状态标签
        self.status_label = QLabel(f"摄像头 {self.app_camera_index} ({self.camera_description})")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.layout.addWidget(self.status_label)

        # 3. 创建可复制的地址标签
        self.address_label = CopyableLabel(self.device_id_str)
        self.address_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.address_label.setWordWrap(True)
        self.address_label.setStyleSheet("font-size: 9pt; color: #444;")
        self.layout.addWidget(self.address_label)
        
        # 4. 让标签占据固定高度，视频容器占据所有剩余空间
        self.layout.setStretch(0, 1) # 第0个控件(video_container)的拉伸因子为1
        self.layout.setStretch(1, 0) # 第1个控件(status_label)的拉伸因子为0
        self.layout.setStretch(2, 0) # 第2个控件(address_label)的拉伸因子为0
        
        self.setLayout(self.layout)

    def start_it_up(self):
        print(f"摄像头 {self.app_camera_index}: 准备启动，设备地址: {self.device_id_str}")
        try:
            self.camera = QCamera(self.camera_device)
            self.capture_session = QMediaCaptureSession()

            supported_formats = self.camera_device.videoFormats()
            target_format = None
            desired_size = QSize(PHOTO_WIDTH, PHOTO_HEIGHT)
            for fmt in supported_formats:
                if fmt.resolution() == desired_size:
                    target_format = fmt
                    break 
            if target_format:
                self.camera.setCameraFormat(target_format)
            else:
                print(f"⚠️ 警告: 摄像头 {self.app_camera_index}: 未找到 {PHOTO_WIDTH}x{PHOTO_HEIGHT} 格式。")
            

            # 从容器中获取真正的QVideoWidget实例
            self.viewfinder = self.video_container.video_widget()

            self.image_capture = QImageCapture()
            
            self.capture_session.setCamera(self.camera)
            self.capture_session.setVideoOutput(self.viewfinder)
            self.capture_session.setImageCapture(self.image_capture)

            self.camera.errorOccurred.connect(self.camera_error)
            self.camera.activeChanged.connect(self.camera_active_changed)

            self.image_capture.setResolution(desired_size)
            self.image_capture.imageCaptured.connect(self.image_captured_and_save)
            self.image_capture.errorOccurred.connect(self.image_capture_error)
            
            self.camera.start()
            self.status_label.setText(f"摄像头 {self.app_camera_index} - 正在启动...")
        except Exception as e:
            error_msg = f"摄像头 {self.app_camera_index} 在初始化期间发生异常: {e}"
            print(f"❌ {error_msg}")
            self.activation_failed.emit(error_msg)


    def camera_active_changed(self, active: bool):
        if active:
            final_format = self.camera.cameraFormat()
            print(f"✅ 摄像头 {self.app_camera_index} 已激活！实际格式: {final_format.resolution().width()}x{final_format.resolution().height()}")
            self.status_label.setText(f"摄像头 {self.app_camera_index} ({self.camera_description})")
            self.activated.emit()
        else:
            if self.camera and not self.camera.isActive():
                 self.status_label.setText(f"摄像头 {self.app_camera_index} - 已停止")

    def camera_error(self, error: QCamera.Error, error_string: str):
        error_msg = f"致命错误 - 摄像头 {self.app_camera_index}: {error_string} (代码: {error})"
        print(f"❌ {error_msg}")
        self.status_label.setText(f"摄像头 {self.app_camera_index}\n错误: {error_string.split(':')[-1].strip()}")
        self.stop_camera()
        self.activation_failed.emit(error_msg)

    def take_photo(self, timestamp):
        if self.camera and self.camera.isActive() and self.image_capture.isAvailable():
            if not self._is_capturing_photo:
                self._is_capturing_photo = True
                self.last_capture_timestamp = timestamp
                self.image_capture.capture()
            else:
                print(f"  - 摄像头 {self.app_camera_index}: 正在等待上一次捕获完成。")
        else:
            active_str = "未知" if not self.camera else f"活动:{self.camera.isActive()}"
            ready_str = "未就绪" if not self.image_capture else f"可用:{self.image_capture.isAvailable()}"
            print(f"  - 摄像头 {self.app_camera_index}: 未准备好捕获照片。 ({active_str}, {ready_str})")

    def image_captured_and_save(self, id: int, preview_image: QImage):
        self._is_capturing_photo = False
        print(f"✅ 成功: 摄像头 {self.app_camera_index} 图像已捕获 (尺寸: {preview_image.width()}x{preview_image.height()})。")
        try:
            base_filename = f"cam_{self.app_camera_index}_{self.last_capture_timestamp}.jpg"
            filename = os.path.join(SAVE_IMAGE_DIR, base_filename)
            if preview_image.save(filename, "JPG", 95):
                print(f"  💾 文件已保存到: {os.path.abspath(filename)}")
            else:
                print(f"  ❌ 错误: 摄像头 {self.app_camera_index} 保存文件失败！")
        except Exception as e:
            print(f"  ❌ 严重错误: 保存图像时发生异常: {e}")

    def image_capture_error(self, id: int, error: QImageCapture.Error, error_string: str):
        print(f"❌ 错误: 摄像头 {self.app_camera_index} 捕获失败: {id}, {error}: {error_string}")
        self._is_capturing_photo = False

    def stop_camera(self):
        if self.camera and self.camera.isActive():
            self.camera.stop()
        print(f"摄像头 {self.app_camera_index} 已停止并释放。")
        self.status_label.setText(f"摄像头 {self.app_camera_index} - 已停止")

# --- 主窗口代码 ---
class MultiCameraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 多摄像头 (响应式布局版)")
        self.setGeometry(50, 50, 1280, 720) # 设置一个合理的初始窗口大小

        self.camera_widgets = []
        self.cameras_to_init = deque()
        
        os.makedirs(SAVE_IMAGE_DIR, exist_ok=True)
        print(f"图片将保存到目录: {os.path.abspath(SAVE_IMAGE_DIR)}")

        self.init_ui()
        self.start_camera_initialization()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.camera_grid_layout = QGridLayout()
        self.camera_grid_layout.setSpacing(10) 
        self.main_layout.addLayout(self.camera_grid_layout)
        
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(10, 10, 10, 10)
        self.take_photo_button = QPushButton("拍照 (C)")
        self.take_photo_button.setFixedSize(120, 40)
        self.take_photo_button.clicked.connect(self.capture_all_photos)
        button_layout.addWidget(self.take_photo_button)
        button_layout.addStretch()
        self.quit_button = QPushButton("退出 (Q)")
        self.quit_button.setFixedSize(120, 40)
        self.quit_button.clicked.connect(self.close)
        button_layout.addWidget(self.quit_button)
        self.main_layout.addLayout(button_layout)

    def start_camera_initialization(self):
        print(f"正在检测可用摄像头...")
        available_cameras = QMediaDevices.videoInputs()

        if not available_cameras:
            QMessageBox.warning(self, "无摄像头", "系统中没有检测到任何可用摄像头。")
            return

        for i, device in enumerate(available_cameras):
            if START_CAMERA_INDEX <= i < END_CAMERA_INDEX:
                self.cameras_to_init.append((device, i))
                print(f" - 发现摄像头 {i} (设备名: {device.description()})")
        
        if not self.cameras_to_init:
            QMessageBox.warning(self, "无摄像头", f"在指定范围 [{START_CAMERA_INDEX}, {END_CAMERA_INDEX-1}] 内没有检测到摄像头。")
            return
            
        print(f"\n准备串行初始化 {len(self.cameras_to_init)} 个摄像头...")
        self.init_next_camera()

    def init_next_camera(self):
        if self.cameras_to_init:
            cam_device, original_app_index = self.cameras_to_init.popleft()
            
            camera_widget = CameraWidget(cam_device, original_app_index)
            self.camera_widgets.append(camera_widget)
            
            # 动态计算网格布局
            num_cameras = len(self.camera_widgets)
            n_cols = max(1, int(math.ceil(math.sqrt(num_cameras))))
            
            # 清空并重新布局所有控件，确保网格始终最优
            # (这是一个简单粗暴但有效的方法)
            while self.camera_grid_layout.count():
                child = self.camera_grid_layout.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)

            for idx, widget in enumerate(self.camera_widgets):
                row = idx // n_cols
                col = idx % n_cols
                self.camera_grid_layout.addWidget(widget, row, col)

            camera_widget.activated.connect(self.init_next_camera)
            camera_widget.activation_failed.connect(self.on_camera_failed)
            
            camera_widget.start_it_up()
        else:
            print("\n🎉 所有摄像头初始化流程完成！")

    def on_camera_failed(self, error_message):
        print(f"摄像头启动失败: {error_message}. 继续初始化下一个...")
        # 即使失败，也继续初始化，失败的窗口会显示错误信息
        self.init_next_camera()
        
    def capture_all_photos(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"\n[拍照] 时间戳: {timestamp}")
        active_cams = [w for w in self.camera_widgets if w.camera and w.camera.isActive()]
        print(f"找到 {len(active_cams)} 个活动摄像头进行拍照。")
        for widget in active_cams:
            widget.take_photo(timestamp)
        print("所有拍照请求已发送。")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Q: self.close()
        elif event.key() == Qt.Key.Key_C: self.capture_all_photos()
        super().keyPressEvent(event)
    
    def cleanup_on_quit(self):
        print("\n正在释放所有摄像头资源...")
        for widget in self.camera_widgets:
            widget.stop_camera()
        print("所有资源已释放。程序退出。")

    def closeEvent(self, event):
        self.cleanup_on_quit()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MultiCameraApp()
    window.show() # 使用show()而不是showMaximized()，让窗口以默认大小启动
    sys.exit(app.exec())

