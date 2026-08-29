#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日自动抓取公开免费节点，生成 Clash 可识别的 yaml 文件
"""

import base64
import re
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml

# 公开免费源（会失效，脚本会自动跳过失败的）
SOURCES = [
    # Clash 直接可用的 yaml
    "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/clash.yaml",
    "https://raw.githubusercontent.com/yy1588133/proxy-pool/main/clash.yaml",
    "https://raw.githubusercontent.com/free-nodes/clashfree/main/clash.yml",
    # base64 / 纯文本节点（会尝试解析）
    "https://raw.githubusercontent.com/clashv2ray-hub/v2rayfree/main/v2ray.txt",
    "https://raw.githubusercontent.com/free-nodes/v2rayfree/main/sub",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200 and r.text.strip():
            return r.text.strip()
    except Exception as e:
        print(f"[跳过] {url} -> {e}")
    return None

def try_decode_base64(text: str) -> str:
    """尝试 base64 解码"""
    try:
        # 补齐 padding
        missing = len(text) % 4
        if missing:
            text += "=" * (4 - missing)
        decoded = base64.b64decode(text).decode("utf-8", errors="ignore")
        return decoded
    except Exception:
        return text

def extract_proxies_from_yaml(content: str) -> list:
    """从 Clash yaml 中提取 proxies"""
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "proxies" in data:
            return data["proxies"] or []
    except Exception:
        pass
    return []

def extract_uris(text: str) -> list[str]:
    """提取 ss/ssr/vmess/vless/trojan 等 URI"""
    pattern = r"(ss|ssr|vmess|vless|trojan|hysteria2?)://[^\s<>\"']+"
    return re.findall(pattern, text, re.IGNORECASE)

def uri_to_proxy(uri: str) -> dict | None:
    """把常见 URI 转成简单 Clash proxy（仅做基础转换，复杂协议可能不完整）"""
    try:
        if uri.startswith("ss://"):
            # 简化处理，很多客户端支持直接写 name + type + server 等，这里只做占位
            return {"name": f"ss-{uri[5:20]}", "type": "ss", "server": "0.0.0.0", "port": 1, "cipher": "aes-128-gcm", "password": "x"}
        # 其他协议同样简化，实际使用时建议用现成 yaml 源
        return None
    except Exception:
        return None

def main():
    print("开始抓取免费节点...")
    all_proxies = []
    seen = set()

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch, url): url for url in SOURCES}
        for fut in as_completed(futures):
            content = fut.result()
            if not content:
                continue

            # 1. 尝试当 Clash yaml 解析
            proxies = extract_proxies_from_yaml(content)
            if proxies:
                for p in proxies:
                    if not isinstance(p, dict):
                        continue
                    name = p.get("name") or p.get("server") or str(p)
                    key = f"{p.get('type')}-{p.get('server')}-{p.get('port')}-{name}"
                    if key not in seen:
                        seen.add(key)
                        all_proxies.append(p)
                continue

            # 2. 尝试 base64 / 纯文本 URI
            decoded = try_decode_base64(content)
            uris = extract_uris(decoded)
            # 这里不强制转换 URI（容易出错），只统计数量
            print(f"  发现 {len(uris)} 条 URI（来自文本源）")

    print(f"共收集到 {len(all_proxies)} 个可用 proxies")

    # 生成 Clash 配置
    beijing = timezone(timedelta(hours=8))
    now = datetime.now(beijing).strftime("%Y-%m-%d %H:%M:%S")

    config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "external-controller": "127.0.0.1:9090",
        "proxies": all_proxies[:800],  # 限制数量，避免过大
        "proxy-groups": [
            {
                "name": "🚀 节点选择",
                "type": "select",
                "proxies": ["♻️ 自动选择", "DIRECT"] + [p["name"] for p in all_proxies[:800] if "name" in p],
            },
            {
                "name": "♻️ 自动选择",
                "type": "url-test",
                "proxies": [p["name"] for p in all_proxies[:800] if "name" in p],
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
            },
        ],
        "rules": [
            "GEOIP,CN,DIRECT",
            "MATCH,🚀 节点选择",
        ],
    }

    with open("clash.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    # 更新 README
    readme = f"""# abaaba - 免费 Clash 节点订阅（自动更新）

> 更新时间（北京时间）：**{now}**  
> 当前节点数量：**{len(all_proxies[:800])}**

## 订阅地址（Clash 直接可用）

```
https://raw.githubusercontent.com/15605875200-spec/abaaba/main/clash.yaml
```

（如果 raw 打不开，可尝试加速：）
```
https://ghproxy.com/https://raw.githubusercontent.com/15605875200-spec/abaaba/main/clash.yaml
```

## 使用方法

1. 打开 Clash / Clash Verge / Clash Meta / FlClash 等客户端
2. 添加订阅 → 粘贴上面的链接 → 更新
3. 选择「🚀 节点选择」或「♻️ 自动选择」即可

## 说明

- 本仓库使用 GitHub Actions **每天自动更新**一次
- 节点全部来自公开免费源，稳定性无法保证，仅供学习测试
- 请勿用于非法用途
- 如需手动立即更新，可到 Actions 页面点击 Run workflow

## 免责声明

本项目仅用于技术学习和交流，所有节点均来自互联网公开分享，与本仓库作者无关。请遵守当地法律法规。
"""
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    print("完成！已生成 clash.yaml 和 README.md")

if __name__ == "__main__":
    main()
