from PyQt5.uic import loadUi
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QSlider,QComboBox,QCheckBox
from CvCamThread import CameraThread
import configparser
import cv2
import sys
import traceback

def excepthook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.exit(1)

sys.excepthook = excepthook  # 重写异常钩子


class CamSetting(QtWidgets.QMainWindow):
    # 全大写键名直接映射到 OpenCV 常量
    params = {
        "FRAME_HEIGHT": cv2.CAP_PROP_FRAME_HEIGHT,
        "FPS": cv2.CAP_PROP_FPS,
        "BRIGHTNESS": cv2.CAP_PROP_BRIGHTNESS,
        "CONTRAST": cv2.CAP_PROP_CONTRAST,
        "SATURATION": cv2.CAP_PROP_SATURATION,
        "HUE": cv2.CAP_PROP_HUE,
        "GAIN": cv2.CAP_PROP_GAIN,
        "EXPOSURE": cv2.CAP_PROP_EXPOSURE,
        "AUTO_EXPOSURE": cv2.CAP_PROP_AUTO_EXPOSURE,
        "AUTOFOCUS": cv2.CAP_PROP_AUTOFOCUS,
        "WB_TEMPERATURE": cv2.CAP_PROP_WB_TEMPERATURE,
        "AUTO_WB": cv2.CAP_PROP_AUTO_WB,
        "BACKLIGHT": cv2.CAP_PROP_BACKLIGHT,
        "SHARPNESS": cv2.CAP_PROP_SHARPNESS,
        "GAMMA": cv2.CAP_PROP_GAMMA,
        }
    
    def __init__(self, parent=None):
        super(CamSetting, self).__init__(parent)
        loadUi('CameraConfig.ui', self)

        self.camera_thread = None  # 初始化摄像头线程
        available_cameras = self.list_all_cameras()
        self.comboBox_camid.addItems(list(map(str, available_cameras))) #int要转换为string
       
        items_list = ["240", "480", "720", "1080"]
        self.comboBox_FRAME_HEIGHT.addItems(items_list)

        resolution = ["30", "60"]
        self.comboBox_FPS.addItems(resolution)
        
        #定义槽函数
        self.comboBox_camid.textActivated.connect(self.select_cam)
        for name in ['BRIGHTNESS', 'CONTRAST', 'SATURATION', 'HUE', 'GAIN', 'EXPOSURE', 'WB_TEMPERATURE','BACKLIGHT', 'SHARPNESS', 'GAMMA']:
            Widget=self.findChild(QSlider,f"horizontalSlider_{name.upper()}")
            Widget.valueChanged.connect(self.setcam)
        for name in ["FRAME_HEIGHT","FPS"]:
            Widget=self.findChild(QComboBox,f"comboBox_{name.upper()}")
            Widget.textActivated.connect(self.setcam)
        for name in ['AUTO_EXPOSURE', 'AUTOFOCUS','AUTO_WB']:
            Widget=self.findChild(QCheckBox,f"checkBox_{name.upper()}")
            Widget.stateChanged.connect(self.setcam)

        self.saveButton.clicked.connect(self.save_setting)
            


    def select_cam(self):
        # 停止之前的摄像头线程
        if self.camera_thread and self.camera_thread.isRunning():
            #thread.stop是异步执行的，不会马上停止，在创建新线程前，需要断开旧线程的所有信号连接，防止旧信号干扰。此外若不断开，在重新执行时会重复创建连接，导致重复执行
            self.camera_thread.change_pixmap.disconnect()
            self.camera_thread.cap_initialized.disconnect()
            self.camera_thread.stop()
            self.camera_thread.wait()

        try:
            cam_id = int(self.comboBox_camid.currentText())
        except ValueError:
            print("摄像头索引无效！")
            return

        self.camera_thread = CameraThread(cam_id)
        self.camera_thread.change_pixmap.connect(self.update_image)
        #摄像头初始化完成后再载入设置
        self.camera_thread.cap_initialized.connect(self.load_config)
        self.camera_thread.start()
        
 

    #枚举摄像头
    def load_config(self, cam_id):
        config = configparser.ConfigParser()
        try:
            config.read("seting.ini", encoding="utf-8")
            print(f"读取配置文件成功")
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            return

        # 动态匹配摄像头配置（例如 Camera1）
        section_name = f"Camera{cam_id}"
        if not config.has_section(section_name):
            print(f"配置文件中缺少 {section_name} 段落！")
            return

        # 初始化摄像头
        #self.cap = self.camera_thread.cap
        if not self.camera_thread.cap.isOpened():
            print(f"摄像头 {cam_id} 无法打开！")
            return

        # 遍历配置项并设置参数
        for param_name in config[section_name]:
            #configparser 默认会将键名转为小写
            if param_name.upper() in self.params:
                param_id = self.params[param_name.upper()]
                value = config[section_name].getint(param_name)
                success = self.camera_thread.set_param(param_id, value)
                if success:
                    print(f"{param_name} = {value}（成功）")
                    if param_name.upper() in ['BRIGHTNESS', 'CONTRAST', 'SATURATION', 'HUE', 'GAIN', 'EXPOSURE',
                                              'WB_TEMPERATURE', 'BACKLIGHT', 'SHARPNESS', 'GAMMA']:
                        slider=self.findChild(QSlider,f"horizontalSlider_{param_name.upper()}")
                        slider.setValue(value)
                        
                    if param_name.upper() in ["FRAME_HEIGHT","FPS"]:
                        print(f"comboBox_{param_name.upper()}")
                        combo=self.findChild(QComboBox,f"comboBox_{param_name.upper()}")
                        combo.setCurrentText(str(value))
                        
                    if param_name.upper() in ['AUTO_EXPOSURE', 'AUTOFOCUS','AUTO_WB']:
                        checkbox=self.findChild(QCheckBox,f"checkBox_{param_name.upper()}")
                        checkbox.setChecked(bool(value))
                    
                else:
                    print(f"警告：{param_name} 不支持当前摄像头")


        

    def update_image(self, q_img):
        pixmap = QPixmap.fromImage(q_img)
        ratio = max(q_img.width() / self.label.width(), q_img.height() / self.label.height())
        #pixmap.setDevicePixelRatio(ratio)
        self.label_17.setAlignment(Qt.AlignCenter)
        self.label_17.setPixmap(pixmap)



    #枚举摄像头
    def list_all_cameras(self,max_tries=10):
        """
        枚举所有可用的摄像头并返回可用摄像头的索引列表。
        :param max_tries: 最大尝试索引数（默认10）
        :return: 可用摄像头的索引列表
        """
        available_cameras = []
        for i in range(max_tries):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        return available_cameras

    # 定义槽函数
    def setcam(self):
        if not self.camera_thread or not self.camera_thread.cap.isOpened():
            return

        widget = self.sender()
        widget_name = widget.objectName()
        param_name = widget_name.split("_", 1)[1]
        param_id = self.params[param_name]
        
        if isinstance(widget, QSlider):
            value = widget.value()
        elif isinstance(widget, QComboBox):
            value = int(widget.currentText())
        elif isinstance(widget, QCheckBox):
            value = 1 if widget.isChecked() else 0
        else:
            return

        success =self.camera_thread.set_param(param_id, value)
        print(f"Set {param_name}  {success}")

    def save_setting(self):
        config = configparser.ConfigParser()
        config.read('seting.ini', encoding='utf-8')
        cam_num=self.camera_thread.cam_num
        for name in ['BRIGHTNESS', 'CONTRAST', 'SATURATION', 'HUE', 'GAIN', 'EXPOSURE', 'WB_TEMPERATURE','BACKLIGHT', 'SHARPNESS', 'GAMMA']:
            slider=self.findChild(QSlider,f"horizontalSlider_{name.upper()}")
            config.set(f'Camera{cam_num}', name, str(slider.value()))
            
        for name in ["FRAME_HEIGHT","FPS"]:
            combo=self.findChild(QComboBox,f"comboBox_{name.upper()}")
            config.set(f'Camera{cam_num}', name, combo.currentText())
            
        for name in ['AUTO_EXPOSURE', 'AUTOFOCUS','AUTO_WB']:
            checkbox=self.findChild(QCheckBox,f"checkBox_{name.upper()}")
            config.set(f'Camera{cam_num}', name, str(int(checkbox.isChecked())))

        config.write(open('seting.ini', 'w'))
        
        


if __name__ == "__main__":
    # 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
    app = QtWidgets.QApplication(sys.argv)
    # #创建一个我们生成的那个窗口，注意把类名修改为MainWindow
    mainWindow = CamSetting()
    mainWindow.show()
    sys.exit(app.exec_())
