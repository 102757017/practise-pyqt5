import pprint
from PyQt5.QtMultimedia import (
    QCamera, QCameraInfo,
    QCameraImageCapture,
    QCameraViewfinderSettings,
    QImageEncoderSettings
    )
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtMultimediaWidgets import QCameraViewfinder



all_camera_infos = QCameraInfo.availableCameras()
for i, info in enumerate(all_camera_infos):
    print(info.availableCameras())
    print(info.defaultCamera())
    print(info.deviceName())
    print(info.description())
    print(info.orientation())
    print(info.position())
    
    
cam=QCamera(info.defaultCamera())

'''
cam.error.connect(self.camera_error)
cam.statusChanged.connect(self.camera_status_changed)
cam.setCaptureMode(QCamera.CaptureStillImage)
'''
#cam.setViewfinder(self.viewfinder)#用于显示的控件

viewfinder_settings = QCameraViewfinderSettings()
viewfinder_settings.setResolution(800, 600)
cam.setViewfinderSettings(viewfinder_settings)


#设置拍照分辨率
image_capture = QCameraImageCapture(cam)
encoder_settings = QImageEncoderSettings()
encoder_settings.setCodec("image/jpeg")
encoder_settings.setResolution(QSize(800, 600))
image_capture.setEncodingSettings(encoder_settings)
image_capture.setCaptureDestination(QCameraImageCapture.CaptureToBuffer)
#image_capture.imageCaptured.connect(self.image_captured_and_save)
#image_capture.error.connect(self.image_capture_error)
pprint.pprint(dir(image_capture))


status=image_capture.capture()
print(status)

