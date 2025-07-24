import tkinter as tk
from tkinter import font, Listbox, Scrollbar
# 1. 引入 ttkbootstrap 库，这是实现现代化的关键
import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.dialogs.dialogs import Querybox, Dialog
import requests
import time
from datetime import datetime, timezone
import sys
import json

# ==============================================================================
#  程序配置 - Manifold Markets 官方 API v0
# ==============================================================================
BASE_API_URL = "https://manifold.markets/api/v0"

# ==============================================================================
#  主应用类：管理所有GUI窗口和逻辑
# ==============================================================================
# ==============================================================================
#  主应用类：管理所有GUI窗口和逻辑
# ==============================================================================
class MarketMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Manifold Markets 浏览器")
        self.root.geometry("600x650")

        self.session = requests.Session()
        self.markets_cache = []
        self.selected_market_id = None
        self.selected_market_question = None
        self.refresh_interval_ms = 6000
        self.after_id = None

        # 创建主框架
        self.discovery_frame = ttk.Frame(root, padding=10)
        self.monitoring_frame = ttk.Frame(root, padding=10)
        
        # 创建状态栏
        self.status_text = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_text, relief=tk.SUNKEN, anchor='w', padding=(5, 2), bootstyle="inverse-dark")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.setup_discovery_view()
        self.setup_monitoring_view()

        self.show_discovery_view()

    def set_status(self, text):
        self.status_text.set(f" {text}")

    # ------------------- 市场发现界面 (Discovery View) -------------------
    def setup_discovery_view(self):
        # 搜索框部分
        search_frame = ttk.Frame(self.discovery_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.search_entry = ttk.Entry(search_frame, width=40, font=("", 10))
        self.search_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=4)
        self.search_button = ttk.Button(search_frame, text="搜索", command=self.search_markets, bootstyle="info")
        self.search_button.pack(side=tk.LEFT, padx=(5, 0))

        # 浏览按钮部分
        browse_frame = ttk.Frame(self.discovery_frame)
        browse_frame.pack(fill=tk.X, pady=5)
        
        self.browse_button = ttk.Button(browse_frame, text="按分类浏览", command=self.browse_categories)
        self.browse_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.newest_button = ttk.Button(browse_frame, text="查看最新市场", command=self.fetch_newest_markets)
        self.newest_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))

        # 结果列表部分
        list_frame = ttk.Frame(self.discovery_frame)
        list_frame.pack(expand=True, fill=tk.BOTH, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.market_listbox = Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10), selectbackground="#444")
        self.market_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        scrollbar.config(command=self.market_listbox.yview)

        # 选择按钮
        self.select_button = ttk.Button(self.discovery_frame, text="监控选中市场", command=self.start_monitoring, state=tk.DISABLED, bootstyle="success")
        self.select_button.pack(pady=10, fill=tk.X, ipady=5)
        
        self.market_listbox.bind('<<ListboxSelect>>', self.on_market_select)

    def on_market_select(self, event):
        if self.market_listbox.curselection():
            self.select_button.config(state=tk.NORMAL)

    def search_markets(self):
        term = self.search_entry.get().strip()
        if not term:
            Messagebox.show_warning("请输入搜索关键词。", "提示")
            return
        self.set_status(f"正在搜索 “{term}”...")
        try:
            params = {'term': term, 'limit': 100, 'sort': 'score'}
            response = self.session.get(f"{BASE_API_URL}/search-markets", params=params)
            response.raise_for_status()
            self.update_market_list(response.json())
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"搜索请求失败: {e}", "错误")
            self.set_status("搜索失败")

    def browse_categories(self):
        self.set_status("正在获取分类列表...")
        try:
            response = self.session.get(f"{BASE_API_URL}/groups", params={'limit': 1000})
            response.raise_for_status()
            groups = sorted(response.json(), key=lambda g: g.get('totalMembers', 0), reverse=True)
            CategorySelectionDialog(title="选择分类", groups=groups[:30], callback=self.fetch_markets_by_category)
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"获取分类失败: {e}", "错误")
            self.set_status("获取分类失败")
            
    def fetch_markets_by_category(self, group_slug, group_name):
        if not group_slug: return
        self.set_status(f"正在获取 “{group_name}” 分类的市场...")
        try:
            response = self.session.get(f"{BASE_API_URL}/group/{group_slug}/markets", params={'limit': 200})
            response.raise_for_status()
            self.update_market_list(response.json())
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"获取分类市场失败: {e}", "错误")
            self.set_status("获取分类市场失败")

    def fetch_newest_markets(self):
        self.set_status("正在获取最新市场...")
        try:
            params = {'limit': 100, 'sort': 'created-time', 'order': 'desc'}
            response = self.session.get(f"{BASE_API_URL}/markets", params=params)
            response.raise_for_status()
            self.update_market_list(response.json())
        except requests.exceptions.RequestException as e:
            Messagebox.show_error(f"获取最新市场失败: {e}", "错误")
            self.set_status("获取最新市场失败")

    def update_market_list(self, markets):
        self.market_listbox.delete(0, tk.END)
        self.select_button.config(state=tk.DISABLED)
        self.markets_cache = []
        
        final_markets = []
        current_time_ms = int(time.time() * 1000)
        for market in markets:
            if not market.get('isResolved', True) and market.get('closeTime', 0) > current_time_ms:
                final_markets.append(market)
        
        if not final_markets:
            self.set_status("未找到任何有效的、尚未结束的市场。")
            return
            
        self.markets_cache = sorted(final_markets, key=lambda m: m.get('closeTime', 0))
        
        for market in self.markets_cache:
            close_date = datetime.fromtimestamp(market.get('closeTime', 0) / 1000)
            display_text = f"[{close_date.strftime('%Y-%m-%d')}] {market.get('question')}"
            self.market_listbox.insert(tk.END, display_text)
        self.set_status(f"已加载 {len(self.markets_cache)} 个有效市场。")

    def start_monitoring(self):
        selected_indices = self.market_listbox.curselection()
        if not selected_indices: return
        
        selected_market = self.markets_cache[selected_indices[0]]
        self.selected_market_id = selected_market.get('id')
        self.selected_market_question = selected_market.get('question')
        
        # 使用 Querybox.get_float 来获取浮点数输入
        minutes = Querybox.get_float(
            prompt="请输入刷新频率（分钟，可输入小数如0.1代表6秒）:",
            title="刷新频率",
            initialvalue=0.1,
            minvalue=0.01
        )
        
        if minutes is not None:
            self.refresh_interval_ms = int(minutes * 60 * 1000)
            self.show_monitoring_view()
        
    # ------------------- 实时监控界面 (Monitoring View) -------------------
    def setup_monitoring_view(self):
        self.back_button = ttk.Button(self.monitoring_frame, text="« 返回主页", command=self.show_discovery_view, bootstyle="secondary-outline")
        self.back_button.pack(anchor='w', pady=(0, 10))
        self.data_display_frame = ttk.Frame(self.monitoring_frame)
        self.data_display_frame.pack(expand=True, fill=tk.BOTH)

    def fetch_and_update_data(self):
        if not self.selected_market_id: return
        
        url = f"{BASE_API_URL}/market/{self.selected_market_id}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            market_data = response.json()
            api_error = None
        except requests.exceptions.RequestException as e:
            market_data = None
            api_error = f"网络错误: {e}"

        for widget in self.data_display_frame.winfo_children():
            widget.destroy()
        
        self.root.title(f"Manifold监控: {self.selected_market_question}")

        if api_error:
            ttk.Label(self.data_display_frame, text=api_error, foreground="red", font=("", 12)).pack(pady=20)
        elif not market_data:
            ttk.Label(self.data_display_frame, text="未能获取到市场数据。", font=("", 12)).pack(pady=20)
        else:
            question_font = font.Font(family="Segoe UI", size=14, weight="bold")
            ttk.Label(self.data_display_frame, text=market_data.get('question', self.selected_market_question), font=question_font, wraplength=550, justify="center").pack(pady=(10, 15))

            outcomes_frame = ttk.Frame(self.data_display_frame)
            outcomes_frame.pack(pady=10)
            
            header_font = font.Font(family="Segoe UI", size=11, weight="bold")
            ttk.Label(outcomes_frame, text="选项", font=header_font).grid(row=0, column=0, padx=20, pady=5, sticky="w")
            ttk.Label(outcomes_frame, text="预测概率", font=header_font).grid(row=0, column=1, padx=20, pady=5, sticky="e")
            
            market_type = market_data.get('outcomeType')
            
            outcomes = []
            if market_type == 'BINARY':
                probability = market_data.get('probability', 0)
                outcomes = [{'name': 'Yes', 'price': probability}, {'name': 'No', 'price': 1 - probability}]
            elif market_type == 'MULTIPLE_CHOICE':
                outcomes = [{'name': ans.get('text'), 'price': ans.get('probability', 0)} for ans in market_data.get('answers', [])]
                outcomes.sort(key=lambda x: x.get('price', 0), reverse=True)
            else:
                ttk.Label(self.data_display_frame, text=f"不支持的市场类型: {market_type}", font=("", 12)).pack(pady=20)
                
            for i, outcome in enumerate(outcomes[:10], start=1):
                name = outcome.get('name', 'N/A')
                price = outcome.get('price', 0.0)
                win_percentage = f"{price:.2%}"
                ttk.Label(outcomes_frame, text=name, font=("Segoe UI", 12)).grid(row=i, column=0, padx=20, pady=4, sticky="w")
                ttk.Label(outcomes_frame, text=win_percentage, font=("Segoe UI", 12, "bold"), bootstyle="success").grid(row=i, column=1, padx=20, pady=4, sticky="e")

        update_time = datetime.now(timezone.utc).astimezone().strftime('%H:%M:%S')
        self.set_status(f"数据来源: Manifold Markets API | 最后更新: {update_time}")
        
        self.after_id = self.root.after(self.refresh_interval_ms, self.fetch_and_update_data)

    # ------------------- 视图切换 (View Switching) -------------------
    def show_discovery_view(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        
        self.monitoring_frame.pack_forget()
        self.discovery_frame.pack(expand=True, fill=tk.BOTH)
        self.root.title("Manifold Markets 浏览器")
        self.set_status("准备就绪。请搜索或浏览市场。")

    def show_monitoring_view(self):
        self.discovery_frame.pack_forget()
        self.monitoring_frame.pack(expand=True, fill=tk.BOTH)
        self.fetch_and_update_data()

# ==============================================================================
#  辅助类：用于分类选择的弹出对话框 (已更新为 ttkbootstrap.Dialog)
# ==============================================================================
class CategorySelectionDialog(Dialog):
    def __init__(self, title, groups, callback, parent=None):
        self.groups = groups
        self.callback = callback
        super().__init__(parent=parent, title=title)

    def create_body(self, master):
        self.listbox = Listbox(master, width=50, height=15)
        for group in self.groups:
            self.listbox.insert(tk.END, f"{group['name']} ({group['totalMembers']} 成员)")
        self.listbox.pack(padx=10, pady=10)
        return self.listbox

    def on_ok(self, event=None):
        selected_indices = self.listbox.curselection()
        if selected_indices:
            selected_group = self.groups[selected_indices[0]]
            self.callback(selected_group['slug'], selected_group['name'])
        super().on_ok() # 调用父类的方法来关闭窗口
        
    def create_buttonbox(self, master):
        box = ttk.Frame(master)
        ok_button = ttk.Button(box, text="确定", command=self.on_ok, bootstyle='success')
        ok_button.pack(side=tk.LEFT, padx=5, pady=10)
        cancel_button = ttk.Button(box, text="取消", command=self.on_cancel, bootstyle='secondary')
        cancel_button.pack(side=tk.LEFT, padx=5, pady=10)
        self.bind("<Return>", self.on_ok)
        self.bind("<Escape>", self.on_cancel)
        box.pack()
        
# ==============================================================================
#  主程序入口
# ==============================================================================
if __name__ == "__main__":
    try:
        # 2. 创建一个 ttkbootstrap 窗口，并选择一个主题
        # 常见主题: 'litera', 'darkly', 'superhero', 'solar', 'cyborg', 'vapor'
        main_window = ttk.Window(themename="superhero")
        app = MarketMonitorApp(main_window)
        main_window.mainloop()
    except Exception as e:
        # messagebox 在GUI未完全初始化时可能失效，保留print作为备用
        print(f"程序遇到未处理的异常: {e}")
        try:
            Messagebox.show_error(f"程序遇到未处理的异常:\n\n{e}", "致命错误")
        except:
            pass
    finally:
        print("\n程序已退出。")