from PyQt5 import  QtWidgets
import sys
from PyQt5.uic import loadUi
from PyQt5 import QtWidgets
from types import MethodType
import os
import sys

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        loadUi('form1.ui', self)


        # 将按钮点击事件和calc槽函数绑定
        self.pushButton.clicked.connect(self.addItem)
        self.pushButton_2.clicked.connect(self.addItems)
        self.comboBox.currentIndexChanged.connect(self.get_value)
        print(type(self.comboBox))

        # 重写showPopup函数
        def showPopup(self):
            # 先清空原有的选项
            self.clear()
            items_list = ["C", "C++", "Java", "Python", "JavaScript", "C#", "Swift", "go", "Ruby", "Lua", "PHP"]
            self.addItems(items_list)
            QtWidgets.QComboBox.showPopup(self)  # 弹出选项框

        # 使用MethodType将函数转换为方法，再绑定到实例上去
        self.comboBox_2.showPopup=MethodType(showPopup, self.comboBox_2)


    # 定义槽函数
    def addItem(self):
        self.comboBox.addItem("item")

    def addItems(self):
        items_list=["C","C++","Java","Python","JavaScript","C#","Swift","go","Ruby","Lua","PHP"]
        self.comboBox.addItems(items_list)

    def get_value(self):
        self.lineEdit.setText(self.comboBox.currentText())

        


if __name__ == "__main__":
    os.chdir(sys.path[0])
    # 创建了一个PyQt封装的QApplication对象,创建的时候,把系统参数传进去了.顾名思义,这一句创建了一个应用程序对象
    app = QtWidgets.QApplication(sys.argv)
    # #创建一个我们生成的那个窗口，注意把类名修改为MainWindow
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
