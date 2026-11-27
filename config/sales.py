"""销售执行端身份；店铺和来源的密钥通过各自环境变量引用读取。"""

from config.env_loader import apply_env_overrides
from config.schema import schema_default

SALES_EXECUTOR_ID = schema_default("SALES_EXECUTOR_ID")

apply_env_overrides(globals())
