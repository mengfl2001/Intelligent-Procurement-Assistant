import asyncio
import json
import logging
from typing import Dict, Optional, List, Tuple

from tools.browser_tools import BrowserTools
from core.api_client import api_client

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一个专业的1688电商采购智能体，负责在1688商品详情页完成采购任务。

## 工作模式

**主要工作由 fill_1688_sku_and_add_to_cart 工具完成**，你负责：
1. 确认页面已加载完成
2. 如果页面被重定向或有弹窗，先处理这些问题
3. 调用 fill_1688_sku_and_add_to_cart 工具完成选品和加购
4. 验证操作结果
5. 使用 finish 工具完成任务

## 工具说明

### fill_1688_sku_and_add_to_cart（核心工具）
直接操作 DOM 完成 1688 SKU 选择和加购，绕过视觉标注的不稳定性。
参数：
- color: 颜色（如"豹纹"、"黑色"）
- size: 尺码（如"37"、"XL"）
- quantity: 购买数量（整数）
- product_type: 商品类型/规格（可选）

## 操作流程

1. 等待页面完全加载
2. 检查页面是否正常显示商品详情
3. 如果页面有弹窗或提示，先关闭弹窗
4. 调用 fill_1688_sku_and_add_to_cart 工具
5. 验证加购是否成功
6. 使用 finish 工具完成任务

## 可用工具（请返回JSON格式）

1. {"tool": "fill_1688_sku_and_add_to_cart", "args": {"color": "颜色", "size": "尺码", "quantity": 数量, "product_type": "商品类型"}} - 直接操作DOM填写SKU并加购
2. {"tool": "click_element", "args": {"index": 元素索引}} - 点击指定索引的元素
3. {"tool": "input_text", "args": {"index": 元素索引, "text": "输入内容"}} - 在输入框中输入文本
4. {"tool": "scroll_down", "args": {"amount": 滚动像素}} - 向下滚动页面
5. {"tool": "scroll_up", "args": {"amount": 滚动像素}} - 向上滚动页面
6. {"tool": "wait", "args": {"seconds": 等待秒数}} - 等待页面加载
7. {"tool": "finish", "args": {"message": "完成说明"}} - 完成任务

