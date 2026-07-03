"""adapter 转接头包：main.py 启动时自动扫描本目录。

加载规则（见 libs/adapter_loader.py）：
- 文件名以 ``_`` 开头的不加载（``__init__`` 与 ``_disabled`` 等皆被跳过）；
- 其余 .py 全部加载，收集 BaseAdapter 子类；
- 两个类的 id 相同则启动弹窗报错并退出。
每个文件定义一个类，类属性 id 为唯一标识。
"""
