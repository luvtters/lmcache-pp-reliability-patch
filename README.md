# LMCache PP 可靠性补丁：匿名下载与终端应用

本仓库公开，可匿名下载，无需在目标服务器登录 GitHub 或配置 Token。

补丁更新到可靠性修复版 `02ffb6943924d1ebd78e31dc3a608dd4af3de271`。脚本自动选择以下两种已验证基线对应的补丁：

- 已有原生 PP 适配版 `89d93a2ea62030f6890b5bbe8f902c5b92945c8d`。
- 上述版本已应用旧 STORE 完成通知修复 `2570c2c2fd2d893c313ebf4a01c14dc88a9ce4fe`，包括只通过终端应用该修复、Git HEAD 尚未变化的情况。

两种补丁均修改 14 个 LMCache Python 文件，不修改 vLLM、Ascend 插件、setup.py 或原生扩展源码。上游 LMCache 代码许可证见 `LMCache-LICENSE`。

## 应用

在容器的个人可写目录，使用原本启动模型和缓存服务的 Python 环境：

```bash
GIT_TERMINAL_PROMPT=0 git -c credential.helper= clone --depth 1 \
  https://github.com/luvtters/lmcache-pp-reliability-patch.git lmcache-fix-public

python lmcache-fix-public/apply_patch.py --check && \
python lmcache-fix-public/apply_patch.py
```

脚本自动定位当前 Python 的 LMCache，打印目标路径，先检查兼容性，再备份受影响文件并应用补丁、检查语法。`--check` 不修改目标；检查失败时不强行覆盖。

如果已经克隆本仓库，先在交付目录执行 `GIT_TERMINAL_PROMPT=0 git -c credential.helper= -c http.extraHeader= pull --ff-only` 更新。旧交付在已经含有 STORE 修复时会在 connector.py 与 metadata.py 两处冲突；新版会选择 `2570c2c-to-02ffb69` 补丁，不重复应用旧修复。选择依据为完整补丁的预检查结果，不只看 Git HEAD。

如果服务通过专用 `PYTHONPATH` 或加载器运行，当前终端须使用同一环境；也可通过 `--root /实际包含lmcache目录的根目录` 显式指定目标。必须确认该目录确实被服务加载。

这不是任意官方 LMCache 版本都可直接使用的通用补丁。目标环境应已有配套原生 PP 和 Ascend 适配，不能与独立 STATUS 重查候选混用。

## 启动配置增量

两台 PP 机器的缓存服务脚本、模型服务脚本，都在实际启动命令之前添加：

```bash
export KS_LMCACHE_MP_READ_POLICY=transfer_borrow
unset KS_LMCACHE_L1_RECHECK_ON_STATUS
```

模型原有 `--kv-transfer-config` 的外层 MultiConnector，以及 `connectors` 数组中的 LMCache 子连接器，均在各自对象直接设置：

```json
"kv_load_failure_policy": "recompute"
```

该字段与各自的 `kv_connector` 同级，不放进子项的 `kv_connector_extra_config`。保留原 APC、模型、TP/PP、MTP、Mooncake 和其他计算参数。

两端代码、配置同步后，通过正常服务切换先启动缓存，再启动模型。脚本不安装依赖、不重编译、不自动启停服务。

## 回退

在补丁目标根目录执行，使用应用时打印的备份目录中的 `applied.patch`：

```bash
export GIT_CEILING_DIRECTORIES="$(dirname "$PWD")"
git -c core.autocrlf=false apply --reverse --check /实际备份目录/applied.patch && \
git -c core.autocrlf=false apply --reverse /实际备份目录/applied.patch
```

同时恢复应用前的启动配置并统一重启相关进程。原文件备份位于脚本打印的 `backup-before-02ffb69-*` 目录，附有 `backup.json`。回退检查失败时保留后续修改，不强行覆盖。

## 范围

本版修复实际搬运期间源对象读保护、失败重算、部分 APC 失败后的 STORE 范围、迟回访健康误判与 PREEMPTED 会话恢复。源码已做跨机 PP2 可靠性验证，但不代表全部设备异常或模型严格数值等价均已验收。

APC 已覆盖时跳过外部查询的性能优化尚未实现；CPU 候选 C 的 STATUS 固定预算修改也未包含。该交付不是性能优化已通过的声明。
