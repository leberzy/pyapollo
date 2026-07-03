# pyapollo 1.0 迁移指南

本文档说明从 0.x 升级到 **1.0.0** 的破坏性变更与推荐写法。

## 环境要求

- Python **>= 3.12**
- 安装：`pip install "shebao-apollo-sdk>=1.0.0"`

## 保持不变的 API

以下用法在 1.0 中**无需修改**（在升级 Python 版本后）：

```python
from pyapollo import ApolloClient, AsyncApolloClient, ApolloSettingsConfig

val = client.get_value("key", default="x", namespace="application")
data = client.get_json_value("json_key")
client.update_config(timeout=60)
config = client.get_current_config()
```

## 推荐的新写法

### 生命周期

```python
from pyapollo import ApolloClient

# 方式 A：上下文管理器（推荐）
with ApolloClient(meta_server_address="http://meta:8080", app_id="my-app") as client:
    if client.is_ready():
        print(client.get_value("k"))

# 方式 B：默认 autostart=True，手动 stop
client = ApolloClient(meta_server_address="http://meta:8080", app_id="my-app")
try:
    print(client.get_value("k"))
finally:
    client.stop()

# 方式 C：延迟启动（测试 / DI）
client = ApolloClient(..., autostart=False)
client.start()
```

异步客户端：`autostart` 仅影响 `async with` 是否自动 `start()`，构造函数内不发起网络请求。

```python
async with AsyncApolloClient(app_id="my-app", config_server_host="http://cfg", config_server_port=8080) as client:
    value = await client.get_value("k")
```

### 变更监听（新能力）

```python
from pyapollo import ApolloClient, ChangeType

def on_change(event):
    for key, change in event.changes.items():
        print(event.namespace, key, change.change_type, change.new_value)

client = ApolloClient(...)
sub = client.add_change_listener(on_change, namespaces=["application"])
# sub.cancel()
```

### 类型化取值（新能力）

```python
port = client.get_int("server.port", default=8080)
enabled = client.get_bool("feature.enabled", default=False)
ratio = client.get_float("sample.ratio", default=0.1)
tags = client.get_list("tags", separator=",")
```

## 破坏性变更对照表

| 项目 | 0.x | 1.0 | 迁移 |
|------|-----|-----|------|
| 隐式单例 | 同参数构造复用实例 | 每次独立实例 | 自行持有单例或 DI |
| 停止方法 | `stop_polling_thread()` / `stop_polling()` | `stop()` / `await stop()` | 改调新方法 |
| 内部模块 | `pyapollo.interface`、`pyapollo.settings` 等 | 仅顶层 `from pyapollo import ...`；配置用 `pyapollo.config` | 勿依赖内部路径 |
| 缓存目录 | 包内 `pyapollo/config/` | `~/.cache/apollo/{app}/{cluster}/` | 可删旧文件 |
| 缓存文件名 | `{app}_configuration_{ns}.txt` | `{ns}.json` + `release_key` 元数据 | 自动重建 |
| 日志 | `loguru` | 标准库 `logging` | 自行配置 `logging.getLogger("pyapollo")` |
| 实时更新 | 定时短轮询 | `/notifications/v2` 长轮询 + 定时兜底 | 透明升级 |

## 直连 Config Server（跳过 Meta）

与 0.x 相同，适用于已知 Config Service 地址的场景：

```python
client = ApolloClient(
    app_id="arch-service-diagnose",
    config_server_host="http://testapollo.shebao.net",
    config_server_port=8080,
    namespaces=["application", "prompt"],
)
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `APOLLO_META_SERVER_ADDRESS` | Meta Server 地址 |
| `APOLLO_APP_ID` | 应用 ID |
| `APOLLO_NAMESPACES` | 逗号分隔 namespace |
| `APOLLO_CACHE_FILE_DIR_PATH` | 缓存根目录（可选） |
| `APOLLO_CACHE_DIR` | 同缓存根目录（`cache.py` 解析优先级更高于默认路径） |

集成测试示例：

```bash
APOLLO_SERVER=http://testapollo.shebao.net:8080 \
APOLLO_APP_ID=arch-service-diagnose \
APOLLO_NAMESPACE=application,prompt \
pytest -m integration --no-cov
```

## 开发贡献

```bash
pip install -e ".[dev]"
pre-commit install
pytest                    # 单元测试
pytest -m integration     # 需可访问 Apollo 环境
ruff check src tests
mypy src/pyapollo/getters.py src/pyapollo/listeners.py  # 核心模块逐步收紧
```