只返回JSON格式，不要包含其他文字。"""


class PurchaseAgent:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.browser_tools = BrowserTools(headless=False)
        self.api_key = api_key
        self.base_url = base_url
        self.max_steps = 30
        self.current_step = 0
        self._llm_retry_count = 0
        self._max_llm_retries = 3
        self._is_running = True
        
        if api_key and base_url:
            api_client.set_config(api_key, base_url, "")
    
    async def _call_llm_with_retry(self, messages: List[Dict]) -> Optional[str]:
        for attempt in range(self._max_llm_retries):
            try:
                result = await api_client.chat_completion(messages)
                if result.get("success"):
                    self._llm_retry_count = 0
                    return result.get("content", "")
                else:
                    logger.warning(f"LLM调用失败 ({attempt+1}/{self._max_llm_retries}): {result.get('message', '')}")
            except Exception as e:
                logger.warning(f"LLM调用异常 ({attempt+1}/{self._max_llm_retries}): {str(e)}")
            
            await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def _parse_tool_call(self, llm_response: str) -> Optional[Dict]:
        try:
            if not llm_response:
                return None
            
            if "```json" in llm_response:
                start = llm_response.find("```json") + 7
                end = llm_response.find("```", start)
                if end == -1:
                    end = len(llm_response)
                json_str = llm_response[start:end].strip()
            elif "{" in llm_response:
                start = llm_response.find("{")
                end = llm_response.rfind("}") + 1
                json_str = llm_response[start:end]
            else:
                return None
            
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"解析工具调用失败: {str(e)}, 响应: {llm_response[:200]}")
            return None
    
    async def _execute_tool(self, tool_name: str, args: Dict) -> str:
        try:
            if tool_name == "fill_1688_sku_and_add_to_cart":
                color = args.get("color", "")
                size = args.get("size", "")
                quantity = int(args.get("quantity", 1))
                product_type = args.get("product_type", "")
                
                logger.info(f"调用 fill_1688_sku_and_add_to_cart: color={color}, size={size}, quantity={quantity}")
                success, msg = await self.browser_tools.fill_1688_sku_and_add_to_cart(
                    color=color,
                    size=size,
                    quantity=quantity,
                    product_type=product_type
                )
                return msg if success else f"失败: {msg}"
            
            elif tool_name == "click_element":
                index = args.get("index", 0)
                logger.info(f"点击元素: 索引 {index}")
                success, msg = await self.browser_tools.click_element(index)
                await asyncio.sleep(1.5)
                return msg if success else f"失败: {msg}"
            
            elif tool_name == "input_text":
                index = args.get("index", 0)
                text = args.get("text", "")
                logger.info(f"输入文本: '{text}' 到元素索引 {index}")
                success, msg = await self.browser_tools.input_text(index, text)
                await asyncio.sleep(0.5)
                return msg if success else f"失败: {msg}"
            
            elif tool_name == "scroll_down":
                amount = args.get("amount", 500)
                logger.info(f"向下滚动: {amount} 像素")
                success, msg = await self.browser_tools.scroll_down(amount)
                await asyncio.sleep(0.5)
                return msg
            
            elif tool_name == "scroll_up":
                amount = args.get("amount", 500)
                logger.info(f"向上滚动: {amount} 像素")
                success, msg = await self.browser_tools.scroll_up(amount)
                await asyncio.sleep(0.5)
                return msg
            
            elif tool_name == "wait":
                seconds = args.get("seconds", 3)
                logger.info(f"等待: {seconds} 秒")
                await asyncio.sleep(seconds)
                return f"已等待 {seconds} 秒"
            
            elif tool_name == "finish":
                return f"任务完成: {args.get('message', '')}"
            
            else:
                return f"未知工具: {tool_name}"
                
        except Exception as e:
            logger.error(f"工具执行失败: {str(e)}")
            return f"工具执行失败: {str(e)}"
    
    def _find_element_index(self, interactive_elements: str, target_text: str) -> Optional[int]:
        if not interactive_elements or not target_text:
            return None
        
        lines = interactive_elements.split('\n')
        exact_match = None
        partial_match = None
        
        for line in lines:
            if '[' in line and ']' in line:
                try:
                    start = line.index('[')
                    end = line.index(']')
                    index_str = line[start+1:end]
                    index = int(index_str)
                    
                    line_text = line[end+1:].strip()
                    
                    if target_text == line_text:
                        exact_match = index
                        break
                    
                    if target_text in line_text:
                        if partial_match is None:
                            partial_match = index
                            
                except (ValueError, IndexError):
                    continue
        
        return exact_match if exact_match is not None else partial_match
    
    def _find_size_plus_button(self, interactive_elements: str, size: str) -> Optional[int]:
        if not interactive_elements or not size:
            return None
        
        lines = interactive_elements.split('\n')
        size_index = None
        size_found = False
        
        for i, line in enumerate(lines):
            if '[' in line and ']' in line:
                try:
                    start = line.index('[')
                    end = line.index(']')
                    index_str = line[start+1:end]
                    index = int(index_str)
                    
                    line_text = line[end+1:].strip()
                    
                    if size_found:
                        if '+' in line_text or '加' in line_text:
                            return index
                    
                    if size in line_text:
                        size_index = index
                        size_found = True
                        
                except (ValueError, IndexError):
                    continue
        
        return size_index
    
    def _find_size_input_and_plus(self, interactive_elements: str, size: str) -> Tuple[Optional[int], Optional[int]]:
        """查找指定尺码行的输入框和加号按钮索引
        
        1688 SKU 结构：每个尺码行包含3个连续元素：减号、输入框、加号
        例如：尺码37行 = [59] 减号、[60] 输入框、[61] 加号
        
        Returns: (input_box_index, plus_button_index)
        """
        if not interactive_elements or not size:
            return None, None
        
        lines = interactive_elements.split('\n')
        elements = []
        
        for line in lines:
            if '[' in line and ']' in line:
                try:
                    start = line.index('[')
                    end = line.index(']')
                    index_str = line[start+1:end]
                    index = int(index_str)
                    line_text = line[end+1:].strip()
                    elements.append((index, line_text))
                except (ValueError, IndexError):
                    continue
        
        size_element_pos = -1
        for i, (index, text) in enumerate(elements):
            if size in text:
                size_element_pos = i
                break
        
        if size_element_pos == -1:
            return None, None
        
        input_box_index = None
        plus_button_index = None
        
        for i in range(size_element_pos, min(size_element_pos + 5, len(elements))):
            index, text = elements[i]
            if text in ['0', ''] or 'input' in text.lower():
                if input_box_index is None:
                    input_box_index = index
            elif '+' in text:
                if plus_button_index is None:
                    plus_button_index = index
        
        return input_box_index, plus_button_index
    
    async def _auto_select_options(self, browser_state: Dict, color: str, size: str, product_type: str = "", quantity: int = 1) -> List[str]:
        results = []
        interactive_elements = browser_state.get("interactive_elements", "")
        
        if product_type:
            type_index = self._find_element_index(interactive_elements, product_type)
            if type_index is not None:
                logger.info(f"自动选择商品类型 '{product_type}'，元素索引: {type_index}")
                success, msg = await self.browser_tools.click_element(type_index)
                if success:
                    results.append(f"已选择商品类型: {product_type}")
                    await asyncio.sleep(1)
                else:
                    results.append(f"选择商品类型失败: {msg}")
            else:
                logger.warning(f"未找到商品类型 '{product_type}' 的元素")
        
        if color:
            color_index = self._find_element_index(interactive_elements, color)
            if color_index is not None:
                logger.info(f"自动选择颜色 '{color}'，元素索引: {color_index}")
                success, msg = await self.browser_tools.click_element(color_index)
                if success:
                    results.append(f"已选择颜色: {color}")
                    await asyncio.sleep(1)
                else:
                    results.append(f"选择颜色失败: {msg}")
            else:
                logger.warning(f"未找到颜色 '{color}' 的元素")
        
        if size:
            logger.info(f"查找尺码 '{size}' 对应的输入框和+按钮...")
            
            input_index, plus_index = self._find_size_input_and_plus(interactive_elements, size)
            
            if input_index is not None:
                logger.info(f"找到尺码 '{size}' 的输入框，元素索引: {input_index}")
                
                logger.info(f"点击输入框以激活...")
                success, msg = await self.browser_tools.click_element(input_index)
                if success:
                    await asyncio.sleep(0.5)
                    
                    logger.info(f"在输入框中输入数量: {quantity}")
                    success, msg = await self.browser_tools.input_text(input_index, str(quantity))
                    if success:
                        results.append(f"已设置尺码 '{size}' 数量为 {quantity}")
                        await asyncio.sleep(1)
                    else:
                        logger.warning(f"输入数量失败: {msg}，尝试使用+按钮")
                        if plus_index is not None:
                            logger.info(f"使用+按钮设置数量，元素索引: {plus_index}，点击 {quantity} 次")
                            for i in range(quantity):
                                await self.browser_tools.click_element(plus_index)
                                await asyncio.sleep(0.3)
                            results.append(f"已通过+按钮设置尺码 '{size}' 数量为 {quantity}")
                else:
                    logger.warning(f"点击输入框失败: {msg}，尝试使用+按钮")
                    if plus_index is not None:
                        logger.info(f"使用+按钮设置数量，元素索引: {plus_index}，点击 {quantity} 次")
                        for i in range(quantity):
                            await self.browser_tools.click_element(plus_index)
                            await asyncio.sleep(0.3)
                        results.append(f"已通过+按钮设置尺码 '{size}' 数量为 {quantity}")
            elif plus_index is not None:
                logger.info(f"未找到输入框，使用+按钮设置尺码 '{size}' 数量，元素索引: {plus_index}")
                for i in range(quantity):
                    await self.browser_tools.click_element(plus_index)
                    await asyncio.sleep(0.3)
                results.append(f"已通过+按钮设置尺码 '{size}' 数量为 {quantity}")
            else:
                logger.warning(f"未找到尺码 '{size}' 的输入框或+按钮，尝试旧逻辑...")
                
                size_plus_index = self._find_size_plus_button(interactive_elements, size)
                if size_plus_index is not None:
                    logger.info(f"找到尺码 '{size}' 的+按钮，元素索引: {size_plus_index}")
                    success, msg = await self.browser_tools.click_element(size_plus_index)
                    if success:
                        results.append(f"已选择尺码 '{size}' 并添加到采购车")
                        await asyncio.sleep(1)
                    else:
                        results.append(f"选择尺码失败: {msg}")
                else:
                    size_index = self._find_element_index(interactive_elements, size)
                    if size_index is not None:
                        logger.info(f"找到尺码 '{size}'，元素索引: {size_index}")
                        success, msg = await self.browser_tools.click_element(size_index)
                        if success:
                            results.append(f"已选择尺码: {size}")
                            await asyncio.sleep(1)
                        else:
                            results.append(f"选择尺码失败: {msg}")
                    else:
                        logger.warning(f"未找到尺码 '{size}' 的元素")
        
        return results
    
    async def execute_purchase_task(
        self, 
        url: str, 
        item_name: str, 
        quantity: int = 1,
        color: str = "",
        size: str = "",
        product_type: str = ""
    ) -> Dict[str, str]:
        screenshot_path = ""
        
        try:
            logger.info(f"===== 开始执行采购任务 =====")
            logger.info(f"URL: {url}")
            logger.info(f"商品名称: {item_name}")
            logger.info(f"数量: {quantity}")
            logger.info(f"颜色: {color if color else '未指定'}")
            logger.info(f"尺码: {size if size else '未指定'}")
            
            logger.info("导航到目标页面...")
            await self.browser_tools.navigate(url)
            logger.info("页面导航完成，等待3秒...")
            await asyncio.sleep(3)
            
            page = await self.browser_tools._context.get_current_page()
            current_url = page.url
            logger.info(f"当前页面URL: {current_url}")
            
            if "notfound" in current_url or current_url.startswith("https://www.1688.com/"):
                logger.warning(f"页面被重定向到: {current_url}")
                logger.info("尝试重新导航...")
                await asyncio.sleep(2)
                await self.browser_tools.navigate(url)
                await asyncio.sleep(3)
                current_url = page.url
                logger.info(f"重新导航后URL: {current_url}")
            
            logger.info("立即绘制元素标注...")
            success, elements_str = await self.browser_tools.highlight_elements()
            logger.info(f"元素标注结果: success={success}, 元素数量={elements_str.count('[') if elements_str else 0}")
            
            logger.info("========== 方案一：直接 DOM 操作 ==========")
            dom_success, dom_msg = await self.browser_tools.fill_1688_sku_and_add_to_cart(
                color=color,
                size=size,
                quantity=quantity,
                product_type=product_type
            )
            
            logger.info(f"DOM操作结果: success={dom_success}, msg={dom_msg}")
            
            if dom_success and ("加采购车" in dom_msg or "加入购物车" in dom_msg):
                logger.info("DOM 操作成功，任务完成")
                screenshot_path = await self.browser_tools.capture_screenshot()
                return {
                    'status': 'success',
                    'message': f"DOM操作成功: {dom_msg}",
                    'screenshot_path': screenshot_path,
                    'steps': 1
                }
            
            logger.warning("DOM 操作未完全成功，转入 LLM Agent 兜底方案")
            
            logger.info("开始获取浏览器状态...")
            success, browser_state = await self.browser_tools.get_browser_state()
            logger.info(f"获取浏览器状态结果: success={success}")
            
            if not success or not browser_state:
                error_msg = browser_state.get('error', '未知错误') if isinstance(browser_state, dict) else str(browser_state)
                logger.error(f"获取浏览器状态失败: {error_msg}")
                screenshot_path = await self.browser_tools.capture_screenshot()
                return {
                    'status': 'failed',
                    'message': f'获取浏览器状态失败: {error_msg}',
                    'screenshot_path': screenshot_path,
                    'steps': 0
                }
            
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"""
采购任务：
- 目标网站: {url}
- 商品名称: {item_name}
- 购买数量: {quantity}
- 颜色: {color if color else '未指定'}
- 尺码: {size if size else '未指定'}
- 商品类型: {product_type if product_type else '未指定'}

