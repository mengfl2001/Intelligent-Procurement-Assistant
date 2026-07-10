import asyncio
import base64
import os
import json
import logging
import ctypes
from datetime import datetime
from typing import Optional, Dict, Tuple

from browser_use import Browser as BrowserUseBrowser
from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.dom.service import DomService

logger = logging.getLogger(__name__)


def get_screen_resolution():
    try:
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        logger.info(f"检测到屏幕分辨率: {width}x{height}")
        return width, height
    except Exception as e:
        logger.warning(f"获取屏幕分辨率失败: {str(e)}，使用默认值")
        return 1920, 1080


class BrowserTools:
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls, headless: bool = False):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance.headless = headless
            cls._instance._browser = None
            cls._instance._context = None
            cls._instance._dom_service = None
            cls._instance._element_list = []
        return cls._instance
    
    async def _ensure_initialized(self):
        async with self._lock:
            if self._initialized:
                return
            
            logger.info("初始化浏览器...")
            
            screen_width, screen_height = get_screen_resolution()
            
            window_width = screen_width - 40
            window_height = screen_height - 120
            
            if window_width < 1280:
                window_width = 1280
            if window_height < 800:
                window_height = 800
            
            self._browser = BrowserUseBrowser(BrowserConfig(headless=self.headless))
            self._context = await self._browser.new_context(BrowserContextConfig(
                highlight_elements=False,
                browser_window_size={"width": window_width, "height": window_height}
            ))
            page = await self._context.get_current_page()
            await page.set_viewport_size({"width": window_width, "height": window_height})
            self._dom_service = DomService(page)
            self._initialized = True
            logger.info(f"浏览器初始化完成，窗口大小: {window_width}x{window_height}，元素标注已启用")
    
    def is_initialized(self) -> bool:
        return self._initialized
    
    async def navigate(self, url: str, highlight: bool = True):
        await self._ensure_initialized()
        
        logger.info(f"导航到 URL: {url}")
        
        page = await self._context.get_current_page()
        await page.goto(url)
        await page.wait_for_load_state()
        
        logger.info("页面加载完成")
        
        if highlight:
            await self.highlight_elements()
        else:
            logger.info("页面加载完成，不绘制元素标注")
    
    async def highlight_elements(self) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            logger.info("绘制右侧SKU区域元素标注...")
            
            page = await self._context.get_current_page()
            
            await page.evaluate("""
                    let container = document.getElementById('playwright-highlight-container');
                    if (container) {
                        container.remove();
                    }
                    
                    container = document.createElement("div");
                    container.id = "playwright-highlight-container";
                    container.style.position = "fixed";
                    container.style.pointerEvents = "none";
                    container.style.top = "0";
                    container.style.left = "0";
                    container.style.width = "100%";
                    container.style.height = "100%";
                    container.style.zIndex = "2147483647";
                    document.body.appendChild(container);
                    
                    const colors = ['#FF0000', '#00FF00', '#0000FF', '#FFA500', '#800080', '#008080', '#FF69B4', '#4B0082', '#FF4500', '#2E8B57'];
                    const labels = [];
                    
                    const sizeKeywords = ['35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45', 'S', 'M', 'L', 'XL', 'XXL'];
                    const colorKeywords = ['颜色', '黑色', '白色', '红色', '蓝色', '绿色', '黄色', '粉色', '紫色', '灰色', '棕色', '米色', '豹纹'];
                    const actionKeywords = ['加采购车', '立即下单', '+', '加入购物车'];
                    const skuKeywords = ['sku', 'spec', 'option', 'color', 'size', 'quantity', 'num', 'count'];
                    const inputKeywords = ['数量', '购买数量', '采购数量'];
                    
                    const allElements = document.querySelectorAll('a, button, input, select, textarea, div, span, [role="button"], [role="link"], [onclick], [tabindex]:not([tabindex="-1"])');
                    
                    allElements.forEach((element, globalIndex) => {
                        try {
                            const rect = element.getBoundingClientRect();
                            if (rect.width < 8 || rect.height < 8) return;
                            if (rect.top < -100 || rect.top > window.innerHeight + 100) return;
                            
                            if (rect.left < window.innerWidth / 2) return;
                            
                            const text = (element.textContent || '').trim();
                            const className = element.className || '';
                            const tagName = element.tagName.toLowerCase();
                            
                            let isTarget = false;
                            let labelType = '';
                            
                            if (tagName === 'input') {
                                const type = element.type || '';
                                const placeholder = element.placeholder || '';
                                const value = (element.value || '').toString();
                                
                                if (type === 'text' || type === 'number' || type === '') {
                                    if (placeholder.includes('数量') || placeholder.includes('购买') || 
                                        value === '0' || value === '' || 
                                        className.includes('quantity') || className.includes('num')) {
                                        isTarget = true;
                                        labelType = '输入框';
                                    }
                                }
                            }
                            
                            if (!isTarget) {
                                for (const kw of sizeKeywords) {
                                    if (text === kw || text === kw + '码') {
                                        const parentClass = (element.parentElement || {}).className || '';
                                        const grandParentClass = ((element.parentElement || {}).parentElement || {}).className || '';
                                        if (parentClass.includes('sku') || parentClass.includes('spec') || 
                                            className.includes('sku') || className.includes('spec') ||
                                            parentClass.includes('size') || className.includes('size') ||
                                            grandParentClass.includes('sku') || grandParentClass.includes('spec') ||
                                            grandParentClass.includes('size') || grandParentClass.includes('prop') ||
                                            grandParentClass.includes('item')) {
                                            isTarget = true;
                                            labelType = '尺码';
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            if (!isTarget) {
                                for (const kw of colorKeywords) {
                                    if (text === kw) {
                                        const parentClass = (element.parentElement || {}).className || '';
                                        const grandParentClass = ((element.parentElement || {}).parentElement || {}).className || '';
                                        if (parentClass.includes('color') || className.includes('color') ||
                                            parentClass.includes('sku') || className.includes('sku') ||
                                            grandParentClass.includes('sku') || grandParentClass.includes('color') ||
                                            grandParentClass.includes('prop') || grandParentClass.includes('item')) {
                                            isTarget = true;
                                            labelType = '颜色';
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            if (!isTarget) {
                                for (const kw of actionKeywords) {
                                    if (text.includes(kw) || className.includes(kw)) {
                                        isTarget = true;
                                        labelType = '操作';
                                        break;
                                    }
                                }
                            }
                            
                            if (!isTarget) {
                                for (const kw of inputKeywords) {
                                    if (text.includes(kw)) {
                                        isTarget = true;
                                        labelType = '输入框';
                                        break;
                                    }
                                }
                            }
                            
                            if (!isTarget) {
                                if (element.tagName === 'BUTTON' || 
                                    element.getAttribute('role') === 'button' ||
                                    className.includes('btn') || 
                                    className.includes('button') ||
                                    className.includes('add') ||
                                    className.includes('cart') ||
                                    className.includes('buy')) {
                                    isTarget = true;
                                    labelType = '按钮';
                                }
                            }
                            
                            if (!isTarget) {
                                if (text.length > 0 && text.length <= 8 && !text.includes('￥')) {
                                    let hasSkuClass = false;
                                    for (const kw of skuKeywords) {
                                        if (className.includes(kw) || (element.parentElement || {}).className.includes(kw)) {
                                            hasSkuClass = true;
                                            break;
                                        }
                                    }
                                    if (hasSkuClass) {
                                        isTarget = true;
                                        labelType = '规格';
                                    }
                                }
                            }
                            
                            if (!isTarget) {
                                const parentClass = (element.parentElement || {}).className || '';
                                const grandParentClass = ((element.parentElement || {}).parentElement || {}).className || '';
                                for (const kw of skuKeywords) {
                                    if (className.includes(kw) || parentClass.includes(kw) || grandParentClass.includes(kw)) {
                                        if (text.length > 0 && text.length <= 15) {
                                            isTarget = true;
                                            labelType = '规格';
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            if (isTarget) {
                                const color = colors[labels.length % colors.length];
                                
                                const overlay = document.createElement("div");
                                overlay.style.position = "fixed";
                                overlay.style.border = "2px solid " + color;
                                overlay.style.backgroundColor = color + "1A";
                                overlay.style.pointerEvents = "none";
                                overlay.style.top = rect.top + "px";
                                overlay.style.left = rect.left + "px";
                                overlay.style.width = rect.width + "px";
                                overlay.style.height = rect.height + "px";
                                overlay.style.zIndex = "2147483646";
                                overlay.setAttribute('data-index', labels.length);
                                container.appendChild(overlay);
                                
                                const label = document.createElement("div");
                                label.style.position = "fixed";
                                label.style.background = color;
                                label.style.color = "white";
                                label.style.padding = "2px 6px";
                                label.style.borderRadius = "4px";
                                label.style.fontSize = "11px";
                                label.style.fontWeight = "bold";
                                label.style.top = rect.top + "px";
                                label.style.left = rect.left + "px";
                                label.style.zIndex = "2147483647";
                                label.style.whiteSpace = "nowrap";
                                label.textContent = "[" + labels.length + "] " + text.substring(0, 10);
                                container.appendChild(label);
                                
                                labels.push({
                                    index: labels.length,
                                    text: text,
                                    type: labelType,
                                    top: rect.top
                                });
                            }
                        } catch (e) {
                            console.log("标注元素失败: ", e);
                        }
                    });
                    
                    window._sku_elements = labels;
                    console.log("绘制了 " + labels.length + " 个SKU区域元素标注");
                """)
                
            await asyncio.sleep(0.5)
            
            element_data = await page.evaluate("window._sku_elements || []")
            self._element_list = element_data if isinstance(element_data, list) else []
            
            elements_str = ""
            for i, el in enumerate(self._element_list):
                elements_str += f"[{i}] {el.get('type', '')}: {el.get('text', '')[:20]}\n"
            
            logger.info(f"标注了 {len(self._element_list)} 个右侧SKU区域元素")
            
            return True, elements_str
            
        except Exception as e:
            logger.error(f"绘制元素标注失败: {str(e)}", exc_info=True)
            return False, str(e)
    
    async def click_element(self, index: int) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            logger.info(f"点击元素索引 {index}")
            
            element = await self._context.get_dom_element_by_index(index)
            if not element:
                logger.error(f"元素索引 {index} 未找到")
                return False, f"Element with index {index} not found"
            
            download_path = await self._context._click_element_node(element)
            output = f"Clicked element at index {index}"
            if download_path:
                output += f" - Downloaded file to {download_path}"
            
            await asyncio.sleep(1)
            
            await self.highlight_elements()
            
            return True, output
            
        except Exception as e:
            logger.error(f"点击失败: {str(e)}", exc_info=True)
            return False, f"Click failed: {str(e)}"
    
    async def input_text(self, index: int, text: str) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            logger.info(f"输入文本 '{text}' 到元素索引 {index}")
            
            element = await self._context.get_dom_element_by_index(index)
            if not element:
                logger.error(f"元素索引 {index} 未找到")
                return False, f"Element with index {index} not found"
            
            await self._context._input_text_element_node(element, text)
            
            await asyncio.sleep(0.5)
            
            await self.highlight_elements()
            
            return True, f"Input '{text}' into element at index {index}"
            
        except Exception as e:
            logger.error(f"输入失败: {str(e)}", exc_info=True)
            return False, f"Input failed: {str(e)}"
    
    async def click_element_by_index(self, index: int) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            if not self._element_list or index >= len(self._element_list):
                return False, f"元素索引越界: {index}，共有 {len(self._element_list)} 个元素"
            
            element_info = self._element_list[index]
            element_text = element_info.get('text', '')
            element_type = element_info.get('type', '')
            
            logger.info(f"点击元素[{index}]: {element_type} - {element_text[:30]}")
            
            page = await self._context.get_current_page()
            
            result = await page.evaluate("""
                ({index, text, type}) => {
                    const container = document.getElementById('playwright-highlight-container');
                    if (!container) return {success: false, error: '标注容器不存在'};
                    
                    const overlay = container.querySelector(`[data-index="${index}"]`);
                    if (!overlay) return {success: false, error: '找不到标注元素'};
                    
                    const top = parseFloat(overlay.style.top);
                    const left = parseFloat(overlay.style.left);
                    const width = parseFloat(overlay.style.width);
                    const height = parseFloat(overlay.style.height);
                    
                    const centerX = left + width / 2;
                    const centerY = top + height / 2;
                    
                    const target = document.elementFromPoint(centerX, centerY);
                    if (!target) return {success: false, error: '坐标处无元素'};
                    
                    try {
                        target.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window, clientX: centerX, clientY: centerY}));
                        target.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window, clientX: centerX, clientY: centerY}));
                        target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window, clientX: centerX, clientY: centerY}));
                        return {success: true, text: target.textContent || ''};
                    } catch(e) {
                        return {success: false, error: e.message};
                    }
                }
            """, {
                "index": index,
                "text": element_text,
                "type": element_type
            })
            
            if result and result.get('success'):
                logger.info(f"  点击成功: {result.get('text', '')[:30]}")
                return True, f"点击成功: {element_type} [{element_text[:20]}]"
            else:
                logger.warning(f"  点击失败: {result.get('error', '未知错误')}")
                return False, f"点击失败: {result.get('error', '未知错误')}"
                
        except Exception as e:
            logger.error(f"点击元素失败: {str(e)}", exc_info=True)
            return False, str(e)
    
    async def find_element_index(self, text: str, element_type: str = "") -> int:
        await self._ensure_initialized()
        try:
            if not self._element_list:
                return -1
            
            for i, el in enumerate(self._element_list):
                el_text = el.get('text', '')
                el_type = el.get('type', '')
                
                if element_type and el_type != element_type:
                    continue
                    
                if el_text == text or el_text == text + '码':
                    return i
                    
            for i, el in enumerate(self._element_list):
                el_text = el.get('text', '')
                el_type = el.get('type', '')
                
                if element_type and el_type != element_type:
                    continue
                    
                if text in el_text:
                    return i
                    
            return -1
        except Exception as e:
            logger.error(f"查找元素索引失败: {str(e)}")
            return -1
    
    async def input_text_by_index(self, index: int, text: str) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            if not self._element_list or index >= len(self._element_list):
                return False, f"元素索引越界: {index}"
            
            element_info = self._element_list[index]
            element_type = element_info.get('type', '')
            
            logger.info(f"输入文本到元素[{index}]: {element_type} - 文本: {text}")
            
            page = await self._context.get_current_page()
            
            result = await page.evaluate("""
                ({index, text}) => {
                    const container = document.getElementById('playwright-highlight-container');
                    if (!container) return {success: false, error: '标注容器不存在'};
                    
                    const overlay = container.querySelector(`[data-index="${index}"]`);
                    if (!overlay) return {success: false, error: '找不到标注元素'};
                    
                    const top = parseFloat(overlay.style.top);
                    const left = parseFloat(overlay.style.left);
                    const width = parseFloat(overlay.style.width);
                    const height = parseFloat(overlay.style.height);
                    
                    const centerX = left + width / 2;
                    const centerY = top + height / 2;
                    
                    const target = document.elementFromPoint(centerX, centerY);
                    if (!target) return {success: false, error: '坐标处无元素'};
                    
                    try {
                        target.focus();
                        
                        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                            if (nativeInputValueSetter) {
                                nativeInputValueSetter.set.call(target, text);
                            }
                            target.dispatchEvent(new Event('input', {bubbles: true}));
                            target.dispatchEvent(new Event('change', {bubbles: true}));
                        }
                        
                        return {success: true};
                    } catch(e) {
                        return {success: false, error: e.message};
                    }
                }
            """, {
                "index": index,
                "text": text
            })
            
            if result and result.get('success'):
                logger.info(f"  输入成功")
                return True, f"输入成功: {text}"
            else:
                logger.warning(f"  输入失败: {result.get('error', '未知错误')}")
                return False, f"输入失败: {result.get('error', '未知错误')}"
                
        except Exception as e:
            logger.error(f"输入文本失败: {str(e)}", exc_info=True)
            return False, str(e)
    
    async def scroll_down(self, amount: int = 500) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            logger.info(f"向下滚动 {amount} 像素")
            
            await self._context.execute_javascript(
                f"window.scrollBy(0, {amount});"
            )
            
            await asyncio.sleep(0.5)
            
            await self.highlight_elements()
            
            return True, f"Scrolled down by {amount} pixels"
            
        except Exception as e:
            logger.error(f"滚动失败: {str(e)}", exc_info=True)
            return False, f"Scroll failed: {str(e)}"
    
    async def scroll_up(self, amount: int = 500) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            logger.info(f"向上滚动 {amount} 像素")
            
            await self._context.execute_javascript(
                f"window.scrollBy(0, -{amount});"
            )
            
            await asyncio.sleep(0.5)
            
            await self.highlight_elements()
            
            return True, f"Scrolled up by {amount} pixels"
            
        except Exception as e:
            logger.error(f"滚动失败: {str(e)}", exc_info=True)
            return False, f"Scroll failed: {str(e)}"
    
    async def refresh(self) -> Tuple[bool, str]:
        await self._ensure_initialized()
        try:
            logger.info("刷新页面")
            
            await self._context.refresh_page()
            
            await asyncio.sleep(2)
            
            await self.highlight_elements()
            
            return True, "Page refreshed"
            
        except Exception as e:
            logger.error(f"刷新失败: {str(e)}", exc_info=True)
            return False, f"Refresh failed: {str(e)}"
    
    async def wait(self, seconds: int = 3):
        logger.info(f"等待 {seconds} 秒")
        await asyncio.sleep(seconds)
    
    async def get_browser_state(self, timeout: int = 60) -> Tuple[bool, Dict]:
        await self._ensure_initialized()
        
        try:
            async with asyncio.timeout(timeout):
                logger.info("========== 获取浏览器状态开始 ==========")
                
                logger.info("步骤1: 获取浏览器状态...")
                state = await self._context.get_state()
                
                page = await self._context.get_current_page()
                await page.bring_to_front()
                await page.wait_for_load_state()
                
                url = state.url
                title = state.title
                logger.info(f"页面URL: {url}")
                logger.info(f"页面标题: {title}")
                
                logger.info("步骤2: 获取可交互元素列表...")
                interactive_elements_str = (
                    state.element_tree.clickable_elements_to_string()
                    if state.element_tree
                    else ""
                )
                element_count = interactive_elements_str.count("[") if interactive_elements_str else 0
                logger.info(f"元素数量: {element_count}")
                
                if element_count > 0:
                    lines = interactive_elements_str.split("\n")
                    logger.info(f"========== 元素列表 (共{len(lines)}个) ==========")
                    for i, line in enumerate(lines[:20]):
                        if line.strip():
                            logger.info(f"  {line.strip()}")
                    if len(lines) > 20:
                        logger.info(f"  ... 还有 {len(lines)-20} 个元素")
                    logger.info("========== 元素列表结束 ==========")
                
                logger.info("步骤3: 检查标注容器是否存在...")
                has_highlight = await page.evaluate(
                    "document.getElementById('playwright-highlight-container') !== null"
                )
                logger.info(f"标注容器存在: {has_highlight}")
                
                logger.info("步骤4: 截图...")
                screenshot = await page.screenshot(
                    full_page=False, animations="disabled", type="jpeg", quality=80
                )
                screenshot_base64 = base64.b64encode(screenshot).decode("utf-8")
                
                viewport_height = 0
                if hasattr(self._context, "config") and hasattr(self._context.config, "browser_window_size"):
                    viewport_height = self._context.config.browser_window_size.get("height", 0)
                
                state_info = {
                    "url": url,
                    "title": title,
                    "screenshot": screenshot_base64,
                    "interactive_elements": interactive_elements_str,
                    "element_count": element_count,
                    "viewport_height": viewport_height,
                    "help": "[0], [1], [2], etc., represent clickable indices corresponding to the elements listed.",
                    "has_highlight": has_highlight
                }
                
                logger.info("========== 获取浏览器状态完成 ==========")
                
                return True, state_info
                
        except asyncio.TimeoutError:
            logger.error("获取浏览器状态超时")
            return False, {"error": "获取浏览器状态超时"}
        except Exception as e:
            logger.error(f"获取浏览器状态失败: {str(e)}", exc_info=True)
            return False, {"error": str(e)}
    
    async def capture_screenshot(self) -> str:
        await self._ensure_initialized()
        
        try:
            page = await self._context.get_current_page()
            await page.bring_to_front()
            
            screenshot_dir = "logs/screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(screenshot_dir, f"screenshot_{timestamp}.png")
            
            screenshot = await page.screenshot(
                full_page=True, type="png"
            )
            
            with open(screenshot_path, "wb") as f:
                f.write(screenshot)
            
            logger.info(f"截图已保存到: {screenshot_path}")
            
            return screenshot_path
            
        except Exception as e:
            logger.error(f"截图失败: {str(e)}", exc_info=True)
            return ""
    
    async def _select_1688_size_by_row(self, page, target_size: str) -> bool:
        """
        针对 1688 截图结构的专用尺码选择器
        特征：尺码行包含 [尺码数字] [价格] [库存]
        策略：定位"尺码"标题 → 找SKU容器 → 找目标尺码文本 → 向上找包含"库存"的行 → 点击该行
        重点：只在右侧区域查找，避免触发左侧图片跳转
        """
        import re
        try:
            logger.info(f"  [尺码选择] 步骤1: 定位'尺码'标题")
            title_locator = page.get_by_text("尺码", exact=True).first
            if await title_locator.count() == 0:
                logger.info(f"  未找到精确'尺码'标题，尝试模糊查找")
                for kw in ["鞋码", "码数", "规格", "尺寸"]:
                    title_locator = page.get_by_text(kw, exact=False).first
                    if await title_locator.count() > 0:
                        logger.info(f"  找到关键词: '{kw}'")
                        break
                else:
                    logger.warning("未找到任何尺码相关标题")
                    return False

            logger.info(f"  [尺码选择] 步骤2: 向上查找SKU容器")
            container = title_locator.locator(
                "xpath=ancestor::div[contains(@class, 'prop') or contains(@class, 'sku') or contains(@class, 'obj') or contains(@class, 'item')][1]"
            )
            if await container.count() == 0:
                logger.info(f"  未找到class容器，使用父级的父级")
                container = title_locator.locator("xpath=../..")

            if await container.count() == 0:
                logger.warning("无法定位SKU容器")
                return False

            logger.info(f"  [尺码选择] 步骤3: 在容器内查找尺码文本 '{target_size}'")
            target_text_locator = container.get_by_text(target_size, exact=True).first

            if await target_text_locator.count() == 0:
                logger.info(f"  精确匹配失败，尝试正则单词边界匹配")
                try:
                    pattern = re.compile(f"^{re.escape(target_size)}\\b")
                    target_text_locator = container.get_by_text(pattern).first
                except Exception:
                    pass

            if await target_text_locator.count() == 0:
                logger.info(f"  正则匹配失败，尝试包含匹配")
                target_text_locator = container.get_by_text(target_size, exact=False).first

            if await target_text_locator.count() == 0:
                logger.warning(f"  在尺码区域未找到文本: {target_size}")
                return False

            logger.info(f"  [尺码选择] 步骤4: 检查元素是否在右侧区域")
            is_in_right_area = await target_text_locator.evaluate("""el => {
                const rect = el.getBoundingClientRect();
                return rect.left >= window.innerWidth / 2;
            }""")
            if not is_in_right_area:
                logger.warning(f"  尺码元素在左侧区域，跳过")
                return False

            logger.info(f"  [尺码选择] 步骤5: 向上查找包含'库存'的行（锚点定位）")
            row_locator = target_text_locator.locator(
                "xpath=ancestor::div[contains(., '库存') or contains(., '件')][1]"
            )

            if await row_locator.count() == 0:
                logger.info(f"  未找到包含'库存'的行，使用直接父级")
                row_locator = target_text_locator.locator("xpath=ancestor::div[1] | ancestor::li[1]").first

            if await row_locator.count() == 0:
                logger.warning("无法定位尺码行")
                return False

            logger.info(f"  [尺码选择] 步骤6: 使用JavaScript原生点击（避免触发<a>跳转）")
            clicked = await row_locator.evaluate("""el => {
                try {
                    el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    return true;
                } catch(e) {
                    console.error('点击失败:', e);
                    return false;
                }
            }""")

            if clicked:
                await page.wait_for_timeout(500)
                is_selected = await self._check_if_selected(row_locator)
                if not is_selected:
                    logger.info(f"  点击后未检测到选中状态，尝试点击文本元素本身")
                    await target_text_locator.evaluate("""el => {
                        try {
                            el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                            return true;
                        } catch(e) {
                            return false;
                        }
                    }""")
                    await page.wait_for_timeout(500)

                logger.info(f"  [OK] 尺码 {target_size} 选择完成")
                return True
            else:
                logger.warning(f"  JavaScript点击失败")
                return False

        except Exception as e:
            logger.error(f"选择尺码逻辑异常: {str(e)}")
            return False

    async def _select_sku_in_region(self, page, target_value: str, region_keywords: list) -> bool:
        """
        核心方法：在指定的SKU区域内精准选择目标值
        策略：先定位包含关键词（如"尺码"）的标题，再向上找SKU容器，在容器内精准匹配
        重点：只在右侧区域查找，使用JavaScript原生点击避免触发<a>跳转
        """
        try:
            region_container = None
            for keyword in region_keywords:
                logger.info(f"  查找SKU区域关键词: '{keyword}'")
                title_locator = page.get_by_text(keyword, exact=False).first
                if await title_locator.count() > 0:
                    logger.info(f"  找到关键词 '{keyword}'，向上查找SKU容器")
                    region_container = title_locator.locator(
                        "xpath=ancestor::div[contains(@class, 'prop') or contains(@class, 'sku') or contains(@class, 'obj') or contains(@class, 'item')][1]"
                    )
                    if await region_container.count() == 0:
                        region_container = title_locator.locator("xpath=..")
                    if await region_container.count() == 0:
                        region_container = title_locator.locator("xpath=../..")

                    if await region_container.count() > 0:
                        logger.info(f"  找到SKU容器 (关键词: {keyword})")
                        break
                    else:
                        region_container = None
                else:
                    logger.info(f"  未找到关键词 '{keyword}'")

            if not region_container or await region_container.count() == 0:
                logger.warning(f"未找到包含 {region_keywords} 的SKU区域")
                return False

            logger.info(f"  在SKU容器内精确匹配: '{target_value}'")
            target_btn = region_container.get_by_text(target_value, exact=True).first

            if await target_btn.count() == 0:
                logger.info(f"  精确匹配失败，尝试包含匹配: '{target_value}'")
                target_btn = region_container.get_by_text(target_value, exact=False).first

            if await target_btn.count() == 0:
                logger.warning(f"  在SKU区域内未找到文本: {target_value}")
                return False

            logger.info(f"  检查元素是否在右侧区域")
            is_in_right_area = await target_btn.evaluate("""el => {
                const rect = el.getBoundingClientRect();
                return rect.left >= window.innerWidth / 2;
            }""")
            if not is_in_right_area:
                logger.warning(f"  元素在左侧区域，跳过")
                return False

            if await self._check_if_selected(target_btn):
                logger.info(f"目标值 {target_value} 已处于选中状态，跳过点击")
                return True

            logger.info(f"  使用JavaScript原生点击: {target_value}")
            clicked = await target_btn.evaluate("""el => {
                try {
                    el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    return true;
                } catch(e) {
                    console.error('点击失败:', e);
                    return false;
                }
            }""")

            if clicked:
                await page.wait_for_timeout(500)
                is_selected = await self._check_if_selected(target_btn)
                if not is_selected:
                    logger.warning(f"点击后未检测到选中状态变化，尝试重新点击: {target_value}")
                    await target_btn.evaluate("""el => {
                        try {
                            el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                            return true;
                        } catch(e) {
                            return false;
                        }
                    }""")
                    await page.wait_for_timeout(500)

                return True
            else:
                logger.warning(f"JavaScript点击失败: {target_value}")
                return False

        except Exception as e:
            logger.error(f"_select_sku_in_region 异常: {str(e)}")
            return False

    async def _check_if_selected(self, locator) -> bool:
        """检查元素是否处于选中状态（通过class或aria属性）"""
        try:
            return await locator.evaluate("""el => {
                const checkEl = el.closest('li') || el.closest('div') || el;
                const classes = checkEl.className || '';
                return classes.includes('selected') ||
                       classes.includes('active') ||
                       classes.includes('checked') ||
                       classes.includes('current') ||
                       el.getAttribute('aria-checked') === 'true';
            }""")
        except:
            return False

    async def _wait_for_page_stable(self, page):
        """等待页面跳动/重排结束（核心防抖机制）"""
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass
        await page.wait_for_timeout(800)

    async def _fill_quantity(self, page, quantity: int) -> bool:
        """填写数量"""
        try:
            qty_inputs = page.locator("input[type='number'], input[type='text']")
            input_count = await qty_inputs.count()
            logger.info(f"找到 {input_count} 个输入框")

            for i in range(input_count):
                try:
                    input_el = qty_inputs.nth(i)
                    input_box = await input_el.bounding_box()
                    if input_box and input_box['width'] > 30 and input_box['height'] > 15:
                        placeholder = await input_el.get_attribute("placeholder") or ""
                        value = await input_el.input_value() or ""
                        class_name = await input_el.get_attribute("class") or ""

                        if ("数量" in placeholder or "qty" in class_name.lower() or
                            "num" in class_name.lower() or value in ["0", "1", ""]):
                            await input_el.click(force=True)
                            await input_el.fill("")
                            await input_el.type(str(quantity), delay=50)
                            await input_el.press("Enter")
                            await page.wait_for_timeout(800)
                            logger.info(f"[OK] 已设置数量: {quantity}")
                            return True
                except Exception:
                    continue

            logger.info("尝试通过+按钮设置数量")
            plus_btns = page.locator("[class*='plus'], [class*='increase'], [class*='add']")
            plus_count = await plus_btns.count()
            if plus_count > 0:
                for _ in range(min(quantity, 100)):
                    await plus_btns.first.click(force=True)
                    await page.wait_for_timeout(100)
                logger.info(f"[OK] 已通过+按钮设置数量: {quantity}")
                return True

            plus_btn = page.get_by_text("+", exact=True).first
            if await plus_btn.count() > 0:
                for _ in range(min(quantity, 100)):
                    await plus_btn.click(force=True)
                    await page.wait_for_timeout(100)
                logger.info(f"[OK] 已通过+按钮设置数量: {quantity}")
                return True

            return False
        except Exception as e:
            logger.warning(f"填写数量失败: {str(e)}")
            return False

    async def fill_1688_sku_and_add_to_cart(
        self,
        color: str = "",
        size: str = "",
        quantity: int = 1,
        product_type: str = ""
    ) -> Tuple[bool, str]:
        """
        精准操作 1688 商品规格并加入采购车
        核心策略：先绘制右侧SKU区域标注 -> 通过索引点击 -> JS原生点击防止页面跳动
        """
        await self._ensure_initialized()

        try:
            page = await self._context.get_current_page()
            results = []

            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)

            size_index = -1

            logger.info("[SKU操作] 步骤1: 绘制右侧SKU区域元素标注")
            await self.highlight_elements()

            if color or product_type:
                target_type = product_type if product_type else color
                logger.info(f"[SKU操作] 步骤2: 选择颜色/款式: {target_type}")
                
                type_index = await self.find_element_index(target_type, "颜色")
                if type_index < 0:
                    type_index = await self.find_element_index(target_type, "规格")
                if type_index < 0:
                    type_index = await self.find_element_index(target_type, "")
                
                if type_index >= 0:
                    type_success, type_msg = await self.click_element_by_index(type_index)
                    if type_success:
                        results.append(f"已选择款式: {target_type}")
                        logger.info(f"  [OK] 款式选择成功: {target_type}")
                        await page.wait_for_timeout(800)
                        await self.highlight_elements()
                    else:
                        logger.warning(f"  款式选择失败: {type_msg}")
                        results.append(f"款式选择失败: {target_type}")
                else:
                    logger.warning(f"  未找到款式元素: {target_type}")
                    results.append(f"未找到款式: {target_type}")

            if size:
                logger.info(f"[SKU操作] 步骤3: 选择规格: {size}")
                
                size_index = await self.find_element_index(size, "尺码")
                size_el_type = "尺码"
                if size_index < 0:
                    size_index = await self.find_element_index(size, "颜色")
                    size_el_type = "颜色"
                if size_index < 0:
                    size_index = await self.find_element_index(size, "规格")
                    size_el_type = "规格"
                if size_index < 0:
                    size_index = await self.find_element_index(size, "")
                    size_el_type = "未知"
                
                if size_index >= 0:
                    size_element = self._element_list[size_index]
                    size_top = size_element.get('top', 0)
                    
                    logger.info(f"  找到规格 '{size}' 在索引 {size_index}, 类型: {size_el_type}, 顶部位置: {size_top}")
                    
                    if size_el_type == "尺码":
                        row_elements = []
                        for i, el in enumerate(self._element_list):
                            el_top = el.get('top', 0)
                            if abs(el_top - size_top) < 20:
                                row_elements.append(i)
                        
                        logger.info(f"  同行元素索引: {row_elements}")
                        
                        if row_elements:
                            last_index = row_elements[-1]
                            logger.info(f"  选择该行最后一个标注索引 {last_index}")
                            size_success, size_msg = await self.click_element_by_index(last_index)
                        else:
                            size_success, size_msg = await self.click_element_by_index(size_index)
                    else:
                        logger.info(f"  颜色/规格类型，直接点击元素")
                        size_success, size_msg = await self.click_element_by_index(size_index)
                    
                    if size_success:
                        results.append(f"已选择规格: {size}")
                        logger.info(f"  [OK] 规格选择成功: {size}")
                        await page.wait_for_timeout(800)
                        await self.highlight_elements()
                    else:
                        logger.warning(f"  规格选择失败: {size_msg}")
                        results.append(f"规格选择失败: {size}")
                else:
                    logger.warning(f"  未找到规格元素: {size}")
                    results.append(f"未找到规格: {size}")

            if quantity > 1:
                logger.info(f"[SKU操作] 步骤4: 设置数量: {quantity}")
                
                target_size_top = None
                if size_index >= 0:
                    target_size_top = self._element_list[size_index].get('top', 0)
                
                qty_input_index = -1
                if target_size_top is not None:
                    for i, el in enumerate(self._element_list):
                        if el.get('type') == '输入框':
                            el_top = el.get('top', 0)
                            if abs(el_top - target_size_top) < 20:
                                qty_input_index = i
                                break
                else:
                    for i, el in enumerate(self._element_list):
                        if el.get('type') == '输入框':
                            qty_input_index = i
                            break
                
                if qty_input_index >= 0:
                    qty_success, qty_msg = await self.input_text_by_index(qty_input_index, str(quantity))
                    if qty_success:
                        results.append(f"已设置数量: {quantity}")
                        logger.info(f"  [OK] 数量设置成功: {quantity}")
                    else:
                        logger.warning(f"  数量设置失败: {qty_msg}")
                        
                        logger.info(f"  尝试使用加号按钮...")
                        plus_index = -1
                        if target_size_top is not None:
                            for i, el in enumerate(self._element_list):
                                if el.get('type') == '加号':
                                    el_top = el.get('top', 0)
                                    if abs(el_top - target_size_top) < 20:
                                        plus_index = i
                                        break
                        else:
                            for i, el in enumerate(self._element_list):
                                if el.get('type') == '加号':
                                    plus_index = i
                                    break
                        
                        if plus_index >= 0:
                            for _ in range(min(quantity - 1, 200)):
                                await self.click_element_by_index(plus_index)
                            results.append(f"已设置数量(加号): {quantity}")
                            logger.info(f"  [OK] 数量设置成功(加号): {quantity}")
                else:
                    logger.warning(f"  未找到数量输入框")
                    results.append("未找到数量输入框")

            logger.info("[SKU操作] 步骤5: 点击加采购车")
            
            cart_index = -1
            for i, el in enumerate(self._element_list):
                text = el.get('text', '')
                el_type = el.get('type', '')
                if (el_type == '操作' or el_type == '') and ('加采购车' in text or '加入购物车' in text):
                    cart_index = i
                    break
            
            if cart_index >= 0:
                cart_element = self._element_list[cart_index]
                cart_top = cart_element.get('top', 0)
                cart_text = cart_element.get('text', '')
                
                logger.info(f"  找到加采购车按钮在索引 {cart_index}, 顶部位置: {cart_top}, 文本: {cart_text}")
                
                await page.evaluate(f"""
                    window.scrollTo(0, {cart_top - 200});
                """)
                await page.wait_for_timeout(500)
                
                cart_success, cart_msg = await self.click_element_by_index(cart_index)
                if cart_success:
                    results.append("已点击加采购车")
                    logger.info("  [OK] 加采购车点击成功")
                    await page.wait_for_timeout(1500)
                else:
                    logger.warning(f"  加采购车点击失败: {cart_msg}")
                    logger.info("  尝试使用文本查找点击...")
                    
                    cart_success, cart_msg = await page.evaluate("""
                        (() => {
                            const buttons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                            for (const btn of buttons) {
                                const text = btn.textContent || btn.value || '';
                                if (text.includes('加采购车') || text.includes('加入购物车')) {
                                    btn.scrollIntoView({block: 'center'});
                                    setTimeout(() => {
                                        btn.click();
                                    }, 200);
                                    return {success: true, text: text};
                                }
                            }
                            return {success: false, error: '未找到按钮'};
                        })();
                    """)
                    
                    if cart_success:
                        results.append("已点击加采购车(文本查找)")
                        logger.info("  [OK] 加采购车点击成功(文本查找)")
                        await page.wait_for_timeout(1500)
                    else:
                        logger.warning("  加采购车点击失败(文本查找)")
                        results.append("加采购车点击失败")
            else:
                logger.warning("  未找到加采购车按钮")
                logger.info("  尝试全局查找加采购车按钮...")
                
                cart_success, cart_msg = await page.evaluate("""
                    (() => {
                        const buttons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                        for (const btn of buttons) {
                            const text = btn.textContent || btn.value || '';
                            if (text.includes('加采购车') || text.includes('加入购物车')) {
                                btn.scrollIntoView({block: 'center'});
                                setTimeout(() => {
                                    btn.click();
                                }, 200);
                                return {success: true, text: text};
                            }
                        }
                        return {success: false, error: '未找到按钮'};
                    })();
                """)
                
                if cart_success:
                    results.append("已点击加采购车(全局查找)")
                    logger.info("  [OK] 加采购车点击成功(全局查找)")
                    await page.wait_for_timeout(1500)
                else:
                    results.append("加采购车点击失败")

            return True, " | ".join(results)

        except Exception as e:
            logger.error(f"SKU填写过程发生异常: {str(e)}", exc_info=True)
            return False, f"执行异常: {str(e)}"
    
    async def is_logged_in(self) -> bool:
        await self._ensure_initialized()
        
        try:
            page = await self._context.get_current_page()
            
            has_logout = await page.evaluate("""
                document.querySelector('a[href*="logout"], a[href*="signout"], .logout, [onclick*="logout"], [onclick*="signout"]') !== null ||
                document.querySelector('.user-info, .avatar, .login-info') !== null
            """)
            
            return has_logout
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {str(e)}", exc_info=True)
            return False
    
    async def cleanup(self):
        logger.info("清理浏览器资源")
        try:
            if self._context is not None:
                await self._context.close()
                self._context = None
                self._dom_service = None
            
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            
            self._initialized = False
            logger.info("浏览器资源清理完成")
            
        except Exception as e:
            logger.error(f"清理浏览器资源失败: {str(e)}", exc_info=True)