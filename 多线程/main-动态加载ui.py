from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import sys
import os
from PyQt5.uic import loadUi
import time


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        loadUi('form1.ui', self)

        # 将按钮点击事件和calc槽函数绑定
        self.pushButton.clicked.connect(self.start)
        self.pushButton_2.clicked.connect(self.stop)
        #创建一个线程
        self.thread=MyThread()
        #连接子进程内的信号与槽函数，该槽函数用来更新button的显示值
        self.thread.sinOut.connect(self.update_button)
        


    # 定义槽函数
    def start(self):
        #使按钮不可用
        self.pushButton.setEnabled(False)
        self.pushButton_2.setEnabled(True)

        
        self.thread.set_flag_true()
        #此处必须用start方法启动子进程，不能用run方法
        self.thread.start()


    # 定义槽函数
    def stop(self):
        self.thread.set_flag_false()
        self.pushButton.setEnabled(True)
        self.pushButton.setText("开始")
        self.pushButton_2.setEnabled(False)

    def update_button(self,text):
        self.pushButton.setText(text)


#由于pyqt的主进程是UI进程，主进程中使用循环语句，会导致进程阻塞，UI界面会卡死，因此必须将耗时的作业放在子进程内操作，因此使用QThread创建子进程
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
            count=str(time.time()-t)[0:5]
            # 发射信号，传递时间参数
            self.sinOut.emit(count)
            print("正在执行")


if __name__ == "__main__":
    os.chdir(sys.path[0])
    # 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
    app = QApplication(sys.argv)
    # #创建一个我们生成的那个窗口，注意把类名修改为MainWindow
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