重要说明：
- 方案一（DOM 操作）已执行，结果: {dom_msg}
- 如果 DOM 操作已成功添加到采购车，请直接使用 finish 工具完成任务
- 如果 DOM 操作部分失败，请：
  1. 检查页面状态，确认哪些步骤已完成
  2. 使用 fill_1688_sku_and_add_to_cart 工具重试
  3. 或者使用其他工具手动操作剩余步骤
  4. 最后确认加入采购车

请执行以下步骤：
1. 检查当前页面状态
2. 完成剩余的采购操作
3. 使用finish工具完成任务

当前页面状态：
URL: {browser_state.get('url', '')}
标题: {browser_state.get('title', '')}

可交互元素列表：
{browser_state.get('interactive_elements', '')}

请根据以上信息决定下一步操作。"""}
            ]
            
            self.current_step = 0
            
            while self.current_step < self.max_steps:
                logger.info(f"=== 第 {self.current_step + 1}/{self.max_steps} 步 ===")
                
                llm_response = await self._call_llm_with_retry(messages)
                
                if not llm_response:
                    logger.error("LLM调用失败，跳过此步")
                    self.current_step += 1
                    await asyncio.sleep(1)
                    continue
                
                logger.debug(f"LLM响应: {llm_response[:300]}")
                
                tool_call = self._parse_tool_call(llm_response)
                
                if not tool_call:
                    logger.warning("无法解析LLM响应，跳过此步")
                    messages.append({"role": "user", "content": "无法解析您的响应，请只返回JSON格式的工具调用"})
                    self.current_step += 1
                    await asyncio.sleep(1)
                    continue
                
                tool_name = tool_call.get("tool", "")
                args = tool_call.get("args", {})
                
                if tool_name == "finish":
                    result_msg = args.get("message", "")
                    screenshot_path = await self.browser_tools.capture_screenshot()
                    logger.info(f"任务完成: {result_msg}")
                    
                    return {
                        'status': 'success',
                        'message': result_msg,
                        'screenshot_path': screenshot_path,
                        'steps': self.current_step + 1
                    }
                
                result = await self._execute_tool(tool_name, args)
                
                messages.append({
                    "role": "assistant",
                    "content": json.dumps(tool_call, ensure_ascii=False)
                })
                messages.append({"role": "user", "content": f"工具执行结果: {result}"})
                
                success, browser_state = await self.browser_tools.get_browser_state()
                if success and browser_state:
                    messages.append({"role": "user", "content": f"""
