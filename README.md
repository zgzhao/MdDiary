# Description
- 使用markdown撰写日记，或保存AI问答结果

# Install

-   创建并激活conda环境（如Notes）

``` example
conda create -n Notes python=3.11
conda activate Notes
```

-   进入项目根目录，执行安装程序（Debian Linux）

``` example
cd MarkdownNotes
chmod +x install.sh
./install.sh
```

-   运行程序

``` example
conda activate Notes
mdiary
```

# Problems

## fcitx

-   source:
    - /usr/lib/x86~64~-linux-gnu/qt5/plugins/platforminputcontexts/libfcitxplatforminputcontextplugin.so
-   target:
    - site-packages/PyQt5/Qt5/plugins/platforminputcontexts/
