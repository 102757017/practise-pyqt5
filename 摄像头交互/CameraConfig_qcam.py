from PyQt5 import QtWidgets, QtCore, QtMultimedia, QtMultimediaWidgets, QtGui
from PyQt5.uic import loadUi
import sys
import configparser
from types import MethodType

def excepthook(exc_type, exc_value, exc_tb):
    sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.exit(1)

sys.excepthook = excepthook

class CamSetting(QtWidgets.QMainWindow):
    params_mapping = {
        'BRIGHTNESS': 'brightness',
        'CONTRAST': 'contrast',
        'SATURATION': 'saturation',
        'HUE': 'hue',
        'GAIN': 'gain',
        'EXPOSURE': 'exposure',
        'AUTO_EXPOSURE': 'autoExposure',
        'AUTOFOCUS': 'autoFocus',
        'WB_TEMPERATURE': 'whiteBalance',
        'AUTO_WB': 'autoWhiteBalance',
        'SHARPNESS': 'sharpening',
        'GAMMA': 'gamma'
    }

    # 参数范围缩放映射
    param_scaling = {
        'brightness': lambda x: (x - 50) / 50.0,  # 0-100 → -1.0到1.0
        'contrast': lambda x: x / 100.0,           # 0-100 → 0.0到1.0
        'saturation': lambda x: x / 100.0,
        'hue': lambda x: (x - 50) / 50.0,
        'gain': lambda x: x / 100.0,
        'exposure': lambda x: x,                   # 保持原值，需根据实际调整
        'whiteBalance': lambda x: x,               # 可能为色温值，暂不缩放
        'sharpening': lambda x: x / 100.0,
        'gamma': lambda x: x / 100.0
    }

    def __init__(self, parent=None):
        super(CamSetting, self).__init__(parent)
        loadUi('CameraConfig.ui', self)
        
        self.camera = None
        self.camera_device = None
        self.image_processing = None
        self.current_cam = None
        
        self.init_ui()
        self.refresh_cam_list()
        
        self.saveButton.clicked.connect(self.save_setting)

    def init_ui(self):
        self.comboBox_camid.currentIndexChanged.connect(self.select_cam)
        
        for name in ['BRIGHTNESS', 'CONTRAST', 'SATURATION', 'HUE', 'GAIN', 
                    'EXPOSURE', 'WB_TEMPERATURE', 'SHARPNESS', 'GAMMA']:
            slider = self.findChild(QtWidgets.QSlider, f"horizontalSlider_{name}")
            slider.valueChanged.connect(self.create_param_setter(name.lower()))
            
        for name in ["FRAME_HEIGHT", "FPS"]:
            combo = self.findChild(QtWidgets.QComboBox, f"comboBox_{name}")
            combo.currentIndexChanged.connect(self.set_format)
            
        for name in ['AUTO_EXPOSURE', 'AUTOFOCUS', 'AUTO_WB']:
            checkbox = self.findChild(QtWidgets.QCheckBox, f"checkBox_{name}")
            checkbox.stateChanged.connect(self.create_auto_setter(name))

    def create_param_setter(self, param_name):
        def setter(value):
            if self.image_processing:
                method_name = f"set{param_name[0].upper()}{param_name[1:]}"
                if hasattr(self.image_processing, method_name):
                    try:
                        # 应用参数缩放
                        scaled_value = self.param_scaling.get(param_name, lambda x: x)(value)
                        method = getattr(self.image_processing, method_name)
                        method(scaled_value)
                        # 获取当前值验证
                        current = getattr(self.image_processing, param_name)()
                        print(f"[SUCCESS] {method_name}({scaled_value:.2f}), Current: {current:.2f}")
                    except Exception as e:
                        print(f"[ERROR] {method_name} failed: {str(e)}")
                else:
                    print(f"[ERROR] Method {method_name} not found")
        return setter



    def create_auto_setter(self, param_name):
        def setter(state):
            if self.image_processing:
                method_name = f"setAuto{param_name[4:]}"
                if hasattr(self.image_processing, method_name):
                    try:
                        method = getattr(self.image_processing, method_name)
                        is_checked = state == QtCore.Qt.Checked
                        method(is_checked)
                        print(f"[SUCCESS] {method_name}({is_checked})")
                    except Exception as e:
                        print(f"[ERROR] {method_name} failed: {str(e)}")
                else:
                    print(f"[ERROR] Method {method_name} not found")
        return setter

    def refresh_cam_list(self):
        self.comboBox_camid.clear()
        cameras = QtMultimedia.QCameraInfo.availableCameras()
        for cam in cameras:
            self.comboBox_camid.addItem(cam.description(), cam)

    def select_cam(self, index):
        if self.camera and self.camera.status() == QtMultimedia.QCamera.ActiveStatus:
            self.camera.stop()
            
        self.camera_device = self.comboBox_camid.itemData(index)
        self.current_cam = index
        
        self.camera = QtMultimedia.QCamera(self.camera_device)
        self.image_processing = self.camera.imageProcessing()
        
        viewfinder = QtMultimediaWidgets.QCameraViewfinder()
        self.label_17.setLayout(QtWidgets.QVBoxLayout())
        self.label_17.layout().addWidget(viewfinder)
        self.camera.setViewfinder(viewfinder)
        
        self.load_config()
        self.camera.start()

    def set_format(self):
        if not self.camera:
            return
            
        format_combo = self.sender()
        if format_combo.objectName() == "comboBox_FRAME_HEIGHT":
            height = int(format_combo.currentText())
            self.set_resolution(height)
        elif format_combo.objectName() == "comboBox_FPS":
            fps = int(format_combo.currentText())
            self.set_framerate(fps)

    def set_resolution(self, height):
        selected_format = None
        for fmt in self.camera_device.supportedViewfinderResolutions():
            if fmt.height() == height:
                selected_format = fmt
                break
        if selected_format:
            viewfinder_settings = self.camera.viewfinderSettings()
            viewfinder_settings.setResolution(selected_format)
            self.camera.setViewfinderSettings(viewfinder_settings)

    def set_framerate(self, fps):
        settings = self.camera.viewfinderSettings()
        min_rate, max_rate = 0, 0
        for rate_range in self.camera_device.supportedViewfinderFrameRateRanges(settings.resolution()):
            if rate_range.minimumFrameRate <= fps <= rate_range.maximumFrameRate:
                min_rate = rate_range.minimumFrameRate
                max_rate = rate_range.maximumFrameRate
                break
        if max_rate > 0:
            settings.setMinimumFrameRate(min_rate)
            settings.setMaximumFrameRate(max_rate)
            self.camera.setViewfinderSettings(settings)

    def load_config(self):
        config = configparser.ConfigParser()
        try:
            config.read("seting.ini", encoding="utf-8")
        except Exception as e:
            print(f"读取配置失败: {e}")
            return
            
        section = f"Camera{self.current_cam}"
        if not config.has_section(section):
            return
            
        for param in config.options(section):
            value = config.getfloat(section, param)
            param = param.upper()
            
            if param in self.params_mapping:
                qt_param = self.params_mapping[param]
                slider = self.findChild(QtWidgets.QSlider, f"horizontalSlider_{param}")
                if slider:
                    slider.setValue(int(value))
                
                checkbox = self.findChild(QtWidgets.QCheckBox, f"checkBox_{param}")
                if checkbox:
                    checkbox.setChecked(bool(value))

    def save_setting(self):
        config = configparser.ConfigParser()
        config.read('seting.ini')
        
        section = f"Camera{self.current_cam}"
        if not config.has_section(section):
            config.add_section(section)
            
        for param in self.params_mapping:
            slider = self.findChild(QtWidgets.QSlider, f"horizontalSlider_{param}")
            if slider:
                config.set(section, param, str(slider.value()))
                
            checkbox = self.findChild(QtWidgets.QCheckBox, f"checkBox_{param}")
            if checkbox:
                config.set(section, param, str(int(checkbox.isChecked())))
        
        with open('seting.ini', 'w') as f:
            config.write(f)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = CamSetting()
    mainWindow.show()
    sys.exit(app.exec_())
