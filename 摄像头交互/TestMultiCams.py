import sys
import os
import math
from datetime import datetime
from collections import deque

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QPushButton, QMessageBox
)
from PyQt5.QtGui import QImage
from PyQt5.QtCore import Qt, QSize, pyqtSignal

from PyQt5.QtMultimedia import (
    QCamera, QCameraInfo,
    QCameraImageCapture,
    QCameraViewfinderSettings,
    QImageEncoderSettings
)
from PyQt5.QtMultimediaWidgets import QCameraViewfinder

# --- 配置参数 ---
PREVIEW_WINDOW_WIDTH = 320
PREVIEW_WINDOW_HEIGHT = 240
PHOTO_WIDTH = 640
PHOTO_HEIGHT = 480
START_CAMERA_INDEX = 0
END_CAMERA_INDEX = 5
SAVE_IMAGE_DIR = "captured_images_pyqt"

# --- 单个摄像头界面和逻辑封装 ---
class CameraWidget(QWidget):
    # 【新】自定义信号，当摄像头成功激活时发出
    activated = pyqtSignal()
    # 【新】自定义信号，当摄像头启动失败时发出
    activation_failed = pyqtSignal(str)

    def __init__(self, camera_info: QCameraInfo, app_camera_index: int, parent=None):
        super().__init__(parent)
        self.camera_info = camera_info
        self.app_camera_index = app_camera_index
        self.original_camera_id = camera_info.deviceName()
        self.camera = None
        self.image_capture = None
        self.viewfinder = None
        self._is_capturing_photo = False
        self.last_capture_timestamp = ""
        
        self.init_ui()
        # 将 init_camera 改为可被外部调用的 start_it_up 方法
        # self.init_camera() 

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.viewfinder_container = QWidget()
        self.viewfinder_container.setFixedSize(PREVIEW_WINDOW_WIDTH, PREVIEW_WINDOW_HEIGHT)
        self.viewfinder_container.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.layout.addWidget(self.viewfinder_container)
        self.status_label = QLabel(f"摄像头 {self.app_camera_index} ({self.original_camera_id})")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.status_label)
        self.setLayout(self.layout)

    def start_it_up(self):
        """外部调用的启动方法"""
        try:
            self.camera = QCamera(self.camera_info)
            # 【重要】在这里连接错误信号
            self.camera.error.connect(self.camera_error)
            self.camera.statusChanged.connect(self.camera_status_changed)
            self.camera.setCaptureMode(QCamera.CaptureStillImage)

            self.viewfinder = QCameraViewfinder(self.viewfinder_container)
            viewfinder_layout = QVBoxLayout(self.viewfinder_container)
            viewfinder_layout.setContentsMargins(0, 0, 0, 0)
            viewfinder_layout.addWidget(self.viewfinder)
            self.camera.setViewfinder(self.viewfinder)

            viewfinder_settings = QCameraViewfinderSettings()
            viewfinder_settings.setResolution(PREVIEW_WINDOW_WIDTH, PREVIEW_WINDOW_HEIGHT)
            self.camera.setViewfinderSettings(viewfinder_settings)
            print(f"摄像头 {self.app_camera_index}: 预览分辨率设置为 {PREVIEW_WINDOW_WIDTH}x{PREVIEW_WINDOW_HEIGHT}")

            self.image_capture = QCameraImageCapture(self.camera)
            
            encoder_settings = QImageEncoderSettings()
            encoder_settings.setCodec("image/jpeg")
            desired_resolution = QSize(PHOTO_WIDTH, PHOTO_HEIGHT)
            
            print(f"摄像头 {self.app_camera_index}: 尝试强制设置拍照分辨率为 {PHOTO_WIDTH}x{PHOTO_HEIGHT}")
            encoder_settings.setResolution(desired_resolution)
            self.image_capture.setEncodingSettings(encoder_settings)
            
            self.image_capture.setCaptureDestination(QCameraImageCapture.CaptureToBuffer)
            self.image_capture.imageCaptured.connect(self.image_captured_and_save)
            self.image_capture.error.connect(self.image_capture_error)
            
            self.camera.start()
            self.status_label.setText(f"摄像头 {self.app_camera_index} - 正在启动...")
            print(f"摄像头 {self.app_camera_index}: 启动命令已发送。")
        except Exception as e:
            error_msg = f"摄像头 {self.app_camera_index} 在初始化期间发生异常: {e}"
            print(f"❌ {error_msg}")
            self.activation_failed.emit(error_msg)

    def camera_status_changed(self, status: QCamera.Status):
        status_text = {
            QCamera.UnloadedStatus: "未加载", QCamera.LoadedStatus: "已加载",
            QCamera.ActiveStatus: "活动中", QCamera.StartingStatus: "正在启动",
            QCamera.StoppingStatus: "正在停止"
        }.get(status, f"未知状态 ({status})")
        
        if status == QCamera.ActiveStatus:
            self.status_label.setText(f"摄像头 {self.app_camera_index} ({self.original_camera_id})")
            print(f"✅ 摄像头 {self.app_camera_index} 已激活！")
            # 【新】成功激活，发射信号通知主窗口
            self.activated.emit()
        else:
            self.status_label.setText(f"摄像头 {self.app_camera_index} - {status_text}")

    def camera_error(self, error):
        # 【修正】使用正确的 PyQt5 QCamera.Error 枚举
        error_map = {
            QCamera.NoError: "NoError",
            QCamera.CameraError: "通用摄像头错误",
            QCamera.InvalidRequestError: "无效请求错误",
            QCamera.ServiceMissingError: "多媒体服务缺失",
            QCamera.NotSupportedFeatureError: "当前状态下不支持该操作"
        }
        friendly_error_str = error_map.get(error, f"未知错误代码 ({error})")
        error_msg = f"致命错误 - 摄像头 {self.app_camera_index}: {friendly_error_str}"
        print(f"❌ {error_msg}")
        self.status_label.setText(f"摄像头 {self.app_camera_index}\n错误: {friendly_error_str}")
        self.stop_camera()
        # 【新】启动失败，发射信号通知主窗口
        self.activation_failed.emit(error_msg)

    # ... 其他方法 (take_photo, image_captured_and_save 等) 无需大改 ...
    def take_photo(self, timestamp):
        if self.camera and self.camera.status() == QCamera.ActiveStatus and self.image_capture.isReadyForCapture():
            if not self._is_capturing_photo:
                self._is_capturing_photo = True
                self.last_capture_timestamp = timestamp
                print(f"  - 摄像头 {self.app_camera_index}: 正在请求捕获图像到内存...")
                self.image_capture.capture()
            else:
                print(f"  - 摄像头 {self.app_camera_index}: 正在等待上一次捕获完成。")
        else:
            status_str = "未知"
            if self.camera: status_str = f"状态: {self.camera.status()}"
            ready_str = "未就绪"
            if self.image_capture: ready_str = f"是否就绪: {self.image_capture.isReadyForCapture()}"
            print(f"  - 摄像头 {self.app_camera_index}: 未准备好捕获照片。 ({status_str}, {ready_str})")

    def image_captured_and_save(self, id: int, preview_image: QImage):
        print(f"✅ 成功: 摄像头 {self.app_camera_index} 图像已捕获到内存 (尺寸: {preview_image.width()}x{preview_image.height()})。")
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

    def image_capture_error(self, id: int, error, error_string: str):
        print(f"❌ 错误: 摄像头 {self.app_camera_index} 捕获失败: {id}, {error}: {error_string}")
        self._is_capturing_photo = False

    def stop_camera(self):
        if self.camera:
            if self.camera.status() in [QCamera.ActiveStatus, QCamera.StartingStatus]:
                self.camera.stop()
                self.camera.unload()
            self.camera.deleteLater()
            self.camera = None
            if self.image_capture: self.image_capture.deleteLater()
            self.image_capture = None
            if self.viewfinder: self.viewfinder.deleteLater()
            self.viewfinder = None
            print(f"摄像头 {self.app_camera_index} 已停止并释放。")
        self.status_label.setText(f"摄像头 {self.app_camera_index} - 已停止")

