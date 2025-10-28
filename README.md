# pyapollo

- [English](README.en.md)
- [中文](README.md)

## 简介

使用官方的 Apollo HTTP API 实现的 Python 客户端。在 Python 3.13 以及最新版的 Apollo 上已经测试通过。

主要功能：

- 支持实时更新：支持 Apollo 配置项获取与实时更新。
- 支持密钥：支持有密钥/无密钥的 Apollo 应用配置获取。
- 支持分布式部署：支持基于分布式部署的 Apollo 应用配置获取。
- 有容灾机制：当一个 Apollo 服务节点不可用时，会自动切换到下一个可用的服务节点。
- 支持异步：提供异步类型的客户端，支持异步获取配置项。
- 支持多种配置方式：支持通过环境变量、.env 文件或直接参数配置。

## 为什么写这个项目

[Apollo 官网](https://www.apolloconfig.com/#/zh/client/python-sdks-user-guide)推荐了三个 Python 客户端，分别有以下问题：

1. [客户端 1 项目](https://github.com/filamoon/pyapollo)现在已经用不了了，在 2019 年就停止维护了。

2. [客户端 2 项目](https://github.com/BruceWW/pyapollo)里面用了 telnetlib 库，这个标准库在 python 3.13 中已经 deprecated 了，还有里面的 url 我试了下已经 404 了，看了下最新的 apollo 官方文档，可能需要更新了。我想在此基础上改一改，但这一改，除了加了支持 app secret 的一些逻辑，还改了不少零零碎碎的地方，删了一些逻辑，所以我就不给作者 BruceWW 提 PR 了。直接新建了一个项目，还是叫 pyapollo。

3. [客户端 3 项目](https://github.com/xhrg-product/apollo-client-python) readme 里说已经废弃了？我就没试了。

## 原理

在 Apollo 官方文档[总体设计](https://www.apolloconfig.com/#/zh/design/apollo-introduction?id=_45-%e6%80%bb%e4%bd%93%e8%ae%be%e8%ae%a1)中说过:

- Meta Server 用于封装 Eureka 的服务发现接口。
- Client 通过域名访问 Meta Server 获取 Config Service 服务列表（IP+Port），而后直接通过 IP+Port 访问服务端获取配置信息。

本项目就是基于这个原理实现的。其中用于服务发现的接口[源码定义所在](https://github.com/apolloconfig/apollo/blob/6de040a2b9bc68d32c95045de00e21f55f20122b/apollo-portal/src/main/java/com/ctrip/framework/apollo/portal/controller/SystemInfoController.java#L45)。

## 安装

通过 pip 安装：

```bash
pip install git+https://github.com/OuterCloud/pyapollo.git@main
```

写到 requirements.txt 里也是一样：

```
git+https://github.com/OuterCloud/pyapollo.git@main
```

## 使用方法

下文中的参数说明：

- meta_server_address: Apollo 服务端的地址。
- app_id: Apollo 应用的 ID。
- app_secret: Apollo 应用的密钥。

### 配置方式

pyapollo 支持多种配置方式，按照优先级从高到低排序：

1. 直接传参：在创建客户端时直接传入参数
2. 使用 ApolloSettingsConfig：创建配置对象并传入客户端
3. 环境变量：使用 APOLLO\_ 前缀的环境变量
4. .env 文件：在项目根目录创建 .env 文件

#### 使用 .env 文件

在项目根目录创建 `.env` 文件，内容如下：

```
# Apollo 必需配置
APOLLO_META_SERVER_ADDRESS=http://localhost:8080
APOLLO_APP_ID=your-app-id

# 认证配置
APOLLO_USING_APP_SECRET=true
APOLLO_APP_SECRET=your-app-secret

# 可选配置
APOLLO_CLUSTER=default
APOLLO_ENV=DEV
APOLLO_NAMESPACES=application,common,database
APOLLO_TIMEOUT=10
APOLLO_CYCLE_TIME=30
```

项目中已提供 `.env.example` 文件作为参考。

##### 自定义 .env 文件路径

除了默认的项目根目录 `.env` 文件外，还可以指定自定义路径的 .env 文件：

```python
from pyapollo.settings import ApolloSettingsConfig
from pyapollo.client import ApolloClient

# 从自定义路径加载 .env 文件
settings = ApolloSettingsConfig.from_env_file("path/to/custom.env")
client = ApolloClient(settings=settings)
```

#### 使用环境变量

直接设置环境变量：

```bash
# 必需配置
export APOLLO_META_SERVER_ADDRESS=http://localhost:8080
export APOLLO_APP_ID=your-app-id

# 认证配置（可选）
export APOLLO_USING_APP_SECRET=true
export APOLLO_APP_SECRET=your-app-secret

# 其他可选配置
export APOLLO_CLUSTER=default
export APOLLO_ENV=DEV
export APOLLO_NAMESPACES=application,common,database
export APOLLO_TIMEOUT=10
export APOLLO_CYCLE_TIME=30
```

##### 支持的环境变量

| 环境变量                   | 说明                   | 默认值      | 是否必需                          |
| -------------------------- | ---------------------- | ----------- | --------------------------------- |
| APOLLO_META_SERVER_ADDRESS | Apollo 服务端地址      | -           | 是                                |
| APOLLO_APP_ID              | Apollo 应用 ID         | -           | 是                                |
| APOLLO_USING_APP_SECRET    | 是否使用密钥认证       | false       | 否                                |
| APOLLO_APP_SECRET          | Apollo 应用密钥        | -           | 仅当 USING_APP_SECRET=true 时必需 |
| APOLLO_CLUSTER             | 集群名称               | default     | 否                                |
| APOLLO_ENV                 | 环境名称               | DEV         | 否                                |
| APOLLO_NAMESPACES          | 命名空间列表，逗号分隔 | application | 否                                |
| APOLLO_TIMEOUT             | 请求超时时间（秒）     | 10          | 否                                |
| APOLLO_CYCLE_TIME          | 配置刷新周期（秒）     | 30          | 否                                |
| APOLLO_CACHE_FILE_DIR_PATH | 缓存文件目录路径       | -           | 否                                |
| APOLLO_IP                  | 客户端 IP 地址         | -           | 否                                |

#### 使用 ApolloSettingsConfig

```python
from pyapollo.settings import ApolloSettingsConfig
from pyapollo.client import ApolloClient

# 创建配置对象
settings = ApolloSettingsConfig(
    meta_server_address="http://localhost:8080",
    app_id="your-app-id",
    using_app_secret=True,
    app_secret="your-app-secret"
)

# 将配置对象传入客户端
client = ApolloClient(settings=settings)
```

### 同步 Apollo 客户端

```python
from pyapollo.client import ApolloClient

# 方式1：直接传参
meta_server_address = "https://your-apollo/meta-server-address"
app_id="your-apollo-app-id"
app_secret="your-apollo-app-secret"

# 有鉴权的 Apollo 同步客户端
apollo = ApolloClient(
    meta_server_address=meta_server_address,
    app_id=app_id,
    app_secret=app_secret,
)

# 无鉴权的 Apollo 同步客户端
apollo = ApolloClient(
    meta_server_address=meta_server_address,
    app_id=app_id,
)

# 方式2：从环境变量或.env文件加载配置
apollo = ApolloClient()  # 自动从环境变量或.env文件加载配置

# 获取 text 格式配置项
val = apollo.get_value("text_key")
print(val)

# 获取 JSON 格式配置项
json_val = apollo.get_json_value("json_key")
print(json_val)
```

### 异步 Apollo 客户端

```python
import asyncio
from pyapollo.async_client import AsyncApolloClient


async def main():
    meta_server_address = "https://your-apollo/meta-server-address"
    app_id="your-apollo-app-id"
    app_secret="your-apollo-app-secret"

    # 有鉴权的 Apollo 异步客户端
    async with AsyncApolloClient(
        meta_server_address=meta_server_address,
        app_id=app_id,
        app_secret=app_secret,
    ) as client:
        # 获取 text 格式配置项
        val = await client.get_json_value("json_key")
        print(val)

        # 获取 JSON 格式配置项
        json_val = await client.get_value("text_key")
        print(json_val)

    # 无鉴权的 Apollo 异步客户端
    async with AsyncApolloClient(
        meta_server_address=meta_server_address,
        app_id=app_id,
    ) as client:
        # 获取 text 格式配置项
        val = await client.get_json_value("json_key")
        print(val)

        # 获取 JSON 格式配置项
        json_val = await client.get_value("text_key")
        print(json_val)

    # 使用自定义配置服务器的异步客户端
    async with AsyncApolloClient(
        app_id=app_id,
        config_server_host="http://config-server.example.com",
        config_server_port=8080
    ) as client:
        # 动态更新配置
        await client.update_config(
            timeout=120,
            namespaces=["application", "cache"]
        )

        val = await client.get_value("sample_key")
        print(val)


if __name__ == "__main__":
    asyncio.run(main())
```

### 动态配置更新

pyapollo 支持在运行时动态更新客户端配置参数，无需重新创建客户端实例：

```python
from pyapollo.client import ApolloClient

# 创建客户端
client = ApolloClient(
    meta_server_address="http://localhost:8080",
    app_id="my-app",
    timeout=30,
    cycle_time=60
)

# 动态更新单个参数
client.update_config(timeout=120)

# 批量更新多个参数
client.update_config(
    timeout=60,
    cycle_time=30,
    cluster="production"
)

# 更新命名空间
client.update_config(
    namespaces=["application", "redis", "database"]
)

# 环境切换
client.update_config(
    meta_server_address="http://prod-apollo:8080",
    env="PROD",
    cluster="production"
)

# 添加认证
client.update_config(
    app_secret="your-secret-key"
)

# 自定义配置服务器（绕过元服务器发现）
client.update_config(
    config_server_host="http://config.example.com",
    config_server_port=8080
)

# 查看当前配置
config = client.get_current_config()
print(config)
```

#### 自定义配置服务器

除了使用元服务器自动发现配置服务器外，还可以直接指定配置服务器地址：

```python
from pyapollo.client import ApolloClient

# 直接连接到已知配置服务器，无需元服务器
client = ApolloClient(
    app_id="my-app",
    config_server_host="http://config-server.example.com",
    config_server_port=8080
)

# 运行时切换配置服务器
client.update_config(
    config_server_host="http://backup-config.example.com",
    config_server_port=9090
)

# 切换回使用元服务器发现（需要提供 meta_server_address）
client.update_config(
    meta_server_address="http://meta-server.example.com",
    config_server_host=None,  # 清除自定义配置
    config_server_port=None
)
```

#### 支持的更新参数

| 参数                | 类型        | 说明                     |
| ------------------- | ----------- | ------------------------ |
| meta_server_address | str         | Apollo 服务端地址        |
| app_id              | str         | 应用 ID                  |
| app_secret          | str \| None | 应用密钥                 |
| cluster             | str         | 集群名称                 |
| env                 | str         | 环境名称                 |
| namespaces          | List[str]   | 命名空间列表             |
| ip                  | str \| None | 客户端 IP 地址           |
| timeout             | int         | 请求超时时间（秒）       |
| cycle_time          | int         | 配置刷新周期（秒）       |
| cache_file_dir_path | str \| None | 缓存文件目录路径         |
| config_server_host  | str \| None | 自定义配置服务器主机地址 |
| config_server_port  | int \| None | 自定义配置服务器端口     |

#### 参数更新的特殊处理

- **meta_server_address**: 更新后会重新获取配置服务器列表
- **app_id**: 更新后会重新初始化缓存文件路径
- **namespaces**: 更新后会清理已移除命名空间的缓存
- **cycle_time**: 更新后会重启轮询线程
- **cache_file_dir_path**: 更新后会重新初始化缓存目录

#### 错误处理

参数更新包含完善的验证机制：

```python
try:
    # 无效参数会抛出 ValueError
    client.update_config(timeout=-1)  # 负数超时
    client.update_config(namespaces=[])  # 空命名空间列表
    client.update_config(app_id="")  # 空应用ID
except ValueError as e:
    print(f"参数验证失败: {e}")
```

## 示例代码

项目提供了多个示例代码，展示不同的配置和使用方式：

### 同步客户端示例

```bash
python examples/sync_demo.py
```

### 异步客户端示例

```bash
python examples/async_demo.py
```

### 配置更新示例

```bash
# 详细的配置更新演示
python examples/update_config_demo.py

# 简单的配置更新示例
python examples/simple_update_examples.py

# 自定义配置服务器示例
python examples/custom_config_server_demo.py

# 异步客户端自定义配置服务器示例
python examples/async_custom_config_server_demo.py
```

### 环境变量配置示例

```bash
# 先设置必要的环境变量
export APOLLO_META_SERVER_ADDRESS=http://localhost:8080
export APOLLO_APP_ID=your-app-id

# 运行示例（使用默认键名 sample_key）
python examples/env_demo.py

# 运行示例（指定配置键名）
python examples/env_demo.py --key your_config_key

# 运行示例（指定不同的文本配置键和JSON配置键）
python examples/env_demo.py --key your_config_key --json-key your_json_key
```

### .env 文件配置示例

```bash
# 确保项目根目录有 .env 文件或 examples/test.env 文件
# 使用默认键名
python examples/dotenv_demo.py

# 指定配置键名
python examples/dotenv_demo.py --key your_config_key

# 指定不同的文本配置键和JSON配置键
python examples/dotenv_demo.py --key your_config_key --json-key your_json_key
```
