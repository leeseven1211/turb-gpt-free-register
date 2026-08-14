import requests, logging, time

logger = logging.getLogger(__name__)
FLARESOLVERR_URL = "http://127.0.0.1:8191/v1"

def get_cf_cookies(timeout_ms: int = 30000) -> list[dict]:
    """通过 flaresolverr 获取 chatgpt.com 的 CF 清障 cookies"""
    try:
        resp = requests.post(
            FLARESOLVERR_URL,
            json={"cmd": "request.get", "url": "https://chatgpt.com/auth/login", "maxTimeout": timeout_ms},
            timeout=(timeout_ms / 1000) + 10
        )
        data = resp.json()
        if data.get("status") != "ok":
            logger.warning("flaresolverr non-ok: %s", data.get("message", "?"))
            return []
        cookies = data.get("solution", {}).get("cookies", [])
        logger.info("flaresolverr: %d CF-cleared cookies", len(cookies))
        return cookies
    except Exception as e:
        logger.warning("flaresolverr failed: %s", e)
        return []

def inject_cookies_via_cdp(driver, cookies: list[dict]) -> int:
    """通过 CDP 注入 cookies（不需要先加载目标域名）"""
    count = 0
    for c in cookies:
        try:
            # CDP Network.setCookie
            driver.execute_cdp_cmd("Network.setCookie", {
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ".chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", False),
                "httpOnly": c.get("httpOnly", False),
            })
            count += 1
        except Exception as e:
            logger.debug("CDP setCookie failed for %s: %s", c.get("name"), e)
    if count:
        logger.info("injected %d CF cookies via CDP", count)
    return count
