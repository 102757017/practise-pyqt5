from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QCoreApplication
import traceback
from threading import Lock #在设置参数和读取帧时，使用线程锁确保同一时间只有一个线程访问摄像头
import sys
import cv2
import time
from pathlib import Path


def excepthook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.exit(1)

sys.excepthook = excepthook  # 重写异常钩子


class CameraThread(QThread):
    change_pixmap = pyqtSignal(QImage)  # 自定义信号，用于传递图像
    cap_initialized = pyqtSignal(int)  # 摄像头初始化信号
    recording=False  #录像状态
    img_save_path=str(Path(__file__).parent/"snap")  #拍照保存路径
    video_save_path=str(Path(__file__).parent/"video")  #录像保存路径
    

    def __init__(self, cam_num):
        super().__init__()
        self.cam_num = cam_num
        self.running = False
        self.cap = None
        self.lock = Lock()  # 创建线程锁

    def run(self):
        self.cap = cv2.VideoCapture(self.cam_num)
        if self.cap.isOpened():
            self.cap_initialized.emit(self.cam_num)  # 摄像头初始化成功后发送信号
        else:
            print("无法打开摄像头")
            return
        self.running = True
        while self.running:
            with self.lock:  # 加锁
                ret, self.img = self.cap.read()
            if ret:
                rgb_image = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self.change_pixmap.emit(q_img)  # 发送图像信号
                if self.recording:
                    self.video.write(self.img)
        self.cap.release()

    def stop(self):
        self.running = False
        # 立即释放摄像头资源
        with self.lock:
            if self.cap and self.cap.isOpened():
                self.cap.release()

    def set_param(self, param_id, value):
        with self.lock:
            if self.cap and self.cap.isOpened():
                result=self.cap.set(param_id, value)
                return result
            else:
                print("相机未初始化完成，无法设置参数")
        return False

    def get_param(self, param_id):
        with self.lock:  # 加锁
            if self.cap and self.cap.isOpened():
                return self.cap.get(param_id)
            else:
                print("相机未初始化完成，无法获取参数")
    #拍照
    def capture(self, save_path=img_save_path):
        with self.lock:  # 加锁
            if self.cap and self.cap.isOpened():
                path=Path(save_path)/f"{int(time.time())}.jpeg"
                cv2.imwrite(str(path), self.img)
            else:
                print("拍照时摄像头未就绪")

    #roi区域截图
    def crop_rect(self, x, y, width, height,save=True,save_path=img_save_path):
        with self.lock:  # 加锁
            if self.cap and self.cap.isOpened():
                croped_img = self.img[y:y+height, x:x+width]
                if save==True:
                    path=Path(save_path)/f"{int(time.time())}.jpeg"
                    cv2.imwrite(str(path), croped_img)
            else:
                print("拍照时摄像头未就绪")

    #录像            
    def record_start(self,fps,save_path = video_save_path):
        if self.cap and self.cap.isOpened():
            cam_fps =self.get_param(cv2.CAP_PROP_FPS)
            print("相机帧率:",cam_fps)
            print("录像帧率:",fps)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            path=Path(save_path)/f"{int(time.time())}.mp4"
            self.video = cv2.VideoWriter(str(path), fourcc, float(fps), (width, height))
            self.recording=True
                

    def record_stop(self):
        if self.recording:
            self.recording=False
            if self.video:
                self.video.release()
                



if __name__ == "__main__":
    import sys

    # 创建 Qt 应用程序
    app = QCoreApplication(sys.argv)

    camera_thread = CameraThread(cam_num=0)
    camera_thread.start()


    #thread.start()是异步执行的，因此不能马上执行stop,要等摄像头初始化之后才能执行stop
    def on_cap_initialized(cam_num):
        #拍照
        camera_thread.capture()
        
        #录像，单位是毫秒
        camera_thread.record_start(fps=30)
        QTimer.singleShot(5000,lambda:camera_thread.record_stop())

        
        QTimer.singleShot(10000,lambda:camera_thread.stop())
        QTimer.singleShot(11000,lambda:QCoreApplication.quit()) # 退出事件循环
        

    # 连接信号和槽
    camera_thread.cap_initialized.connect(on_cap_initialized)

    # 启动事件循环
    sys.exit(app.exec_())