# --- 主窗口类 (重构以支持串行加载) ---
class MultiCameraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 多摄像头 (串行加载版)")
        self.setGeometry(100, 100, 1000, 800)

        self.camera_widgets = []
        # 【新】使用双端队列存储待初始化的摄像头信息
        self.cameras_to_init = deque()
        
        os.makedirs(SAVE_IMAGE_DIR, exist_ok=True)
        print(f"图片将保存到目录: {os.path.abspath(SAVE_IMAGE_DIR)}")

        self.init_ui()
        self.start_camera_initialization()

        app.aboutToQuit.connect(self.cleanup_on_quit)

    def init_ui(self):
        # ... UI 部分无变化 ...
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
        """【重构】第一步: 检测摄像头并填充队列，然后启动第一个"""
        print(f"正在检测可用摄像头 (逻辑索引从 {START_CAMERA_INDEX} 到 {END_CAMERA_INDEX})...")
        all_camera_infos = QCameraInfo.availableCameras()

        if not all_camera_infos:
            QMessageBox.warning(self, "无摄像头", "系统中没有检测到任何可用摄像头。")
            return

        for i, info in enumerate(all_camera_infos):
            if START_CAMERA_INDEX <= i <= END_CAMERA_INDEX:
                self.cameras_to_init.append((info, i))
                print(f" - 发现摄像头 {i} (设备名: {info.deviceName()})")
        
        if not self.cameras_to_init:
            QMessageBox.warning(self, "无摄像头", f"在指定范围 [{START_CAMERA_INDEX}, {END_CAMERA_INDEX}] 内没有检测到摄像头。")
            return
            
        print(f"\n准备串行初始化 {len(self.cameras_to_init)} 个摄像头...")
        self.init_next_camera()

    def init_next_camera(self):
        """【新】核心逻辑: 从队列中取出一个摄像头并初始化"""
        if self.cameras_to_init:
            cam_info, original_app_index = self.cameras_to_init.popleft()
            
            print(f"\n---> 正在初始化摄像头 {original_app_index}...")
            
            camera_widget = CameraWidget(cam_info, original_app_index)
            self.camera_widgets.append(camera_widget)
            
            # 计算布局位置
            num_started = len(self.camera_widgets)
            n_cols = max(1, int(math.ceil(math.sqrt(END_CAMERA_INDEX - START_CAMERA_INDEX + 1))))
            row = (num_started - 1) // n_cols
            col = (num_started - 1) % n_cols
            self.camera_grid_layout.addWidget(camera_widget, row, col)

            # 连接信号，以便在一个成功/失败后启动下一个
            camera_widget.activated.connect(self.init_next_camera)
            camera_widget.activation_failed.connect(self.on_camera_failed)
            
            # 真正启动摄像头
            camera_widget.start_it_up()
        else:
            print("\n🎉 所有摄像头初始化流程完成！")

    def on_camera_failed(self, error_message):
        """【新】处理单个摄像头启动失败的情况，并继续尝试下一个"""
        print(f"摄像头启动失败: {error_message}. 继续初始化下一个...")
        # 即使失败了，也要继续尝试初始化队列中的下一个摄像头
        self.init_next_camera()

    # ... 其他主窗口方法无变化 ...
    def capture_all_photos(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"\n准备为 {len(self.camera_widgets)} 个摄像头拍照...")
        for widget in self.camera_widgets:
            widget.take_photo(timestamp)
        print("所有拍照请求已发送。")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q: self.close()
        elif event.key() == Qt.Key_C: self.capture_all_photos()
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
    sys.exit(app.exec_())
