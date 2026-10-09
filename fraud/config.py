import os
from pathlib import Path
DATA = Path(os.getenv('DATA_DIR', 'data'))
MODELS = Path(os.getenv('MODEL_DIR', 'models'))
API_KEY = os.getenv('API_KEY', 'local-demo-change-me')
REDIS_URL = os.getenv('REDIS_URL', '')
FEATURES = ['log_amount', 'count_5m', 'sum_5m', 'amount_ratio', 'new_device', 'foreign', 'hour_sin', 'hour_cos']
