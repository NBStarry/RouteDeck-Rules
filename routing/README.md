# RouteDeck Rules

RouteDeck desktop v0.3.0 使用纯 YAML 管理桌面分流。订阅只提供节点；RouteDeck 提供组与规则。无需 JavaScript、仓库登录、Token、外部下载器或新增后台服务。

本目录提供桌面纯 YAML 方案。公开仓库为 [RouteDeck-Rules](https://github.com/NBStarry/RouteDeck-Rules)。固定版本下载以发行记录为准。目标桌面已完成新 Profile 导入、运行与定点原生更新检查；长期稳定性和用户验收仍未完成。旧 RouteDeck 私库、JS 和手机配置保持历史状态；手机暂停，不属于本轮交付。

## 文件与更新

|文件|用途|更新方式|
|---|---|---|
|`routing/desktop.yaml`|完整公网组、规则入口和节点源模板|固定版本，手动升级|
|`routing/rules/openai.yaml`|OpenAI 域名|原生 HTTP rule-provider|
|`routing/rules/us.yaml`|Anthropic/Claude 与 Google 域名|原生 HTTP rule-provider|
|`routing/rules/direct.yaml`|仅 DeepSeek API 精确域名|原生 HTTP rule-provider|
|`routing/desktop.test.py`|公开文件与合成内核检查|开发时运行，不在客户端运行|

规则地址固定为 `https://raw.githubusercontent.com/NBStarry/RouteDeck-Rules/stable/v1/routing/rules/` 下的三个文件。发布方先验证内容，再更新 `stable/v1`。客户端每86400秒由 Mihomo 拉取规则数据。模板、代理组、节点源地址及本机例外不会随规则下载改变。短周期隔离测试不能证明真实桌面已经等待并触发整日更新。

## 准备本机配置

1. 从同一固定版本下载 `desktop.yaml`。保留当前可用 Profile、专属层和全局层的受限备份。
2. 在本机私有副本中，将两个 `example.invalid` 地址替换为已授权的节点订阅地址。示例地址不可用。各来源必须获准用于自动地区组；manual-only 或 iKuuu 来源不能加入。只有一个允许来源时，移除另一 provider，并从四个地区组的 `use` 中移除它。节点列表下载显式使用 `proxy: DIRECT`，避免冷启动时依赖尚未取得节点的 RouteDeck 组；首次部署须确认保留的 HTTPS 源可通过该路径下载。运行时各源独立更新；任一已授权源能提供所需地区的可用节点即可继续，另一个源不可用不会单独阻断整个方案。这个设置只控制节点列表下载，不为业务请求增加 DIRECT。源不能直达时停止安装并确认下载路径，不静默使用其他源或放宽分流。
3. 保持各源独立缓存路径和不同 `additional-prefix`。检查同一来源内的重复节点名；发现冲突就停止导入。当前支持供应商返回 Mihomo 可读取的节点数据；其他订阅格式须先验证。
4. 显式加入本机所需 DNS、私有节点、内网组和例外规则。逐项对照切换前实际运行配置、全局层及本机专属层，保留有来源依据的本机例外和顺序。只提取旧脚本的一个选项块可能遗漏 Tailnet 或办公网络例外。不要从供应商复制规则、组或 DNS。公开模板不包含这些设备设置。
5. 将本机例外放在三个 `RULE-SET` 之前。保留唯一末尾 `MATCH,RouteDeck-Proxy`。检查所有组、规则和 DNS 引用都存在，再用已有目标内核对私有候选执行 `mihomo -t`。

如果现有 DNS 依赖代理规则，首次节点下载可能发生启动依赖。目标设备实测需要先写入原生节点缓存：

1. 从已授权源取得当前有效的 Mihomo 节点数据。确认缓存仅含该源的 `proxies`，并保留节点原始名称。
2. 根据实际运行核心的 HomeDir（`-d`）解析各 provider 的相对 `path`。在该目录中新建可写的私有缓存目录；本轮使用 `./routedeck-cache/v1/source-a.yaml` 和 `source-b.yaml`。同步修改私有 YAML 中对应的 `path`，不要覆盖已有缓存或修改既有目录权限。
3. 将新缓存目录权限设为 `0700`，两个节点文件设为 `0600`。保持 provider 的 `type: http`、授权 URL、原有更新周期和 DNS 配置。缓存预置只解决首启，不能改成永久 file provider。
4. 激活后分别核对节点数、更新时间和原生更新结果。预置成功不等于 HTTP 更新成功。

私有订阅、认证、节点、DNS、内网例外和身份数据只留在本机，不能提交或放入公开下载。保留既有 OS Tailscale 身份与系统网络设置。本方案不创建 Tailscale 节点、状态目录或登录身份。

## Clash Verge Rev 导入

目标实测版本为 Clash Verge Rev 2.4.5 / Mihomo 1.19.19。菜单名称以该版本为准。

1. 在“订阅”页点击“新建”，将类型从 Remote 改为 Local，点击“选择文件”并选取本机私有 YAML。选择文件会改写名称，因此在选完文件后填写名称，例如 `RouteDeck YAML v0.3.0`，然后保存。保留原 Profile。
2. 如果客户端有全局 Merge/Script，先检查其对新 Profile 的影响。2.4.5 会先执行全局层，新 Profile 不会自动跳过它。通过新 Profile 右键菜单的“扩展覆写配置”，在专属编辑器中保存完整私有 YAML，以最后覆盖 `proxies`、`proxy-groups`、`rules`。专属“扩展脚本”保持客户端默认无操作模板，不导入 RouteDeck JS。
3. mapping 会深合并，数组会替换。旧 provider 或 DNS 子键可能残留。确认新地区组只显式引用允许的源，旧条目不进入新组或规则，且不会增加未授权下载；不能只看到六个组就认为隔离完成。不要为清理残留而更改其他任务的全局脚本。
4. 保存后点击新 Profile 卡片激活。修改当前 Profile 后，可使用“重新激活订阅”。读回实际内核组、规则、DNS及本机依赖；检查公网 HTTPS 和既有 Tailnet IPv4、IPv6、完整域名连接。
5. 分别检查节点 provider 更新与公共 rule-provider 更新。它们是两种原生更新，不能把订阅卡片刷新或重新激活当作规则定时更新的证据。“代理”页的“代理集合”中可看到 A/B 各自的“更新”按钮。本轮观察了按钮，实际定点更新通过核心原生 API 执行；未把按钮点击记作已验证。不点击“更新全部”。本轮没有确认公共规则的独立 UI 更新按钮；规则自动按 `interval` 更新，检查时使用原生规则 provider API。

本轮通过真实 UI 创建并激活独立 Local Profile，保存专属 YAML，保持默认扩展脚本。独立检查确认六组、两个 select 默认 US、三条规则集及本机例外生效。两源与三规则的原生更新均返回 HTTP 204，更新时间推进；更新后公网 HTTPS 与既有 Tailnet IPv4、IPv6、完整域名连接通过，身份保持。本轮还在配置失败时实际切回原 Profile 并确认连接恢复。首次失败及修正过程保留在工程记录中。

## 分流行为

- US、TW、HK、SG 各使用原生 fallback，按 provider 顺序选择可用节点，不按最低延迟排序。四地区均以终端拒绝 provider 结束；不得移除它或把它放到首位。
- 名称只接受明确地区标记。混合地区、manual-only、iKuuu、私有或非准许协议不会进入地区池。名称不能证明节点真实地理位置。节点源白名单与节点过滤同时生效。
- 每个源通过原生 `additional-prefix` 区分同名节点。源自身的同名冲突必须在候选阶段拒绝，不能依赖静默覆盖。
- OpenAI 与 Proxy 是两个独立 select，默认 US，可分别手动选择 TW/HK/SG。US 无节点时拒绝，不自动跨区。所有地区为空时也不能回退 DIRECT。启动或节点全部失效时允许连接失败，不保证无中断。
- OpenAI 域名：chatgpt.com、openai.com、oaistatic.com、oaiusercontent.com。
- 固定 US：anthropic.com、claude.ai、claude.com、claudeusercontent.com、google.com、googleapis.com、gstatic.com、googleusercontent.com。
- 仅 api.deepseek.com 精确直连。其他 DeepSeek 域名没有特殊规则。

最终顺序：本机明确例外 → OpenAI/US/Direct 三个规则集 → `MATCH,RouteDeck-Proxy`。不保留供应商规则，不自动加国内直连、广告拦截或通用私网直连。

源 provider 的 `exclude-type` 比较原始类型名；组的 `exclude-type` 比较内核类型名，二者不能随意互换。源端排除 reject/direct 等类型，组端保留本机专用 Reject 终端。不要使用 `include-all`，不要依靠节点名称排序放置终端。

## 失败与恢复

规则 provider 带当前规则的内嵌 `payload`，用于原生首启备用。首次无缓存、下载失败、明确解析失败、重启缓存及新请求热采用需要目标内核验证，不能仅凭字段存在声明离线可用。原生解析可能容忍部分坏行或空集；发布检查拒绝空集合、非法域名、额外目标和未知规则类型。

节点源按各自 `interval` 更新。节点数据更新不引入供应商规则、组或 DNS。公共规则更新不修改节点源地址或本机私有层。固定 gstatic 健康探测只验证该地址，不证明业务登录、地区许可或认证流可用。

升级模板时，先保存当前可用私有副本，再取新固定版本并重新合入本机私有层、检查候选，最后通过相同 UI 保存与激活。规则数据使用 stable/v1 原生更新；模板不会自动下载执行。

保留旧 Profile 作为恢复入口。只有本轮应用失败或用户明确要求时才切回，并核对实际运行和连接；文件保存成功不代表网络恢复。本轮不重跑用户已取消的完整历史回退实验。

## 开发检查与证据边界

使用已安装的 Python/PyYAML，不安装新运行依赖：

```sh
python3 routing/desktop.test.py
python3 routing/desktop.test.py --mihomo /path/to/existing/mihomo
```

第一条检查规则格式、策略边界、唯一缓存、组引用、地区名称及冲突。第二条使用现有内核、临时目录和 loopback 端点检查实际成员、末尾拒绝和空地区请求未直连；不会读取真实订阅或修改活动客户端。未指定内核时，内核检查明确跳过。

原生定时更新和缓存使用独立临时内核验证；实际设备导入、运行结果、长期稳定性和用户验收分别记录。首启后与刷新后的身份一致不能补写未知的迁移前身份验证。候选公开可下载不代表设备切换完成。
