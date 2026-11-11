<p align="center">
  <img src="assets/icon.png" width="128" alt="Gray Intel">
</p>

<p align="center">
  <a href="https://github.com/Mymiyu-tool/gray-intel/actions/workflows/package.yml"><img src="https://github.com/Mymiyu-tool/gray-intel/actions/workflows/package.yml/badge.svg" alt="Package"></a>
</p>

<h1 align="center">Gray Intel · 灰产情报检索</h1>

<p align="center">给 Miyu 用的灰产 / 黑产情报检索工具：会黑话，会绕软文，会做站内 dork。</p>

---

## 为什么不是普通搜索

搜「Claude 中转站」这类词，普通搜索引擎前十有八个是「怎么选 / 排行 / 推荐」的带货文。这个包做三件事：

1. **黑话扩展**：`中转站` → `API中转 / relay / 2api / one-api / 号池 / 倍率`；`降智` → `掺水 / 掉包 / 偷换模型 / 虚标`。
2. **多引擎 + 站内 dork**：Bing、360 双引擎，自动对 linux.do、v2ex、GitHub 等站点做定向检索。
3. **软文降权、实锤加权**：标题含「推荐 / 排行 / 测评 / 教程 / 首充」扣分；含「跑路 / 判刑 / 曝光 / 不通过 / 泄漏」加分；落地页广告直接压到底。

结果按分数排序，分数会写在每条结果后面。

## 安装

```bash
git clone https://github.com/Mymiyu-tool/gray-intel.git
miyu pkg install ./gray-intel
```

或者下载 Release 里的 `.miyu` 文件：

```bash
curl -LO https://github.com/Mymiyu-tool/gray-intel/releases/latest/download/gray-intel-0.1.0.miyu
miyu pkg install gray-intel-0.1.0.miyu
```

> 官方社区源收录之后，可以直接 `miyu pkg install gray-intel`，不需要手动下载。

装好后出现 `grayintel` 工具。

## 用法

```jsonc
// 普通检索
{ "query": "Claude 中转站", "limit": 20 }

// 只看论坛/社区
{ "query": "中转站 卖数据", "mode": "forum" }

// 看黑话扩展出来的词表
{ "query": "降智", "action": "expand" }

// 看可定向的站点
{ "query": "x", "action": "sites" }

// 给程序用
{ "query": "外挂 内存修改", "format": "json" }
```

### 参数

| 参数 | 说明 |
|---|---|
| `query` | 关键词，必填 |
| `action` | `search`（默认）/ `expand` / `sites` |
| `mode` | `all` / `web` / `forum` / `code` / `social` / `market` / `dark` |
| `engine` | `all`（Bing + 360）/ `bing` / `so360` / `ddg` / `sogou` |
| `site` | 额外指定一个站点，如 `linux.do` |
| `extra` | 追加关键词 |
| `limit` | 结果条数，默认 24 |
| `expand` | 是否自动扩展黑话，默认 true |
| `format` | `md` / `json` |

## 依赖

只用 Python 标准库。不需要 API key，不需要登录。

搜索引擎有频率限制，连续大量请求可能返回空结果，工具会自动重试一次。

## 许可

MIT © 2026 yxxbc
