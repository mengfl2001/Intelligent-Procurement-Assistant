import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import pandas as pd
import asyncio

from core.async_runner import async_runner
from core.api_client import api_client
from core.data_processor import DataProcessor
from core.task_manager import TaskManager
from utils.logger import logger
from config.config import load_config, get_api_config, set_api_key, set_base_url, set_model_name


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self._config = load_config()
        self._ui_config = self._config.get('ui', {})
        
        title = self._ui_config.get('app_title', 'SmartPurchaseAgent - 智能采购助手')
        width = self._ui_config.get('window_width', 1200)
        height = self._ui_config.get('window_height', 800)
        primary_color = self._ui_config.get('primary_color', '#1E90FF')
        
        self.title(title)
        self.geometry(f"{width}x{height}")
        
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        self._primary_color = primary_color
        
        self._uploaded_data = None
        self._is_running = False
        self._is_paused = False
        self._progress_value = 0
        self._task_manager = None
        self._data_processor = DataProcessor()
        self._is_logged_in = False
        
        self._setup_layout()
        self._load_config_to_ui()
        self._start_background_services()
        self._start_log_poller()
    
    def _setup_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        
        left_panel = ctk.CTkFrame(self, width=300, corner_radius=10, fg_color="#ffffff")
        left_panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        left_panel.grid_propagate(False)
        self._setup_config_panel(left_panel)
        
        right_panel = ctk.CTkFrame(self, corner_radius=10, fg_color="#ffffff")
        right_panel.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        self._setup_task_panel(right_panel)
        
        bottom_panel = ctk.CTkFrame(self, height=180, corner_radius=10, fg_color="#ffffff")
        bottom_panel.grid(row=1, column=0, columnspan=2, padx=10, pady=0, sticky="ew")
        bottom_panel.grid_propagate(False)
        bottom_panel.grid_rowconfigure(0, weight=1)
        bottom_panel.grid_columnconfigure(0, weight=1)
        self._setup_log_panel(bottom_panel)
    
    def _setup_config_panel(self, parent):
        title_label = ctk.CTkLabel(parent, text="API 配置", font=("Arial", 16, "bold"), text_color="#333333")
        title_label.pack(pady=15, padx=10, anchor="w")
        
        api_key_label = ctk.CTkLabel(parent, text="API Key", text_color="#666666")
        api_key_label.pack(pady=(10, 5), padx=15, anchor="w")
        self._api_key_entry = ctk.CTkEntry(parent, width=250, placeholder_text="请输入API Key", show="*", 
                                           fg_color="#f5f5f5", border_color=self._primary_color, text_color="#333333")
        self._api_key_entry.pack(pady=(0, 10), padx=15)
        
        base_url_label = ctk.CTkLabel(parent, text="Base URL", text_color="#666666")
        base_url_label.pack(pady=(10, 5), padx=15, anchor="w")
        self._base_url_entry = ctk.CTkEntry(parent, width=250, placeholder_text="https://api.example.com",
                                           fg_color="#f5f5f5", border_color=self._primary_color, text_color="#333333")
        self._base_url_entry.pack(pady=(0, 10), padx=15)
        
        model_name_label = ctk.CTkLabel(parent, text="模型名称", text_color="#666666")
        model_name_label.pack(pady=(10, 5), padx=15, anchor="w")
        self._model_name_entry = ctk.CTkEntry(parent, width=250, placeholder_text="qwen3.6-flash",
                                             fg_color="#f5f5f5", border_color=self._primary_color, text_color="#333333")
        self._model_name_entry.pack(pady=(0, 10), padx=15)
        
        save_btn = ctk.CTkButton(parent, text="保存配置", command=self._save_config, width=115,
                                 fg_color=self._primary_color, hover_color="#00BFFF")
        save_btn.pack(side="left", pady=20, padx=(15, 5))
        
        test_btn = ctk.CTkButton(parent, text="测试连通性", command=self._test_api_connection, width=115,
                                 fg_color=self._primary_color, hover_color="#00BFFF")
        test_btn.pack(side="left", pady=20, padx=(5, 15))
        
        status_frame = ctk.CTkFrame(parent, height=60, corner_radius=8, fg_color="#f5f5f5")
        status_frame.pack(pady=10, padx=15, fill="x")
        status_frame.grid_propagate(False)
        
        status_label = ctk.CTkLabel(status_frame, text="连接状态:", text_color="#666666")
        status_label.pack(pady=(8, 0), padx=10, anchor="w")
        
        self._connection_status = ctk.CTkLabel(status_frame, text="未测试", text_color="#999999")
        self._connection_status.pack(pady=(5, 0), padx=10, anchor="w")
    
    def _setup_task_panel(self, parent):
        top_frame = ctk.CTkFrame(parent, fg_color="#ffffff")
        top_frame.pack(pady=10, padx=10, fill="x")
        
        login_btn = ctk.CTkButton(top_frame, text="用户登录", command=self._login_to_1688, width=100,
                                  fg_color=self._primary_color, hover_color="#00BFFF")
        login_btn.pack(side="left", padx=(0, 10))
        
        self._login_status_label = ctk.CTkLabel(top_frame, text="未登录", text_color="#ff4444", font=("Arial", 12, "bold"))
        self._login_status_label.pack(side="left", padx=(0, 20))
        
        upload_btn = ctk.CTkButton(top_frame, text="上传 Excel", command=self._upload_excel, width=100,
                                  fg_color=self._primary_color, hover_color="#00BFFF")
        upload_btn.pack(side="left", padx=(0, 10))
        
        self._upload_info = ctk.CTkLabel(top_frame, text="未选择文件", text_color="#666666")
        self._upload_info.pack(side="left")
        
        tree_frame = ctk.CTkFrame(parent, fg_color="#ffffff", border_width=1, border_color="#e0e0e0")
        tree_frame.pack(pady=(0, 10), padx=10, fill="both", expand=True)
        
        self._tree = ttk.Treeview(tree_frame, show="headings")
        self._tree.pack(side="left", fill="both", expand=True)
        
        style = ttk.Style()
        style.configure("Treeview", background="#ffffff", foreground="#333333", 
                       fieldbackground="#ffffff", bordercolor="#e0e0e0")
        style.configure("Treeview.Heading", background="#f0f0f0", foreground="#333333")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        scrollbar.pack(side="right", fill="y")
        self._tree.configure(yscrollcommand=scrollbar.set)
        
        bottom_frame = ctk.CTkFrame(parent, fg_color="#ffffff")
        bottom_frame.pack(pady=(0, 10), padx=10, fill="x")
        
        start_btn = ctk.CTkButton(bottom_frame, text="开始采购", command=self._start_purchase, width=120,
                                  fg_color=self._primary_color, hover_color="#00BFFF")
        start_btn.pack(side="left", padx=(0, 10))
        self._start_btn = start_btn
        
        pause_btn = ctk.CTkButton(bottom_frame, text="暂停", command=self._pause_purchase, width=120, state="disabled",
                                  fg_color="#FFA500", hover_color="#FF8C00")
        pause_btn.pack(side="left", padx=(0, 10))
        self._pause_btn = pause_btn
        
        stop_btn = ctk.CTkButton(bottom_frame, text="停止", command=self._stop_purchase, width=120, state="disabled",
                                 fg_color="#ff4444", hover_color="#cc0000")
        stop_btn.pack(side="left", padx=(0, 10))
        self._stop_btn = stop_btn
    
    def _setup_log_panel(self, parent):
        log_frame = ctk.CTkFrame(parent, corner_radius=8, fg_color="#f5f5f5")
        log_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        self._log_text = ctk.CTkTextbox(log_frame, state="disabled", font=("Consolas", 11),
                                       fg_color="#ffffff", text_color="#333333", border_color="#e0e0e0")
        self._log_text.pack(pady=5, padx=5, fill="both", expand=True)
        
        progress_frame = ctk.CTkFrame(parent, height=40, fg_color="#ffffff")
        progress_frame.pack(pady=(0, 10), padx=10, fill="x")
        progress_frame.grid_propagate(False)
        
        progress_label = ctk.CTkLabel(progress_frame, text="进度:", text_color="#666666")
        progress_label.pack(side="left", padx=(0, 10))
        
        self._progress_bar = ctk.CTkProgressBar(progress_frame, width=800,
                                                 progress_color=self._primary_color)
        self._progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._progress_bar.set(0)
        
        progress_value_label = ctk.CTkLabel(progress_frame, text="0%", text_color="#666666")
        progress_value_label.pack(side="left")
        self._progress_value_label = progress_value_label
    
    def _load_config_to_ui(self):
        api_config = get_api_config()
        self._api_key_entry.insert(0, api_config.get('api_key', ''))
        self._base_url_entry.insert(0, api_config.get('base_url', ''))
        self._model_name_entry.insert(0, api_config.get('model_name', ''))
    
    def _save_config(self):
        api_key = self._api_key_entry.get().strip()
        base_url = self._base_url_entry.get().strip()
        model_name = self._model_name_entry.get().strip()
        
        set_api_key(api_key)
        set_base_url(base_url)
        set_model_name(model_name)
        
        messagebox.showinfo("成功", "配置已保存")
        logger.info("配置已保存")
    
    def _start_background_services(self):
        async_runner.start()
    
    def _start_log_poller(self):
        def poll_logs():
            while True:
                log_entry = logger.get_log(block=False)
                if log_entry:
                    self._log_text.configure(state="normal")
                    self._log_text.insert(tk.END, log_entry + "\n")
                    self._log_text.see(tk.END)
                    self._log_text.configure(state="disabled")
                else:
                    break
            self.after(100, poll_logs)
        
        self.after(100, poll_logs)
    
    def _test_api_connection(self):
        api_key = self._api_key_entry.get().strip()
        base_url = self._base_url_entry.get().strip()
        model_name = self._model_name_entry.get().strip()
        
        if not api_key or not base_url:
            messagebox.showerror("错误", "API Key 和 Base URL 不能为空")
            return
        
        api_client.set_config(api_key, base_url, model_name)
        logger.info(f"开始测试 API 连通性: {base_url}")
        
        def on_test_result(result):
            self.after(0, lambda: self._handle_test_result(result))
        
        async_runner.submit(api_client.test_connection(), on_test_result)
    
    def _handle_test_result(self, result):
        if isinstance(result, Exception):
            message = str(result)
            success = False
        else:
            success = result.get("success", False)
            message = result.get("message", "")
        
        if success:
            self._connection_status.configure(text="已连接", text_color="#00cc00")
            messagebox.showinfo("成功", message)
            logger.info("API 连接测试成功")
        else:
            self._connection_status.configure(text="连接失败", text_color="#ff4444")
            messagebox.showerror("失败", message)
            logger.error(f"API 连接测试失败: {message}")
    
    def _upload_excel(self):
        file_path = filedialog.askopenfilename(
            title="选择 Excel 文件",
            filetypes=[("Excel 文件", "*.xlsx;*.xls"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            processed_df, errors = self._data_processor.process_excel(file_path)
            
            if errors:
                error_msg = "\n".join(errors)
                messagebox.showwarning("数据校验警告", error_msg)
            
            if processed_df.empty:
                self._upload_info.configure(text="数据校验失败")
                return
            
            self._uploaded_data = processed_df
            self._upload_info.configure(text=f"已加载: {len(self._uploaded_data)} 条有效数据", text_color="#00cc00")
            logger.info(f"成功加载 Excel 文件: {file_path}, 共 {len(self._uploaded_data)} 条有效数据")
            self._display_data_preview()
            
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
            logger.error(f"加载 Excel 文件失败: {str(e)}")
    
    def _display_data_preview(self):
        for col in self._tree.get_children():
            self._tree.delete(col)
        
        if self._uploaded_data is None:
            return
        
        columns = list(self._uploaded_data.columns)
        self._tree["columns"] = columns
        
        for col in columns:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=120)
        
        for idx, row in self._uploaded_data.iterrows():
            self._tree.insert("", tk.END, values=list(row))
    
    def _login_to_1688(self):
        logger.info("开始登录流程")
        async_runner.submit(self._do_login())
    
    async def _do_login(self):
        try:
            from tools.browser_tools import BrowserTools
            
            browser_tools = BrowserTools(headless=False)
            logger.info("打开1688登录页面...")
            await browser_tools.navigate("https://login.1688.com", highlight=False)
            
            logger.info("登录状态更新为: 已登录")
            self._is_logged_in = True
            self.after(0, self._update_login_status)
            
        except Exception as e:
            logger.error(f"登录过程异常: {str(e)}")
            self._is_logged_in = False
            self.after(0, self._update_login_status)
    
    def _update_login_status(self):
        if self._is_logged_in:
            self._login_status_label.configure(text="已登录", text_color="#00cc00")
            logger.info("登录状态更新为: 已登录")
        else:
            self._login_status_label.configure(text="未登录", text_color="#ff4444")
            logger.info("登录状态更新为: 未登录")
    
    def _start_purchase(self):
        if self._uploaded_data is None:
            messagebox.showwarning("警告", "请先上传 Excel 文件")
            return
        
        api_key = self._api_key_entry.get().strip()
        base_url = self._base_url_entry.get().strip()
        
        if not api_key or not base_url:
            messagebox.showerror("错误", "请先配置 API Key 和 Base URL")
            return
        
        self._task_manager = TaskManager(api_key=api_key, base_url=base_url, max_concurrent=2)
        
        self._task_manager.set_callbacks(
            progress_callback=self._on_progress_update,
            log_callback=self._on_log_update
        )
        
        self._is_running = True
        self._is_paused = False
        self._progress_value = 0
        
        self._update_progress(0)
        self._pause_btn.configure(state="normal")
        self._stop_btn.configure(state="normal")
        
        logger.info("开始采购任务")
        
        async_runner.submit(self._run_purchase_task())
    
    def _on_progress_update(self, completed: int, total: int, message: str = ""):
        if total > 0:
            progress = (completed / total) * 100
            self.after(0, lambda p=progress: self._update_progress(p))
        
        if message:
            logger.info(message)
    
    def _on_log_update(self, message: str):
        logger.info(message)
    
    def _pause_purchase(self):
        if self._task_manager:
            if self._is_paused:
                self._task_manager.resume()
                self._pause_btn.configure(text="暂停")
            else:
                self._task_manager.pause()
                self._pause_btn.configure(text="继续")
        
        self._is_paused = not self._is_paused
    
    def _stop_purchase(self):
        if self._task_manager:
            self._task_manager.stop()
        
        self._is_running = False
        self._is_paused = False
        self._pause_btn.configure(text="暂停", state="disabled")
        self._stop_btn.configure(state="disabled")
    
    async def _run_purchase_task(self):
        try:
            report_path = await self._task_manager.run_and_report(self._uploaded_data)
            
            self.after(0, lambda path=report_path: self._purchase_task_completed(path))
            
        except Exception as e:
            logger.error(f"采购任务执行异常: {str(e)}")
            self.after(0, lambda: self._purchase_task_completed(None))
    
    def _update_progress(self, value):
        self._progress_value = value
        self._progress_bar.set(value / 100)
        self._progress_value_label.configure(text=f"{int(value)}%")
    
    def _purchase_task_completed(self, report_path: str = None):
        self._is_running = False
        self._pause_btn.configure(text="暂停", state="disabled")
        self._stop_btn.configure(state="disabled")
        
        if self._progress_value >= 100:
            logger.info("采购任务完成")
            
            if report_path:
                messagebox.showinfo("完成", f"采购任务已完成!\n\n报告已生成:\n{report_path}")
            else:
                messagebox.showinfo("完成", "采购任务已完成")
        else:
            logger.info("采购任务已终止")
            messagebox.showwarning("终止", "采购任务已终止")
    
    def destroy(self):
        async_runner.stop()
        super().destroy()