import sys
import os
os.environ["QT_MEDIA_BACKEND"] = "windows" # 设置环境变量,否则可能导致摄像头列表为空
import math
from datetime import datetime
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QPushButton, QMessageBox
)
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from PyQt6.QtMultimedia import (
    QCamera, QCameraDevice, QMediaDevices,
    QImageCapture, QMediaCaptureSession, QCameraFormat
)
from PyQt6.QtMultimediaWidgets import QVideoWidget

# --- 配置参数 ---
PREVIEW_WINDOW_WIDTH = 640
PREVIEW_WINDOW_HEIGHT = 480
PHOTO_WIDTH = 320
PHOTO_HEIGHT = 240
START_CAMERA_INDEX = 0
END_CAMERA_INDEX = 5
SAVE_IMAGE_DIR = "captured_images_pyqt6"

# --- 单个摄像头界面和逻辑封装 ---
class CameraWidget(QWidget):
    activated = pyqtSignal()
    activation_failed = pyqtSignal(str)

    def __init__(self, camera_device: QCameraDevice, app_camera_index: int, parent=None):
        super().__init__(parent)
        self.camera_device = camera_device
        self.app_camera_index = app_camera_index
        self.camera_description = camera_device.description()
        
        self.camera = None
        self.image_capture = None
        self.capture_session = None
        self.viewfinder = None
        self._is_capturing_photo = False
        self.last_capture_timestamp = ""
        
        self.init_ui()
        
    def init_ui(self):
        self.layout = QVBoxLayout()
        self.viewfinder_container = QWidget()
        self.viewfinder_container.setFixedSize(PREVIEW_WINDOW_WIDTH, PREVIEW_WINDOW_HEIGHT)
        self.viewfinder_container.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.layout.addWidget(self.viewfinder_container)
        self.status_label = QLabel(f"摄像头 {self.app_camera_index} ({self.camera_description})")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)
        self.setLayout(self.layout)

    # =========================================================================
    # ====================   核心修改在此方法中   ==============================
    # =========================================================================
    def start_it_up(self):
        """【PyQt6 核心重构】使用新的多媒体框架启动摄像头"""
        try:
            self.camera = QCamera(self.camera_device)
            self.capture_session = QMediaCaptureSession()

            # --- 【问题修复】开始: 显式设置摄像头格式 ---
            # 1. 查询摄像头支持的所有视频格式
            supported_formats = self.camera_device.videoFormats()
            target_format = None
            
            desired_size = QSize(PHOTO_WIDTH, PHOTO_HEIGHT)

            print(f"--- 摄像头 {self.app_camera_index} 支持的格式 ---")
            for fmt in supported_formats:
                # 打印每个支持的格式，便于调试
                print(f"  - {fmt.resolution().width()}x{fmt.resolution().height()} @ {fmt.maxFrameRate():.2f}fps")
                if fmt.resolution() == desired_size:
                    target_format = fmt
                    # 可以在这里根据帧率等做更精细的选择，但通常匹配分辨率即可
                    break 

            # 2. 如果找到了匹配的格式，就应用它
            if target_format:
                print(f"✅ 摄像头 {self.app_camera_index}: 找到匹配的分辨率 {PHOTO_WIDTH}x{PHOTO_HEIGHT}，正在应用该格式...")
                self.camera.setCameraFormat(target_format)
            else:
                print(f"⚠️ 警告: 摄像头 {self.app_camera_index}: 未找到完全匹配 {PHOTO_WIDTH}x{PHOTO_HEIGHT} 的格式。将使用默认格式，照片可能被裁剪。")
            # --- 【问题修复】结束 ---

            self.viewfinder = QVideoWidget(self.viewfinder_container)
            viewfinder_layout = QVBoxLayout(self.viewfinder_container)
            viewfinder_layout.setContentsMargins(0, 0, 0, 0)
            viewfinder_layout.addWidget(self.viewfinder)

            self.image_capture = QImageCapture()
            
            self.capture_session.setCamera(self.camera)
            self.capture_session.setVideoOutput(self.viewfinder)
            self.capture_session.setImageCapture(self.image_capture)

            self.camera.errorOccurred.connect(self.camera_error)
            self.camera.activeChanged.connect(self.camera_active_changed)

            # 尽管我们设置了 cameraFormat，但再次设置 image_capture 的分辨率是个好习惯，确保意图明确
            print(f"摄像头 {self.app_camera_index}: 再次确认拍照分辨率为 {PHOTO_WIDTH}x{PHOTO_HEIGHT}")
            self.image_capture.setResolution(desired_size)

            self.image_capture.imageCaptured.connect(self.image_captured_and_save)
            self.image_capture.errorOccurred.connect(self.image_capture_error)
            
            self.camera.start()
            self.status_label.setText(f"摄像头 {self.app_camera_index} - 正在启动...")
            print(f"摄像头 {self.app_camera_index}: 启动命令已发送。")
        except Exception as e:
            error_msg = f"摄像头 {self.app_camera_index} 在初始化期间发生异常: {e}"
            print(f"❌ {error_msg}")
            self.activation_failed.emit(error_msg)

    def camera_active_changed(self, active: bool):
        if active:
            final_format = self.camera.cameraFormat()
            print(f"✅ 摄像头 {self.app_camera_index} 已激活！当前实际使用格式: {final_format.resolution().width()}x{final_format.resolution().height()}")
            self.status_label.setText(f"摄像头 {self.app_camera_index} ({self.camera_description})")
            self.activated.emit()
        else:
            if self.camera and not self.camera.isActive(): # 避免在停止过程中重复设置
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
                print(f"  - 摄像头 {self.app_camera_index}: 正在请求捕获图像...")
                self.image_capture.capture()
            else:
                print(f"  - 摄像头 {self.app_camera_index}: 正在等待上一次捕获完成。")
        else:
            active_str = "未知"
            if self.camera: active_str = f"是否活动: {self.camera.isActive()}"
            ready_str = "未就绪"
            if self.image_capture: ready_str = f"是否可用: {self.image_capture.isAvailable()}"
            print(f"  - 摄像头 {self.app_camera_index}: 未准备好捕获照片。 ({active_str}, {ready_str})")

    def image_captured_and_save(self, id: int, preview_image: QImage):
        print(f"✅ 成功: 摄像头 {self.app_camera_index} 图像已捕获 (实际尺寸: {preview_image.width()}x{preview_image.height()})。")
        try:
            base_filename = f"cam_{self.app_camera_index}_{self.last_capture_timestamp}.jpg"
            filename = os.path.join(SAVE_IMAGE_DIR, base_filename)
            success = preview_image.save(filename, "JPG", 95)
            if success:
                print(f"  💾 文件已保存到: {os.path.abspath(filename)}")
            else:
                print(f"  ❌ 错误: 摄像头 {self.app_camera_index} 使用 QImage.save() 保存文件失败！")
        except Exception as e:
            print(f"  ❌ 严重错误: 在保存图像时发生异常: {e}")
        finally:
            self._is_capturing_photo = False

    def image_capture_error(self, id: int, error: QImageCapture.Error, error_string: str):
        print(f"❌ 错误: 摄像头 {self.app_camera_index} 捕获失败: {id}, {error}: {error_string}")
        self._is_capturing_photo = False

    def stop_camera(self):
        if self.camera:
            if self.camera.isActive():
                self.camera.stop()
            self.camera.deleteLater()
            self.camera = None
        if self.image_capture:
            self.image_capture.deleteLater()
            self.image_capture = None
        if self.capture_session:
            self.capture_session.deleteLater()
            self.capture_session = None
        if self.viewfinder:
            self.viewfinder.deleteLater()
            self.viewfinder = None
        print(f"摄像头 {self.app_camera_index} 已停止并释放。")
        self.status_label.setText(f"摄像头 {self.app_camera_index} - 已停止")

