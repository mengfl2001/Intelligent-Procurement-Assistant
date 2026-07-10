import os
import yaml
from typing import Dict, Optional

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.yaml')

DEFAULT_CONFIG = {
    'api': {
        'api_key': '',
        'base_url': '',
        'model_name': 'qwen3.6-flash'
    },
    'ui': {
        'app_title': 'SmartPurchaseAgent - 智能采购助手',
        'window_width': 1200,
        'window_height': 800,
        'theme': 'light',
        'primary_color': '#1E90FF'
    },
    'browser': {
        'headless': False,
        'window_width': 1280,
        'window_height': 960,
        'timeout': 120
    },
    'task': {
        'max_concurrent': 2,
        'max_retries': 3
    }
}


def load_config() -> Dict:
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        config = merge_configs(DEFAULT_CONFIG, config)
        return config
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return DEFAULT_CONFIG


def save_config(config: Dict):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        print(f"保存配置文件失败: {e}")


def merge_configs(default: Dict, custom: Dict) -> Dict:
    result = default.copy()
    for key, value in custom.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def get_api_config() -> Dict:
    config = load_config()
    return config.get('api', DEFAULT_CONFIG['api'])


def get_ui_config() -> Dict:
    config = load_config()
    return config.get('ui', DEFAULT_CONFIG['ui'])


def get_browser_config() -> Dict:
    config = load_config()
    return config.get('browser', DEFAULT_CONFIG['browser'])


def get_task_config() -> Dict:
    config = load_config()
    return config.get('task', DEFAULT_CONFIG['task'])


def set_api_key(api_key: str):
    config = load_config()
    config['api']['api_key'] = api_key
    save_config(config)


def set_base_url(base_url: str):
    config = load_config()
    config['api']['base_url'] = base_url
    save_config(config)


def set_model_name(model_name: str):
    config = load_config()
    config['api']['model_name'] = model_name
    save_config(config)