# RouteDeck Party v1

Clash Party 2.0.4 的远程覆写策略。节点来自用户授权的原始订阅，分流来自本策略。本目录与桌面纯 YAML 方案并存，使用时不要混用两套安装步骤。

`main` 提供后续可更新的策略地址：`https://raw.githubusercontent.com/NBStarry/RouteDeck-Rules/main/routing/party/v1/party-policy.js`

固定版本：[party-v1.0.0 目录](https://github.com/NBStarry/RouteDeck-Rules/tree/party-v1.0.0/routing/party/v1)；[固定策略文件](https://raw.githubusercontent.com/NBStarry/RouteDeck-Rules/party-v1.0.0/routing/party/v1/party-policy.js)。固定地址不随 `main` 后续更新。

## 首次设置

1. 在 Clash Party 中导入原始节点订阅 URL。只使用允许纳入自动地区组的来源。当前策略接收展开的节点，不支持非空 `proxy-providers` 输入。
2. 由维护 Agent 一次通过客户端原生界面迁入本机准备层，保留本机 DNS、内网规则及其依赖。用户无需手改文件或准备节点缓存；两个 URL 入口不能替代这一步。
3. 添加远程 JavaScript 覆写，填入策略 URL。对目标订阅绑定两个专属覆写，顺序为“本机准备 → 公共远程策略”。不要设为影响其他订阅的全局覆写。
4. 首次试用时使用独立端口，关闭新客户端的系统代理和 TUN。检查绑定、RouteDeck 组、本机例外和实际连接后，再通过原生界面接管。Windows 权限由用户批准；只让一个客户端控制系统代理和 TUN。

本机准备层须清除输入中的旧 `x-routedeck-local`，再完整写入 `version: 1`、`allowCurrentProfile: true`、`excludeNodeNames`、`privateRules`、`privateProxies`、`privateGroups`。该字段只是本地处理接口，不证明输入可信。DNS 与 hosts 各由一个本机来源负责；若客户端原生设置负责，则不重复写入本地对象。维护者须核对绑定顺序与最终运行结果。私有数据不得提交本仓库。

## 日常使用

- 更新节点：刷新原始订阅。随后检查策略绑定、RouteDeck 组和当前地区。
- 更新策略：刷新远程覆写。确认重新应用后，检查 RouteDeck 组、节点来源与实际连接。只刷新节点不会更新策略代码。
- 更新规则数据：由 Mihomo 的 HTTP rule-provider 单独处理。规则数据更新不等于策略代码更新。本版本不承诺客户端定时刷新策略代码。
- 选择地区：`RouteDeck-OpenAI` 与 `RouteDeck-Proxy` 独立选择，默认 US。地区内使用原生 fallback；跨地区由用户手动选择。空地区拒绝，业务不会自动降级为 DIRECT。

健康探测失败不等于业务节点不可用。原生 fallback 可能继续尝试同地区首节点；同地区业务仍可成功时不主动阻断。所选地区业务连接全部不可用时，请求失败，不自动改走其他地区或 DIRECT。

## 故障处理

Clash Party 可能捕获覆写错误并继续使用供应商输入配置，界面也可能没有明显错误提示。网络仍能访问不代表 RouteDeck 分流正常。如果 RouteDeck 组消失或规则异常，记录故障并交维护者修复。维护者在同一策略 URL 恢复有效内容后，刷新远程覆写、重新应用，再验证分流、本机 DNS、内网与实际连接。

本方案不承诺坏策略更新时保留旧策略或首次自动拒绝启用，也不添加本地更新器或守护服务。

## 检查与验证范围

从仓库根运行合成检查：

```sh
node --test routing/party/v1/party-policy.test.cjs
```

Windows 实际验证已覆盖原生界面绑定、两类手动刷新、同 URL 故障修复、手动换区、客户端接管与恢复，以及系统代理、TUN、fake-IP 和已确认的内网连接。这不代表任意订阅格式、所有内网服务或应用登录均可用。

生产环境完整 24 小时触发、长期稳定性与用户验收未完成。短周期隔离规则更新试验不能代替生产整日运行验证。
