import pandas as pd
import re
from typing import Dict, Optional, Tuple, List


class DataProcessor:
    REQUIRED_COLUMNS = ['url', 'item_name', 'quantity']
    OPTIONAL_COLUMNS = ['color', 'size', 'product_type']
    
    COLUMN_ALIASES = {
        'url': ['url', '网址', '链接', '网站', 'web_url', 'site_url'],
        'item_name': ['item_name', '商品名', '商品名称', '名称', '商品', 'item', 'product_name', 'product'],
        'quantity': ['quantity', '数量', '购买数量', '购数量', 'num', 'count'],
        'color': ['color', '颜色', '色', '颜色分类', '色彩'],
        'size': ['size', '尺码', '尺寸', '号', '规格', '鞋码'],
        'product_type': ['product_type', '类型', '商品类型', '规格类型', '产品类型', '型号', '款号']
    }
    
    def __init__(self):
        pass
    
    def _find_column(self, df: pd.DataFrame, target: str) -> Optional[str]:
        for col in df.columns:
            col_lower = str(col).strip().lower()
            if col_lower in self.COLUMN_ALIASES.get(target, []):
                return col
        return None
    
    def _normalize_url(self, url: str) -> str:
        url = str(url).strip()
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url
        return url
    
    def _validate_url(self, url: str) -> bool:
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$',
            re.IGNORECASE
        )
        return bool(url_pattern.match(url))
    
    def _validate_quantity(self, quantity: int) -> bool:
        return isinstance(quantity, int) and quantity > 0 and quantity <= 999
    
    def process_excel(self, file_path: str) -> Tuple[pd.DataFrame, List[str]]:
        errors = []
        
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            errors.append(f"读取文件失败: {str(e)}")
            return pd.DataFrame(), errors
        
        if df.empty:
            errors.append("Excel 文件为空")
            return pd.DataFrame(), errors
        
        column_mapping = {}
        for required_col in self.REQUIRED_COLUMNS:
            found_col = self._find_column(df, required_col)
            if found_col:
                column_mapping[required_col] = found_col
            else:
                errors.append(f"缺少必需列: {required_col} (别名: {', '.join(self.COLUMN_ALIASES.get(required_col, []))})")
        
        if errors:
            return pd.DataFrame(), errors
        
        processed_data = []
        for idx, row in df.iterrows():
            row_data = {
                'url': self._normalize_url(row[column_mapping['url']]),
                'item_name': str(row[column_mapping['item_name']]).strip(),
                'quantity': int(row[column_mapping['quantity']]) if pd.notna(row[column_mapping['quantity']]) else 1
            }
            
            for opt_col in self.OPTIONAL_COLUMNS:
                found_col = self._find_column(df, opt_col)
                if found_col and pd.notna(row[found_col]):
                    row_data[opt_col] = str(row[found_col]).strip()
                else:
                    row_data[opt_col] = ''
            
            row_errors = []
            
            if not self._validate_url(row_data['url']):
                row_errors.append(f"第 {idx+1} 行: URL 格式无效")
            
            if not row_data['item_name']:
                row_errors.append(f"第 {idx+1} 行: 商品名称为空")
            
            if not self._validate_quantity(row_data['quantity']):
                row_errors.append(f"第 {idx+1} 行: 数量无效 (应为 1-999)")
            
            if row_errors:
                errors.extend(row_errors)
            else:
                processed_data.append(row_data)
        
        result_df = pd.DataFrame(processed_data)
        
        if not result_df.empty:
            errors.append(f"数据校验完成，共 {len(processed_data)} 条有效数据，{len(df) - len(processed_data)} 条无效数据已过滤")
        
        return result_df, errors
    
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        errors = []
        
        if df.empty:
            errors.append("数据为空")
            return False, errors
        
        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                errors.append(f"缺少必需列: {col}")
        
        if errors:
            return False, errors
        
        for idx, row in df.iterrows():
            if not self._validate_url(str(row['url'])):
                errors.append(f"第 {idx+1} 行: URL 格式无效")
            
            if not str(row['item_name']).strip():
                errors.append(f"第 {idx+1} 行: 商品名称为空")
            
            if not self._validate_quantity(int(row['quantity'])):
                errors.append(f"第 {idx+1} 行: 数量无效")
        
        return len(errors) == 0, errors
    
    def generate_report(self, results: List[Dict], output_path: str) -> bool:
        try:
            report_data = []
            for idx, result in enumerate(results):
                report_data.append({
                    '序号': idx + 1,
                    'URL': result.get('url', ''),
                    '商品名称': result.get('item_name', ''),
                    '商品类型': result.get('product_type', ''),
                    '颜色': result.get('color', ''),
                    '尺码': result.get('size', ''),
                    '数量': result.get('quantity', 1),
                    '状态': result.get('status', 'unknown'),
                    '失败原因': result.get('message', '') if result.get('status') == 'failed' else '',
                    '截图路径': result.get('screenshot_path', ''),
                    '执行步骤': result.get('steps', 0)
                })
            
            report_df = pd.DataFrame(report_data)
            
            success_count = len([r for r in results if r.get('status') == 'success'])
            failed_count = len([r for r in results if r.get('status') == 'failed'])
            
            summary_sheet = pd.DataFrame({
                '统计项': ['总任务数', '成功数', '失败数', '成功率'],
                '数值': [
                    len(results),
                    success_count,
                    failed_count,
                    f"{(success_count / len(results) * 100):.2f}%" if results else 'N/A'
                ]
            })
            
            with pd.ExcelWriter(output_path) as writer:
                report_df.to_excel(writer, sheet_name='采购结果', index=False)
                summary_sheet.to_excel(writer, sheet_name='统计汇总', index=False)
            
            return True
        
        except Exception as e:
            return False
