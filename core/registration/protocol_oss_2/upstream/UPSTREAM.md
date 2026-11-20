# 开源protocol-2 兼容入口

真实上游实现、QuickJS 脚本、许可证和来源说明已经迁移到
[内核上游目录](../../../kernels/protocol/protocol_oss_2/upstream/UPSTREAM.md)。
本目录的 Python 文件只将旧导入路径关联到同一个内核模块对象，不再拥有执行源码。

本目录保留 `LICENSE` 与 `SOURCE_SHA256.json` 供历史路径查询；校验值仍表示原始同步前内容，
未按本地修改后的源码重新计算。运行时仅加载内核目录的 JavaScript 资源。