当前页面状态：
URL: {browser_state.get('url', '')}
标题: {browser_state.get('title', '')}

可交互元素列表：
{browser_state.get('interactive_elements', '')}

请根据以上信息决定下一步操作。"""})
                
                self.current_step += 1
                
                await asyncio.sleep(0.5)
            
            screenshot_path = await self.browser_tools.capture_screenshot()
            logger.warning(f"任务未完成，已执行 {self.current_step}/{self.max_steps} 步")
            
            return {
                'status': 'failed',
                'message': f'任务未完成，已执行 {self.current_step}/{self.max_steps} 步',
                'screenshot_path': screenshot_path,
                'steps': self.current_step
            }
        
        except Exception as e:
            screenshot_path = await self.browser_tools.capture_screenshot()
            logger.error(f"采购任务异常: {str(e)}")
            
            return {
                'status': 'failed',
                'message': str(e),
                'screenshot_path': screenshot_path,
                'steps': self.current_step
            }
    
    async def stop(self):
        self._is_running = False
        logger.info("收到停止信号，清理浏览器资源")
        await self.browser_tools.cleanup()
    
    async def execute_batch_tasks(self, tasks: List[Dict], progress_callback=None, log_callback=None) -> List[Dict]:
        results = []
        total = len(tasks)
        
        logger.info(f"===== 开始批量采购任务，共 {total} 个商品 =====")
        
        for idx, task in enumerate(tasks):
            if not self._is_running:
                logger.info("任务已停止，退出批量执行")
                break
            
            task_id = idx + 1
            url = task.get('url', '')
            item_name = task.get('item_name', '')
            quantity = task.get('quantity', 1)
            color = task.get('color', '')
            size = task.get('size', '')
            product_type = task.get('product_type', '')
            
            if log_callback:
                log_callback(f"[{task_id}/{total}] 开始处理: {item_name}")
            else:
                logger.info(f"[{task_id}/{total}] 开始处理: {item_name}")
            
            if progress_callback:
                progress_callback(idx, total, f"正在处理第 {task_id}/{total} 个: {item_name}")
            
            result = {
                'id': task_id,
                'url': url,
                'item_name': item_name,
                'quantity': quantity,
                'color': color,
                'size': size,
                'product_type': product_type,
                'status': 'failed',
                'message': '',
                'screenshot_path': '',
                'steps': 0
            }
            
            try:
                logger.info(f"导航到商品页面: {url}")
                await self.browser_tools.navigate(url)
                await asyncio.sleep(3)
                
                page = await self.browser_tools._context.get_current_page()
                current_url = page.url
                
                if "notfound" in current_url or current_url.startswith("https://www.1688.com/"):
                    logger.warning(f"页面被重定向，尝试重新导航...")
                    await asyncio.sleep(2)
                    await self.browser_tools.navigate(url)
                    await asyncio.sleep(3)
                
                logger.info("绘制元素标注...")
                success, elements_str = await self.browser_tools.highlight_elements()
                
                logger.info("执行 DOM 操作（选择SKU并加购）...")
                dom_success, dom_msg = await self.browser_tools.fill_1688_sku_and_add_to_cart(
                    color=color,
                    size=size,
                    quantity=quantity,
                    product_type=product_type
                )
                
                logger.info(f"DOM操作结果: success={dom_success}, msg={dom_msg}")
                
                is_success = False
                if '规格选择失败' in dom_msg or '坐标处无元素' in dom_msg:
                    is_success = False
                elif '加采购车' in dom_msg and ('文本查找' in dom_msg or '全局查找' in dom_msg):
                    is_success = True
                
                screenshot_path = await self.browser_tools.capture_screenshot()
                result['screenshot_path'] = screenshot_path
                result['message'] = dom_msg
                result['steps'] = 1
                
                if is_success:
                    result['status'] = 'success'
                    if log_callback:
                        log_callback(f"[✓] 任务 {task_id}/{total} 成功: {item_name}")
                    else:
                        logger.info(f"[✓] 任务 {task_id}/{total} 成功: {item_name}")
                else:
                    result['status'] = 'failed'
                    if log_callback:
                        log_callback(f"[✗] 任务 {task_id}/{total} 失败: {item_name} - {dom_msg}")
                    else:
                        logger.warning(f"[✗] 任务 {task_id}/{total} 失败: {item_name} - {dom_msg}")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                screenshot_path = await self.browser_tools.capture_screenshot()
                result['screenshot_path'] = screenshot_path
                result['message'] = str(e)
                
                if log_callback:
                    log_callback(f"[✗] 任务 {task_id}/{total} 异常: {item_name} - {str(e)}")
                else:
                    logger.error(f"[✗] 任务 {task_id}/{total} 异常: {item_name} - {str(e)}")
            
            results.append(result)
            
            if progress_callback:
                progress_callback(idx + 1, total, f"已完成 {task_id}/{total} 个")
        
        logger.info(f"===== 批量采购任务完成，成功 {sum(1 for r in results if r['status']=='success')}/{total} 个 =====")
        
        return results