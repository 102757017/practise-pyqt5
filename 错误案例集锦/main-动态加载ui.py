from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import  QtWidgets
from PyQt5.uic import loadUi
import sys
import os
import time
from PyQt5.QtCore import QTimer
import traceback

def excepthook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.exit(1)

sys.excepthook = excepthook  # 重写异常钩子

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        loadUi('form1.ui', self)

        #连接子进程内的信号与槽函数
        self.pushButton.clicked.connect(self.delay1)
        self.pushButton_2.clicked.connect(self.delay2)
        self.pushButton_3.clicked.connect(self.loop1)
        self.pushButton_4.clicked.connect(self.loop2)
        


    # 定义槽函数
    def delay1(self):
        #槽函数内使用sleep会阻塞主线程
        time.sleep(5)
        QtWidgets.QMessageBox.information(self, "标题", "槽函数内使用sleep会阻塞主线程")
        
    def delay2(self):
        #QTimer本质上就是一个信号连接到了槽函数，其单位是毫秒
        QTimer.singleShot(3000,
                          lambda: QtWidgets.QMessageBox.information(self, "标题","槽函数内使用QTimer不会阻塞主线程")
                          )
    def loop1(self):
        #槽函数内使用循环会阻塞主线程,UI会卡住
        while True:
            print("循环正在执行")
        
    def loop2(self):
        #将耗时的作业放在子进程的run方法内操作
        self.thread=MyThread()
        self.thread.start()
        QTimer.singleShot(3000,
                          lambda:self.thread.set_flag_false()
                          )
        
        

class MyThread(QThread):
    #创建一个信号，该信号会传递一个str类型的参数给槽函数
    sinOut = pyqtSignal(str)
    def __init__(self,parent=None):
        # super主要来调用父类方法来显示调用父类,要将子类Child和self传递进去
        #首先找到MyThread的父类（QThread），然后把类MyThread的对象self转换为类QThread的对象，然后“被转换”的QThread对象调用自己的__init__函数
        super(MyThread, self).__init__(parent)

        #设置标志位，用来中断子进程内的循环语句
        self.flag = True

    def set_flag_true(self):
        self.flag = True
        
    def set_flag_false(self):
        self.flag = False

    #重写QThread的run函数，将子进程要执行的操作放在此函数内，线程的start方法会执行run函数
    def run(self):
        t=time.time()
        while self.flag:
            print("循环正在执行")


if __name__ == "__main__":
    os.chdir(sys.path[0])
    # 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
    app = QApplication(sys.argv)
    # #创建一个我们生成的那个窗口，注意把类名修改为MainWindow
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
