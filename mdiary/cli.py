import re, os, sys
import json
import shutil
import markdown
from markdown.extensions.tables import TableExtension
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QCalendarWidget, QTextEdit, QLineEdit, QPushButton, QListWidget,
    QLabel, QMessageBox, QListWidgetItem, QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate, QSize
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QFont, QWheelEvent, QTextCharFormat, QBrush, QColor, QIcon, QCloseEvent
from mdiary.config import *

def format_md(contents: str) -> str:
    script = False
    ans = []
    clist = contents.split(r'\n')
    for cc in clist:
        if re.match(r'^```[^`]*', cc):
            script = not script
            ans.append(cc)
        if script:
            ans.append('  ' + cc)
        else:
            ans.append(cc)
    return '\n'.join(ans)

def highlight_html(html: str, keywords: list[str]) -> str:
    """
    在 html 中对 keywords 做高亮，返回新 html
    关键词支持中文/英文/空格/符号；自动避开已有标签
    """
    keywords = [k.strip() for k in keywords if len(k.strip()) > 0]
    if not keywords:
        return html

    # 1. 构造正则：多关键词 OR，支持整词或子串
    escaped = [re.escape(k.strip()) for k in keywords]
    if not escaped:
        return html
    pattern = re.compile('|'.join(escaped), flags=re.I)

    # 2. 把要替换的片段包上指定标签
    def wrap(m: re.Match) -> str:
        return f'<span class="highlight">{m.group(0)}</span>'

    # 3. 避开 HTML 标签内部属性，只处理“>...<”之间的文本
    #    用反向匹配切分，性能足够
    parts = re.split(r'(>[^<]*<)', html)
    for i, part in enumerate(parts):
        if part.startswith('>') and part.endswith('<'):
            parts[i] = pattern.sub(wrap, part)
    return ''.join(parts)
class CustomTextEdit(QTextEdit):
    # 自定义文本编辑控件，处理Ctrl+滚轮事件
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.setPlaceholderText('编辑模式')
    def wheelEvent(self, event: QWheelEvent):
        # 当Ctrl键按下时，调整字体大小而不滚动内容
        if event.modifiers() & Qt.ControlModifier:
            # 将事件传递给父窗口处理字体大小调整
            self.parent_app.wheelEvent(event)
            # 接受事件，防止内容滚动
            event.accept()
        else:
            # 正常处理滚轮事件（滚动内容）
            super().wheelEvent(event)

class DiaryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Markdown日记")

        # 初始化配置
        if (not os.path.exists(USER_CONFIG_FILE)
                or not os.path.exists(USER_STYLES_FILE)):
            os.makedirs(DIR_ASSETS, 0o755, exist_ok=True)
            # 默认配置
            self.config = {
                'font_size': 12,
                'zoom_factor': 1.0
            }
            with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            # 默认样式
            example_style = os.path.join(DIR_ASSETS, 'styles-example.css')
            shutil.copy(example_style, USER_STYLES_FILE)
        else:
            with open(USER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = json.load(f)

        ## 加载/应用配置参数
        self.font_size = self.config.get('font_size', 12)
        self.zoom_factor = self.config.get('zoom_factor', 1.0)
        pos_x = self.config.get('window_x', 100)
        pos_y = self.config.get('window_y', 100)
        pos_w = self.config.get('window_w', 1200)
        pos_h = self.config.get('window_h', 800)
        self.setGeometry(pos_x, pos_y, pos_w, pos_h)
        if not os.path.exists(DIR_DIARY):
            os.makedirs(DIR_DIARY, 0o700, exist_ok=True)

        ##
        self.current_date = QDate.currentDate()
        self.last_content = ""
        self.is_editing = True

        if not os.path.exists(DIR_DIARY):
            os.makedirs(DIR_DIARY)

        # 创建主布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # 创建左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(600)
        left_panel.setMinimumWidth(200)

        # 日历导航按钮
        nav_layout = QHBoxLayout()
        self.back_btn = QPushButton("后退")
        self.today_btn = QPushButton("今天")
        self.forward_btn = QPushButton("前进")
        self.edit_view_btn = QPushButton("编辑")
        self.preview_view_btn = QPushButton("查看")
        self.back_btn.clicked.connect(self.calendar_back)
        self.today_btn.clicked.connect(self.calendar_today)
        self.forward_btn.clicked.connect(self.calendar_forward)
        self.edit_view_btn.clicked.connect(self.switch_to_edit)
        self.preview_view_btn.clicked.connect(self.switch_to_preview)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.today_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.edit_view_btn)
        nav_layout.addWidget(self.preview_view_btn)
        left_layout.addLayout(nav_layout)

        # 日历控件
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.calendar.setSelectedDate(self.current_date)
        self.calendar.clicked.connect(self.on_date_selected)
        # 连接月份变化信号，更新高亮显示
        self.calendar.currentPageChanged.connect(self.highlight_dates_with_diary)
        left_layout.addWidget(self.calendar)
        # 显示日记数
        self.diary_count = QLabel("日记总数：0")
        left_layout.addWidget(self.diary_count)
        # 查找区域
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索日记...")
        self.search_input.textChanged.connect(self.search_diary)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)

        # 搜索结果列表
        self.search_results = QListWidget()
        self.search_results.itemClicked.connect(self.on_search_result_clicked)
        left_layout.addWidget(self.search_results)

        # 创建右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 日期标题
        self.date_label = QLabel()
        self.date_label.setFont(QFont("Arial", 16, QFont.Bold))
        right_layout.addWidget(self.date_label)

        # 编辑和预览视图
        self.edit_view = CustomTextEdit(self)
        self.edit_view.textChanged.connect(self.auto_save)
        self.edit_view.setFont(QFont("Courier New", self.font_size))

        # 预览视图（WebEngine）
        self.preview_view = QWebEngineView()
        self.preview_view.setZoomFactor(self.zoom_factor)

        # 默认显示编辑视图
        #self.edit_view.hide()
        #self.preview_view.show()
        #self.edit_view_btn.setEnabled(True)
        #self.preview_view_btn.setEnabled(False)

        right_layout.addWidget(self.edit_view, 1)
        right_layout.addWidget(self.preview_view, 1)

        # 添加到主布局
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 3)

        self.setCentralWidget(main_widget)
        self.update_date_label()

        # 初始化日历
        self.highlight_dates_with_diary()
        self.loading = True
        self.load_diary(self.current_date)
        #

    def update_date_label(self):
        date_str = self.current_date.toString("yyyy年MM月dd日 dddd")
        self.date_label.setText(date_str)

    def on_date_selected(self, date):
        self.current_date = date
        self.update_date_label()
        self.load_diary(date)

    def get_diary_filename(self, date):
        date_str = date.toString("yyyy-MM-dd")
        return os.path.join(DIR_DIARY, f"{date_str}.md")

    def load_diary(self, date):
        self.loading = True
        filename = self.get_diary_filename(date)
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                ## content = format_md(f.read())
                content = f.read()
                self.edit_view.setPlainText(content)
                self.render_markdown(content)
                self.last_content = content
                self.switch_to_preview()
        else:
            self.edit_view.setPlainText("")
            self.render_markdown("")
            self.last_content = ""
            self.switch_to_edit()
        self.loading = False
    def save_diary(self, date, content):
        filename = self.get_diary_filename(date)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

    def auto_save(self):
        if self.loading:
            return False
        content = self.edit_view.toPlainText()
        # 检查内容是否有变化
        if content != self.last_content:
            filename = self.get_diary_filename(self.current_date)
            if content.strip():
                # 有内容则保存
                self.save_diary(self.current_date, content)
            else:
                # 无内容则删除文件
                if os.path.exists(filename):
                    os.remove(filename)
            self.render_markdown(content)
            self.last_content = content
            # 更新日历高亮显示
            self.highlight_dates_with_diary()

    def wheelEvent(self, event: QWheelEvent):
        # 鼠标滚轮调整字号
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                # 放大字体
                self.font_size += 2
            else:
                # 缩小字体
                if self.font_size > 8:
                    self.font_size -= 2
            self.edit_view.setFont(QFont("Courier New", self.font_size))
            event.accept()
        else:
            super().wheelEvent(event)
        #

    def calendar_back(self):
        # 前进到上一个月
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        if month == 1:
            # 1月的上一个月是上一年的12月
            new_year = year - 1
            new_month = 12
        else:
            new_year = year
            new_month = month - 1
        self.calendar.setCurrentPage(new_year, new_month)

    def calendar_today(self):
        # 回到今天
        today = QDate.currentDate()
        self.calendar.setSelectedDate(today)
        self.on_date_selected(today)

    def calendar_forward(self):
        # 前进到下一个月
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        if month == 12:
            # 12月的下一个月是下一年的1月
            new_year = year + 1
            new_month = 1
        else:
            new_year = year
            new_month = month + 1
        self.calendar.setCurrentPage(new_year, new_month)

    def switch_to_edit(self):
        # 切换到编辑模式
        self.is_editing = True
        self.edit_view.show()
        self.preview_view.hide()
        self.edit_view_btn.setEnabled(False)
        self.preview_view_btn.setEnabled(True)

    def switch_to_preview(self):
        # 切换到预览模式
        self.is_editing = False
        self.edit_view.hide()
        self.preview_view.show()
        self.edit_view_btn.setEnabled(True)
        self.preview_view_btn.setEnabled(False)

    def render_markdown(self, content):
        # 渲染Markdown为HTML
        html = markdown.markdown(content, extensions=[TableExtension()])
        keywords = re.split(r'\W+', self.search_input.text().strip())
        html = highlight_html(html, keywords)
        # 加载CSS样式文件
        if os.path.exists(USER_STYLES_FILE):
            with open(USER_STYLES_FILE, 'r', encoding='utf-8') as f:
                css = f.read()
            # 将CSS嵌入到HTML中
            styled_html = f"""
<html>
<head>
<style>
{css}
</style>
</head>
<body>
{html}
</body>
</html>
"""
            self.preview_view.setHtml(styled_html)
        else:
            # 如果CSS文件不存在，使用默认样式
            self.preview_view.setHtml(html)

    def get_dates_with_diary(self):
        # 获取所有有日记的日期列表
        dates_with_diary = []
        if os.path.exists(DIR_DIARY):
            for filename in os.listdir(DIR_DIARY):
                if filename.endswith('.md'):
                    # 提取日期字符串 (格式: yyyy-MM-dd)
                    date_str = filename[:-3]
                    try:
                        # 转换为QDate对象
                        date = QDate.fromString(date_str, "yyyy-MM-dd")
                        if date.isValid():
                            dates_with_diary.append(date)
                    except Exception as e:
                        print(f"解析日期文件 {filename} 失败: {e}")
        return dates_with_diary

    def closeEvent(self, evt: QCloseEvent) -> None:
        try:
            geo = self.geometry()
            self.config.update({
                'font_size': self.font_size,
                'zoom_factor': self.preview_view.zoomFactor(),
                'window_x': geo.x(),
                'window_y': geo.y(),
                'window_w': geo.width(),
                'window_h': geo.height()
            })
            with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def highlight_dates_with_diary(self):
        # 在日历上高亮显示有日记的日期
        dates_with_diary = self.get_dates_with_diary()
        diary_count = len(dates_with_diary)
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        diary_month = len([x for x in dates_with_diary if x.year() == year and x.month() == month])
        self.diary_count.setText(f'日记总数：{diary_count}；当前月日记数：{diary_month}')
        # 重置所有日期格式
        default_format = QTextCharFormat()
        self.calendar.setDateTextFormat(QDate(), default_format)  # 清空所有格式

        # 创建高亮格式
        format_date_with_diary = QTextCharFormat()
        format_date_with_diary.setBackground(QBrush(QColor('#ffb6c1'))) ## 高亮颜色
        format_date_with_diary.setForeground(QBrush(QColor(0, 0, 0)))  # 黑色文字
        format_today = QTextCharFormat()
        format_today.setBackground(QBrush(QColor('#ff7f50'))) ## 高亮颜色
        format_today.setForeground(QBrush(QColor(0, 0, 0)))  # 黑色文字

        # 应用高亮格式到有日记的日期
        for date in dates_with_diary:
            self.calendar.setDateTextFormat(date, format_date_with_diary)
        self.calendar.setDateTextFormat(QDate.currentDate(), format_today)

    def search_diary(self):
        self.search_results.clear()
        keywords = self.search_input.text().strip()
        if keywords == '':
            return
        keywords = re.split(r'\W+', keywords)
        if not keywords:
            return
        # 遍历所有日记文件
        for filename in os.listdir(DIR_DIARY):
            if filename.endswith('.md'):
                filepath = os.path.join(DIR_DIARY, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                if len([k for k in keywords if k in content]) == len(keywords):
                    # 解析日期
                    date_str = filename[:-3]  # 去掉.md扩展名
                    date = QDate.fromString(date_str, "yyyy-MM-dd")

                    # 创建列表项
                    item_text = date.toString('yyyy-MM-dd')
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, date)
                    self.search_results.addItem(item)

    def on_search_result_clicked(self, item):
        date = item.data(Qt.UserRole)
        self.calendar.setSelectedDate(date)
        self.on_date_selected(date)

def main():
    app = QApplication(sys.argv)
    window = DiaryApp()
    window.setWindowIcon(QIcon(ICON_APP))
    window.show()
    sys.exit(app.exec_())
#
if __name__ == "__main__":
    main()
