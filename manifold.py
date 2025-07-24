import tkinter as tk
from tkinter import font
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.dialogs.dialogs import Querybox, Dialog
import requests
import time
from datetime import datetime, timezone
import sys

# API地址
BASE_API_URL = "https://manifold.markets/api/v0"

# --- 分类选择弹窗 ---
class CategorySelectionDialog(Dialog):
    # 一个用来选分类的对话框
    def __init__(self, title, groups, callback, parent=None):
        self.groups = groups
        self.callback = callback
        super().__init__(parent=parent, title=title)

    def create_body(self, master):
        # 对话框主体，放个列表
        self.tree = ttk.Treeview(master, columns=('name',), show='', height=15)
        self.tree.pack(padx=10, pady=10, fill=BOTH, expand=YES)

        for group in self.groups:
            display_text = f"{group['name']} ({group['totalMembers']}人)"
            self.tree.insert('', END, values=(display_text,), iid=group['slug'])
        
        # 支持双击列表项直接确定
        self.tree.bind("<Double-1>", self.on_ok)
        return self.tree

    def on_ok(self, event=None):
        # 用户点了"确定"
        selection = self.tree.selection()
        if selection:
            selected_slug = selection[0]
            selected_group = next((g for g in self.groups if g['slug'] == selected_slug), None)
            if selected_group:
                self.callback(selected_group['slug'], selected_group['name'])
        super().on_ok()

    def create_buttonbox(self, master):
        # 对话框的按钮
        box = ttk.Frame(master)
        box.pack(pady=(0, 10))

        ok_button = ttk.Button(box, text="确定", command=self.on_ok, bootstyle='success')
        ok_button.pack(side=LEFT, padx=5)
        
        cancel_button = ttk.Button(box, text="取消", command=self.on_cancel, bootstyle='secondary')
        cancel_button.pack(side=LEFT, padx=5)
        
        self.bind("<Return>", self.on_ok)
        self.bind("<Escape>", self.on_cancel)


