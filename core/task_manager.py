import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional, Callable
import pandas as pd

from agent.purchase_agent import PurchaseAgent
from core.data_processor import DataProcessor


class TaskManager:
    def __init__(self, api_key: str, base_url: str, max_concurrent: int = 2):
        self.api_key = api_key
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self._is_running = False
        self._is_paused = False
        self._pending_tasks: List[Dict] = []
        self._completed_tasks: List[Dict] = []
        self._active_tasks: int = 0
        self._total_tasks: int = 0
        self._progress_callback: Optional[Callable[[int, int, str], None]] = None
        self._log_callback: Optional[Callable[[str], None]] = None
        self._task_semaphore: asyncio.Semaphore = None
        self._pause_event: asyncio.Event = None
    
    def set_callbacks(
        self, 
        progress_callback: Callable[[int, int, str], None],
        log_callback: Callable[[str], None]
    ):
        self._progress_callback = progress_callback
        self._log_callback = log_callback
    
    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)
    
    def _update_progress(self, completed: int, total: int, message: str = ""):
        if self._progress_callback:
            self._progress_callback(completed, total, message)
    
    async def _execute_single_task(self, task_data: Dict) -> Dict:
        task_id = task_data.get('id', 0)
        url = task_data.get('url', '')
        item_name = task_data.get('item_name', '')
        quantity = task_data.get('quantity', 1)
        color = task_data.get('color', '')
        size = task_data.get('size', '')
        product_type = task_data.get('product_type', '')
        
        self._log(f"开始执行任务 {task_id}/{self._total_tasks}: {item_name} (类型: {product_type}, 颜色: {color}, 尺码: {size})")
        self._update_progress(task_id - 1, self._total_tasks, f"正在采购第 {task_id}/{self._total_tasks} 个...")
        
        result = {
            'id': task_id,
            'url': url,
            'item_name': item_name,
            'quantity': quantity,
            'color': color,
            'size': size,
            'status': 'failed',
            'message': '',
            'screenshot_path': '',
            'steps': 0
        }
        
        try:
            agent = PurchaseAgent(api_key=self.api_key, base_url=self.base_url)
            
            while self._is_paused and self._is_running:
                self._log(f"任务 {task_id} 已暂停，等待继续...")
                await asyncio.sleep(0.5)
            
            if not self._is_running:
                result['message'] = '任务已被用户停止'
                return result
            
            purchase_result = await agent.execute_purchase_task(url, item_name, quantity, color, size, product_type)
            
            result['status'] = purchase_result.get('status', 'failed')
            result['message'] = purchase_result.get('message', '')
            result['screenshot_path'] = purchase_result.get('screenshot_path', '')
            
            if 'steps' in purchase_result:
                result['steps'] = purchase_result['steps']
            
            if result['status'] == 'success':
                self._log(f"任务 {task_id}/{self._total_tasks} 执行成功")
            else:
                self._log(f"任务 {task_id}/{self._total_tasks} 执行失败: {result['message']}")
        
        except Exception as e:
            result['message'] = str(e)
            self._log(f"任务 {task_id}/{self._total_tasks} 执行异常: {str(e)}")
        
        finally:
            self._active_tasks -= 1
        
        return result
    
    async def _worker(self):
        while self._pending_tasks and self._is_running:
            task_data = self._pending_tasks.pop(0)
            
            async with self._task_semaphore:
                result = await self._execute_single_task(task_data)
                self._completed_tasks.append(result)
                
                completed_count = len(self._completed_tasks)
                self._update_progress(completed_count, self._total_tasks)
                
                if completed_count == self._total_tasks:
                    self._log("所有任务执行完成")
    
    async def start(self, data_df: pd.DataFrame) -> bool:
        if self._is_running:
            self._log("任务管理器已在运行中")
            return False
        
        self._is_running = True
        self._is_paused = False
        self._completed_tasks = []
        self._active_tasks = 0
        
        self._pending_tasks = []
        for idx, row in data_df.iterrows():
            self._pending_tasks.append({
                'id': idx + 1,
                'url': row.get('url', ''),
                'item_name': row.get('item_name', ''),
                'quantity': int(row.get('quantity', 1)),
                'color': row.get('color', ''),
                'size': row.get('size', ''),
                'product_type': row.get('product_type', '')
            })
        
        self._total_tasks = len(self._pending_tasks)
        self._task_semaphore = asyncio.Semaphore(self.max_concurrent)
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        
        self._log(f"开始执行采购任务，共 {self._total_tasks} 个任务，串行执行模式")
        
        await self._batch_worker()
        
        self._is_running = False
        
        return True
    
    async def _batch_worker(self):
        from agent.purchase_agent import PurchaseAgent
        
        agent = PurchaseAgent(api_key=self.api_key, base_url=self.base_url)
        
        def progress_callback(completed, total, message=""):
            self._update_progress(completed, total, message)
        
        def log_callback(message):
            self._log(message)
        
        try:
            results = await agent.execute_batch_tasks(
                self._pending_tasks,
                progress_callback=progress_callback,
                log_callback=log_callback
            )
            
            self._completed_tasks = results
            
            success_count = sum(1 for r in results if r['status'] == 'success')
            self._log(f"所有任务执行完成: 成功 {success_count}/{len(results)} 个")
            
        except Exception as e:
            self._log(f"批量执行异常: {str(e)}")
        finally:
            await agent.stop()
    
    def pause(self):
        self._is_paused = True
        self._log("任务已暂停")
    
    def resume(self):
        self._is_paused = False
        self._log("任务已继续")
    
    def stop(self):
        self._is_running = False
        self._is_paused = False
        self._log("任务已停止")
    
    def is_running(self) -> bool:
        return self._is_running
    
    def is_paused(self) -> bool:
        return self._is_paused
    
    def get_progress(self) -> Dict:
        return {
            'completed': len(self._completed_tasks),
            'total': self._total_tasks,
            'active': self._active_tasks,
            'pending': len(self._pending_tasks)
        }
    
    def generate_report(self, output_dir: str = 'reports') -> Optional[str]:
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(output_dir, f'采购报告_{timestamp}.xlsx')
        
        processor = DataProcessor()
        success = processor.generate_report(self._completed_tasks, output_path)
        
        if success:
            self._log(f"采购报告已生成: {output_path}")
            return output_path
        else:
            self._log("生成采购报告失败")
            return None
    
    async def run_and_report(self, data_df: pd.DataFrame, report_dir: str = 'reports') -> Optional[str]:
        await self.start(data_df)
        return self.generate_report(report_dir)