# 以下主窗口代码无需修改
class MultiCameraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 多摄像头 (串行加载版 - 已修复)")
        self.setGeometry(100, 100, 1300, 800)

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
        self.main_layout.addLayout(self.camera_grid_layout)
        button_layout = QHBoxLayout()
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
        print(f"正在检测可用摄像头 (逻辑索引从 {START_CAMERA_INDEX} 到 {END_CAMERA_INDEX})...")
        available_cameras = QMediaDevices.videoInputs()

        if not available_cameras:
            QMessageBox.warning(self, "无摄像头", "系统中没有检测到任何可用摄像头。")
            return

        for i, device in enumerate(available_cameras):
            if START_CAMERA_INDEX <= i <= END_CAMERA_INDEX:
                self.cameras_to_init.append((device, i))
                print(f" - 发现摄像头 {i} (设备名: {device.description()})")
        
        if not self.cameras_to_init:
            QMessageBox.warning(self, "无摄像头", f"在指定范围 [{START_CAMERA_INDEX}, {END_CAMERA_INDEX}] 内没有检测到摄像头。")
            return
            
        print(f"\n准备串行初始化 {len(self.cameras_to_init)} 个摄像头...")
        self.init_next_camera()

    def init_next_camera(self):
        if self.cameras_to_init:
            cam_device, original_app_index = self.cameras_to_init.popleft()
            
            print(f"\n---> 正在初始化摄像头 {original_app_index}...")
            
            camera_widget = CameraWidget(cam_device, original_app_index)
            self.camera_widgets.append(camera_widget)
            
            num_widgets_with_this = len(self.camera_widgets)
            n_cols = max(1, int(math.ceil(math.sqrt(END_CAMERA_INDEX - START_CAMERA_INDEX + 1))))
            if PREVIEW_WINDOW_WIDTH > 400: # 如果预览窗口较大，减少列数
                n_cols = max(1, self.width() // (PREVIEW_WINDOW_WIDTH + 20))
            
            row = (num_widgets_with_this - 1) // n_cols
            col = (num_widgets_with_this - 1) % n_cols
            self.camera_grid_layout.addWidget(camera_widget, row, col)

            camera_widget.activated.connect(self.init_next_camera)
            camera_widget.activation_failed.connect(self.on_camera_failed)
            
            camera_widget.start_it_up()
        else:
            print("\n🎉 所有摄像头初始化流程完成！")

    def on_camera_failed(self, error_message):
        print(f"摄像头启动失败: {error_message}. 继续初始化下一个...")
        self.init_next_camera()
        
    def capture_all_photos(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"\n准备为 {len(self.camera_widgets)} 个摄像头拍照...")
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
    window.showMaximized()
    sys.exit(app.exec())