# --- 主程序 ---
class MarketMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Manifold Markets 浏览器")
        self.root.geometry("650x700")

        # 初始化一些程序要用的变量
        self.session = requests.Session()
        self.markets_cache = []
        self.selected_market_id = None
        self.selected_market_question = None
        self.refresh_interval_ms = 6000
        self.after_id = None # 用于控制定时刷新

        # 搜索框的灰色提示字
        self.placeholder_text = "输入关键词搜索..."
        self.placeholder_color = 'grey'
        self.default_fg_color = ttk.Style().lookup('TLabel', 'foreground')

        # 创建主界面框架
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(expand=YES, fill=BOTH)

        self.discovery_frame = ttk.Frame(main_frame)
        self.monitoring_frame = ttk.Frame(main_frame)
        
        # 底部状态栏
        self.status_text = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_text, padding=(10, 5), bootstyle="inverse-dark")
        self.status_bar.pack(side=BOTTOM, fill=X)
        
        # 初始化UI并显示主页
        self.setup_ui()
        self.show_discovery_view()
        
    def setup_ui(self):
        # 把创建界面的代码都放这儿
        self.setup_discovery_view()
        self.setup_monitoring_view()

    # --- 搜索框占位符处理 ---
    def set_status(self, text):
        # 更新状态栏的文字
        self.status_text.set(f" {text}")

    def add_placeholder(self):
        # 给搜索框加上灰色的提示词
        self.search_entry.insert(0, self.placeholder_text)
        self.search_entry.config(foreground=self.placeholder_color)

    def on_entry_focus_in(self, event):
        # 用户点进搜索框了
        if self.search_entry.get() == self.placeholder_text:
            self.search_entry.delete(0, "end")
            self.search_entry.config(foreground=self.default_fg_color)

    def on_entry_focus_out(self, event):
        # 用户点到别处了，如果搜索框是空的，就恢复提示词
        if not self.search_entry.get():
            self.add_placeholder()

    # --- 市场发现页面的UI和逻辑 ---
    def setup_discovery_view(self):
        # 搜索框和按钮
        search_frame = ttk.Frame(self.discovery_frame)
        search_frame.pack(fill=X, pady=(0, 15))
        self.search_entry = ttk.Entry(search_frame, font=("", 11))
        self.search_entry.pack(side=LEFT, expand=YES, fill=X, ipady=6)
        self.add_placeholder()
        self.search_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_entry_focus_out)
        self.search_entry.bind("<Return>", lambda event: self.search_markets()) # 回车直接搜索
        self.search_button = ttk.Button(search_frame, text="搜索", command=self.search_markets, bootstyle="info")
        self.search_button.pack(side=LEFT, padx=(8, 0))

        # 两个浏览按钮
        browse_frame = ttk.Frame(self.discovery_frame)
        browse_frame.pack(fill=X, pady=(0, 15))
        self.browse_button = ttk.Button(browse_frame, text="按分类浏览", command=self.browse_categories, bootstyle="outline-info", width=20)
        self.browse_button.pack(side=LEFT, expand=YES, fill=X, padx=(0, 5), ipady=4)
        self.newest_button = ttk.Button(browse_frame, text="查看最新", command=self.fetch_newest_markets, bootstyle="outline-info", width=20)
        self.newest_button.pack(side=RIGHT, expand=YES, fill=X, padx=(5, 0), ipady=4)

        # 市场列表，用Treeview实现，好看而且能去掉滚动条
        list_frame = ttk.Frame(self.discovery_frame)
        list_frame.pack(expand=YES, fill=BOTH, pady=5)
        self.market_list = ttk.Treeview(list_frame, columns=('market_info',), show='', selectmode='browse')
        self.market_list.pack(side=LEFT, expand=YES, fill=BOTH)
        self.market_list.bind("<MouseWheel>", self.on_mouse_wheel) # 绑定滚轮事件
        
        # 监控按钮
        self.select_button = ttk.Button(self.discovery_frame, text="开始监控", command=self.start_monitoring, state=DISABLED, bootstyle="success")
        self.select_button.pack(pady=(15, 0), fill=X, ipady=8)
        self.market_list.bind('<<TreeviewSelect>>', self.on_market_select)

    def on_mouse_wheel(self, event):
        # 滚轮控制列表上下滚动
        if event.delta > 0: self.market_list.yview_scroll(-1, "units")
        else: self.market_list.yview_scroll(1, "units")
        return "break"

    def on_market_select(self, event):
        # 选中列表里的一项后，让"开始监控"按钮能点
        if self.market_list.selection():
            self.select_button.config(state=NORMAL)

    def search_markets(self):
        # 按关键词搜索
        term = self.search_entry.get().strip()
        if not term or term == self.placeholder_text:
            Messagebox.show_warning("请输入搜索关键词。", "提示")
            return
        
        self.set_status(f"正在搜索 “{term}”...")
        try:
            params = {'term': term, 'limit': 100, 'sort': 'score'}
            response = self.session.get(f"{BASE_API_URL}/search-markets", params=params, timeout=15)
            response.raise_for_status()
            self.update_market_list(response.json())
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"搜索失败: {e}", "错误")
            self.set_status("搜索失败")

    def browse_categories(self):
        # 浏览分类
        self.set_status("正在获取分类列表...")
        try:
            response = self.session.get(f"{BASE_API_URL}/groups", params={'limit': 1000}, timeout=15)
            response.raise_for_status()
            groups = sorted(response.json(), key=lambda g: g.get('totalMembers', 0), reverse=True)
            CategorySelectionDialog(title="选择分类", groups=groups[:30], callback=self.fetch_markets_by_category)
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"获取分类失败: {e}", "错误")
            self.set_status("获取分类失败")
            
    def fetch_markets_by_category(self, group_slug, group_name):
        # 根据选好的分类拉取市场数据
        if not group_slug: return
        self.set_status(f"正在获取“{group_name}”分类下的市场...")
        try:
            response = self.session.get(f"{BASE_API_URL}/group/{group_slug}/markets", params={'limit': 200}, timeout=15)
            response.raise_for_status()
            self.update_market_list(response.json())
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"获取分类市场失败: {e}", "错误")
            self.set_status("获取分类市场失败")

    def fetch_newest_markets(self):
        # 获取最新的市场
        self.set_status("正在获取最新市场...")
        try:
            params = {'limit': 100, 'sort': 'created-time', 'order': 'desc'}
            response = self.session.get(f"{BASE_API_URL}/markets", params=params, timeout=15)
            response.raise_for_status()
            self.update_market_list(response.json())
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"获取最新市场失败: {e}", "错误")
            self.set_status("获取最新市场失败")

    def update_market_list(self, markets_data):
        # 把获取到的市场数据显示在列表里
        self.market_list.delete(*self.market_list.get_children())
        self.select_button.config(state=DISABLED)
        self.markets_cache.clear()
        
        current_time_ms = int(time.time() * 1000)
        # 过滤掉已经结束或关闭的市场
        valid_markets = [m for m in markets_data if not m.get('isResolved', True) and m.get('closeTime', 0) > current_time_ms]
        
        if not valid_markets:
            self.set_status("没有找到有效的市场。")
            self.market_list.insert('', END, values=("未找到相关市场",), iid="no_market")
            return
            
        self.markets_cache = sorted(valid_markets, key=lambda m: m.get('closeTime', 0))
        
        for market in self.markets_cache:
            close_date = datetime.fromtimestamp(market.get('closeTime', 0) / 1000)
            display_text = f"[{close_date.strftime('%Y-%m-%d')}] {market.get('question')}"
            self.market_list.insert('', END, values=(display_text,), iid=market['id'])
            
        self.set_status(f"已加载 {len(self.markets_cache)} 个市场。")

    def start_monitoring(self):
        # 点了"开始监控"按钮
        selected_items = self.market_list.selection()
        if not selected_items: return
        
        selected_id = selected_items[0]
        selected_market = next((m for m in self.markets_cache if m['id'] == selected_id), None)
        
        if not selected_market:
            Messagebox.show_error("找不到所选市场的详细信息。", "错误")
            return

        self.selected_market_id = selected_market.get('id')
        self.selected_market_question = selected_market.get('question')
        
        # 弹窗问用户刷新频率
        minutes = Querybox.get_float(
            prompt="请输入刷新频率(分钟), 如0.1代表6秒:",
            title="设置刷新率",
            initialvalue=0.1,
            minvalue=0.01
        )
        
        if minutes is not None:
            self.refresh_interval_ms = int(minutes * 60 * 1000)
            self.show_monitoring_view()
        
    # --- 监控页面的UI和逻辑 ---
    def setup_monitoring_view(self):
        # 返回按钮和数据显示区只在这里创建一次
        self.back_button = ttk.Button(self.monitoring_frame, text="« 返回", command=self.show_discovery_view, bootstyle="secondary-outline")
        # **BUG修复**: 移除 fill='x'，让按钮恢复正常大小
        self.back_button.pack(anchor='w', pady=(0, 10))
        
        self.data_display_frame = ttk.Frame(self.monitoring_frame)
        self.data_display_frame.pack(expand=YES, fill=BOTH)

    def fetch_and_update_data(self):
        # 定时刷新并显示数据
        if not self.selected_market_id: return
        
        # 先清空旧数据
        for widget in self.data_display_frame.winfo_children():
            widget.destroy()

        try:
            url = f"{BASE_API_URL}/market/{self.selected_market_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            market_data = response.json()
        except requests.exceptions.RequestException as e:
            market_data = None
            self.set_status(f"网络错误: {e}")
            ttk.Label(self.data_display_frame, text=f"网络错误: {e}", bootstyle="danger", font=("", 12)).pack(pady=20)
            # 即使出错，也要保证下一次刷新能继续
            self.after_id = self.root.after(self.refresh_interval_ms, self.fetch_and_update_data)
            return

        if not market_data:
            ttk.Label(self.data_display_frame, text="获取市场数据失败。", font=("", 12)).pack(pady=20)
        else:
            # 更新窗口标题
            short_question = (self.selected_market_question or "")[:30] + "..."
            self.root.title(f"监控中: {short_question}")
            
            # 显示问题
            question_font = font.Font(family="Segoe UI", size=16, weight="bold")
            ttk.Label(self.data_display_frame, text=market_data.get('question', self.selected_market_question), font=question_font, wraplength=600, justify="center").pack(pady=(10, 20))
            
            # 用一个带边框的Frame把结果包起来，好看点
            outcomes_labelframe = ttk.Labelframe(self.data_display_frame, text=" 市场预测 ", bootstyle="info")
            outcomes_labelframe.pack(pady=10, padx=10, fill=X)
            
            # 网格布局显示结果
            outcomes_frame = ttk.Frame(outcomes_labelframe, padding=15)
            outcomes_frame.pack(expand=YES, fill=X)
            outcomes_frame.columnconfigure(0, weight=1) # 选项这列宽一点
            
            header_font = font.Font(family="Segoe UI", size=11, weight="bold")
            ttk.Label(outcomes_frame, text="选项", font=header_font).grid(row=0, column=0, padx=10, pady=5, sticky="w")
            ttk.Label(outcomes_frame, text="概率", font=header_font).grid(row=0, column=1, padx=10, pady=5, sticky="e")
            ttk.Separator(outcomes_frame, orient=HORIZONTAL).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

            # 解析不同类型的市场
            market_type = market_data.get('outcomeType')
            outcomes = []
            if market_type == 'BINARY': # 是/否
                prob = market_data.get('probability', 0)
                outcomes = [{'name': '是', 'price': prob}, {'name': '否', 'price': 1 - prob}]
            elif market_type == 'MULTIPLE_CHOICE': # 多选
                answers = market_data.get('answers', [])
                outcomes = [{'name': ans.get('text'), 'price': ans.get('probability', 0)} for ans in answers]
                outcomes.sort(key=lambda x: x.get('price', 0), reverse=True)
            else:
                ttk.Label(self.data_display_frame, text=f"暂不支持的市场类型: {market_type}", font=("", 12)).pack(pady=20)
            
            # 循环显示每个选项
            for i, outcome in enumerate(outcomes[:10], start=2):
                name, price = outcome.get('name', 'N/A'), outcome.get('price', 0.0)
                ttk.Label(outcomes_frame, text=name, font=("Segoe UI", 12)).grid(row=i, column=0, padx=10, pady=6, sticky="w")
                ttk.Label(outcomes_frame, text=f"{price:.2%}", font=("Segoe UI", 13, "bold"), bootstyle="success").grid(row=i, column=1, padx=10, pady=6, sticky="e")
        
        update_time = datetime.now(timezone.utc).astimezone().strftime('%H:%M:%S')
        self.set_status(f"数据源: Manifold API | 更新于: {update_time}")
        
        # 设置下一次刷新
        self.after_id = self.root.after(self.refresh_interval_ms, self.fetch_and_update_data)

    # --- 页面切换 ---
    def show_discovery_view(self):
        # 显示主页
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        
        self.monitoring_frame.pack_forget()
        self.discovery_frame.pack(expand=YES, fill=BOTH)
        self.root.title("Manifold Markets 浏览器") 
        self.set_status("准备就绪, 请搜索或浏览市场。")

    def show_monitoring_view(self):
        # 显示监控页
        self.discovery_frame.pack_forget()
        self.monitoring_frame.pack(expand=YES, fill=BOTH)
        self.fetch_and_update_data()

# --- 程序入口 ---
if __name__ == "__main__":
    try:
        # 用一个好看的深色主题
        main_window = ttk.Window(themename="darkly")
        app = MarketMonitorApp(main_window)
        main_window.mainloop()
    except Exception as e:
        # 兜底的异常处理
        print(f"程序遇到未处理的异常: {e}")
        try: 
            Messagebox.show_error(f"程序遇到致命错误:\n\n{e}", "致命错误")
        except: 
            pass # 如果连GUI都出错了，就只在控制台打印
    finally:
        print("程序已退出。")
