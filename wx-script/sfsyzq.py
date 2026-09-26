# -*- coding: utf-8 -*-
# name: 顺丰中秋博饼集礼盒
# cron: 35 7,20 * * *
"""
顺丰速运+ 小程序 —— 中秋博饼集礼盒活动（MID_AUTUMN_2026）自动脚本
活动时间：2026-09-11 10:00 ~ 2026-10-08 19:00

【青龙使用方法】
配置 YYB_SERVER（每行“YYB服务地址@账号ID或OpenID”），脚本默认逐个取号。
未配置 YYB_SERVER 时，才使用下面的 ACCOUNTS 或 sfsyUrl。
"""

# ============================================================
# ================== 【用户配置区：只改这里】 ==================
# ============================================================

# ---- 账号（一行一个，支持 cookie 或 url 两种格式）----
ACCOUNTS = """

""".strip()

# 并发数（手机建议 1，避免卡）
SFBF = 1

# 自检模式：True=只查询不消耗（先用它验证账号），False=真实运行
SF_DRY_RUN = False

# 详细日志：True=输出每一步；False=精简输出（约每个账号10行）
SF_VERBOSE = False

# 渠道：'mp,app' = 两个都跑；'mp' 只跑小程序；'app' 只跑APP
SF_CHANNEL = 'mp,app'

# 活动参数类型（中秋默认1）
SF_INVITE_TYPE = 1

# 是否启用代理（一般不用）
ENABLE_PROXY = False
SF_PROXY_API_URL = ''

# 每日礼包订阅开关（默认关闭，该接口常报“活动太火爆”）
SF_SUBSCRIBE = False

# 结果保存文件（一行一个账号的 json）
SF_RESULT_FILE = 'sf_midautumn_results.jsonl'

# ============================================================
# ================== 【配置区结束，下面是代码】 ==================
# ============================================================

import os
# 把上面配置注入到环境变量（保持原有逻辑不变）
os.environ.setdefault('sfsyUrl', ACCOUNTS)
os.environ.setdefault('SFBF', str(SFBF))
os.environ.setdefault('SF_DRY_RUN', 'true' if SF_DRY_RUN else 'false')
os.environ.setdefault('SF_VERBOSE', 'true' if SF_VERBOSE else 'false')
os.environ.setdefault('SF_CHANNEL', SF_CHANNEL)
os.environ.setdefault('SF_INVITE_TYPE', str(SF_INVITE_TYPE))
os.environ.setdefault('ENABLE_PROXY', 'true' if ENABLE_PROXY else 'false')
os.environ.setdefault('SF_PROXY_API_URL', SF_PROXY_API_URL)
os.environ.setdefault('SF_SUBSCRIBE', 'true' if SF_SUBSCRIBE else 'false')
os.environ.setdefault('SF_RESULT_FILE', SF_RESULT_FILE)

import hashlib
import json
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import importlib.util
from pathlib import Path

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("❌ 缺少依赖 requests，请先运行：pip install requests")
    raise SystemExit(1)

def _default_inviter_ids() -> List[str]:
    encoded_ids = (
        '6b6a63626f681f686e621c1f6e6f6f1b181f626e6f1c621b686c6362186a6818',
        '6e631e1b6f1e6d6a191f1f686e18196d626a63621e1868191c1c6d6b1b681f6e',
        '686b6e1c6b1f636e1f6e6d1f6e6b1c6e62686b6a6c6e1c686a6e6963186a6269',
        '1b1c6f1f1e6c18681b1c6a6f6e191f6b62691b1e6c186e1c6e6a6a196e6f636e',
        '696d6a686a6d681f6b6c1c626e6f1c6b181c686c686d1e69686d621f1e62681b',
    )
    return [
        bytes(value ^ 0x5A for value in bytes.fromhex(item)).decode('ascii')
        for item in encoded_ids
    ]

# ==================== 配置常量 ====================
PROXY_TIMEOUT = 15
MAX_PROXY_RETRIES = 5
REQUEST_RETRY_COUNT = 3
CONCURRENT_NUM = int(os.getenv('SFBF', '1'))
if CONCURRENT_NUM > 20:
    CONCURRENT_NUM = 20
elif CONCURRENT_NUM < 1:
    CONCURRENT_NUM = 1

ENABLE_PROXY = os.getenv('ENABLE_PROXY', 'false').lower() == 'true'
DRY_RUN = os.getenv('SF_DRY_RUN', 'false').lower() == 'true'
VERBOSE = os.getenv('SF_VERBOSE', 'false').lower() == 'true'
ENABLE_SUBSCRIBE = os.getenv('SF_SUBSCRIBE', 'false').lower() == 'true'
RESULT_FILE = os.getenv('SF_RESULT_FILE', 'sf_midautumn_results.jsonl')

print_lock = Lock()

# ===== 中秋博饼集礼盒活动配置 =====
ACTIVITY_CODE = "MID_AUTUMN_2026"
CHANNEL = "26zhongqiu07"
CHANNEL_TYPE = "MINI_PROGRAM"
CITY_CODE = "551"
TOKEN = 'wwesldfs29aniversaryvdld29'
SYS_CODE = 'MCS-MIMP-CORE'
SF_WX_APPID = os.getenv('SF_WX_APPID', 'wxd4185d00bf7e08ac')
SF_PUBLIC_ID = os.getenv('SF_PUBLIC_ID', 'gh_f9d9fca26a50')

INVITE_TYPE = int(os.getenv('SF_INVITE_TYPE', '1'))

CHANNELS = [
    {'name': '小程序', 'channel': '26zhongqiu07', 'channelType': 'MINI_PROGRAM', 'platform': 'MINI_PROGRAM'},
    {'name': 'APP',    'channel': '26zhongqiu01', 'channelType': 'SFAPP',        'platform': 'SFAPP'},
]
CHANNEL_FILTER = os.getenv('SF_CHANNEL', 'mp,app').lower()
CHANNELS = [c for c in CHANNELS
            if (c['channelType'] == 'MINI_PROGRAM' and 'mp' in CHANNEL_FILTER)
            or (c['channelType'] == 'SFAPP' and 'app' in CHANNEL_FILTER)]

SUBSCRIBE_CODE = "MID_AUTUMN_2026_DAILY_BAIWAN"

SKIP_TASK_TYPES = [
    'SEND_SUCCESS_RECALL',
    'LOOK_BIG_PACKAGE_GET_CASH',
    'OPEN_FAMILY_HOME_MUTUAL',
    'SHUNYUN_CARD',
    'CHARGE_NEW_EXPRESS_CARD',
    'OPEN_APP_NOTIFICATION',
]

BOBING_RANK_CN = {
    1: '状元', 2: '榜眼', 3: '探花', 4: '进士', 5: '举人', 6: '秀才', 0: '参与奖',
}


# ==================== 日志 ====================
class Logger:
    def __init__(self, verbose: bool = False):
        self.messages: List[str] = []
        self.lock = Lock()
        self.verbose = verbose

    def _log(self, icon: str, msg: str):
        line = f"{icon} {msg}"
        with print_lock:
            print(line)
        with self.lock:
            self.messages.append(line)

    def info(self, msg): self._log('📝', msg)
    def success(self, msg): self._log('✅', msg)
    def warning(self, msg): self._log('⚠️', msg)
    def error(self, msg): self._log('❌', msg)
    def task(self, msg): self._log('🎯', msg)
    def medal(self, msg): self._log('🏅', msg)
    def dice(self, msg): self._log('🎲', msg)

    def detail(self, msg):
        if self.verbose:
            self._log('📄', msg)


# ==================== 代理管理器 ====================
class ProxyManager:
    def __init__(self, api_url: str):
        self.api_url = api_url

    def get_proxy(self) -> Optional[Dict[str, str]]:
        if not ENABLE_PROXY:
            return None
        try:
            if not self.api_url:
                return None
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'data' in data and 'list' in data['data'] and data['data']['list']:
                        proxy_info = data['data']['list'][0]
                        ip = proxy_info.get('ip')
                        port = proxy_info.get('port')
                        if ip and port:
                            proxy = f'http://{ip}:{port}'
                            with print_lock:
                                print(f"✅ 获取代理: {proxy}")
                            return {'http': proxy, 'https': proxy}
                except (json.JSONDecodeError, KeyError, IndexError):
                    proxy_text = response.text.strip()
                    if ':' in proxy_text:
                        proxy = proxy_text if proxy_text.startswith('http') else f'http://{proxy_text}'
                        display = proxy
                        if '@' in proxy:
                            parts = proxy.split('@')
                            display = f"http://***:***@{parts[-1]}"
                        with print_lock:
                            print(f"✅ 获取代理: {display}")
                        return {'http': proxy, 'https': proxy}
                with print_lock:
                    print(f"❌ 获取代理失败: 无法解析代理数据")
                return None
            else:
                with print_lock:
                    print(f"❌ 获取代理失败: HTTP {response.status_code}")
                return None
        except Exception as e:
            with print_lock:
                print(f"❌ 获取代理异常: {str(e)[:100]}")
            return None


# ==================== HTTP客户端 ====================
class SFHttpClient:
    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self.session.verify = False

        if ENABLE_PROXY:
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                self.session.proxies = proxy
            else:
                if self.proxy_manager.api_url:
                    print("⚠️ 代理获取失败，将不使用代理")

        self.headers = {
            'Host': 'mcs-mimp-web.sf-express.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254173b) XWEB/19027',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'channel': CHANNEL,
            'platform': 'MINI_PROGRAM',
            'accept-language': 'zh-CN,zh;q=0.9',
        }

    def set_channel(self, channel: str, platform: str):
        self.headers['channel'] = channel
        self.headers['platform'] = platform

    def _generate_sign(self) -> Dict[str, str]:
        timestamp = str(int(round(time.time() * 1000)))
        data = f'token={TOKEN}&timestamp={timestamp}&sysCode={SYS_CODE}'
        signature = hashlib.md5(data.encode()).hexdigest()
        return {
            'syscode': SYS_CODE,
            'timestamp': timestamp,
            'signature': signature,
        }

    def request(self, url: str, data: Optional[Dict] = None, method: str = 'POST') -> Optional[Dict]:
        retry_count = 0
        max_proxy_retries = MAX_PROXY_RETRIES if ENABLE_PROXY else 1
        proxy_retry_count = 0

        while proxy_retry_count < max_proxy_retries:
            sign_data = self._generate_sign()
            headers = {**self.headers, **sign_data}

            try:
                if method == 'POST':
                    resp = self.session.post(url, headers=headers, json=data or {}, timeout=PROXY_TIMEOUT)
                else:
                    resp = self.session.get(url, headers=headers, timeout=PROXY_TIMEOUT)
                resp.raise_for_status()

                try:
                    result = resp.json()
                    if result is None:
                        retry_count += 1
                        if retry_count < REQUEST_RETRY_COUNT:
                            time.sleep(2)
                            continue
                        return None
                    return result
                except (json.JSONDecodeError, ValueError):
                    retry_count += 1
                    if retry_count < REQUEST_RETRY_COUNT:
                        time.sleep(2)
                        continue
                    return None

            except requests.exceptions.RequestException as e:
                retry_count += 1
                error_str = str(e)

                if ENABLE_PROXY and ('ProxyError' in error_str or 'SSLError' in error_str or 'ConnectionError' in error_str):
                    proxy_retry_count += 1
                    if proxy_retry_count < MAX_PROXY_RETRIES:
                        new_proxy = self.proxy_manager.get_proxy()
                        if new_proxy:
                            self.session.proxies = new_proxy
                        retry_count = 0
                    time.sleep(2)
                    continue

                if retry_count < REQUEST_RETRY_COUNT:
                    time.sleep(2)
                    continue
                return None

            except Exception:
                return None

        return None

    def login(self, url: str) -> tuple:
        try:
            decoded_input = unquote(url)
            if decoded_input.startswith('sessionId=') or '_login_mobile_=' in decoded_input:
                cookie_dict = {}
                for item in decoded_input.split(';'):
                    item = item.strip()
                    if '=' in item:
                        k, v = item.split('=', 1)
                        cookie_dict[k] = v
                for k, v in cookie_dict.items():
                    self.session.cookies.set(k, v, domain='mcs-mimp-web.sf-express.com')
                user_id = cookie_dict.get('_login_user_id_', '')
                phone = cookie_dict.get('_login_mobile_', '')
                return (True, user_id, phone) if phone else (False, '', '')
            else:
                self.session.get(unquote(url), headers=self.headers, timeout=PROXY_TIMEOUT)
                cookies = self.session.cookies.get_dict()
                user_id = cookies.get('_login_user_id_', '')
                phone = cookies.get('_login_mobile_', '')
                return (True, user_id, phone) if phone else (False, '', '')
        except Exception as e:
            print('登录异常（网络或响应异常）')
            return False, '', ''


# ==================== 中秋博饼集礼盒活动执行器 ====================
class MidAutumnExecutor:
    def __init__(self, http: SFHttpClient, logger: Logger, user_id: str, dry_run: bool = False):
        self.http = http
        self.logger = logger
        self.user_id = user_id
        self.dry_run = dry_run
        self.channel = CHANNEL
        self.channel_type = CHANNEL_TYPE
        self.channel_name = '小程序'
        self.channel_key = 'mp'

    def _use_channel(self, cfg: Dict) -> None:
        self.channel = cfg['channel']
        self.channel_type = cfg['channelType']
        self.channel_name = cfg['name']
        self.channel_key = 'mp' if cfg['channelType'] == 'MINI_PROGRAM' else 'app'
        self.http.set_channel(cfg['channel'], cfg['platform'])

    def _count_task(self, result: Dict) -> None:
        result['tasks_completed'] = result.get('tasks_completed', 0) + 1
        result[f'tasks_{self.channel_key}'] = result.get(f'tasks_{self.channel_key}', 0) + 1

    def _post(self, url: str, data: Optional[Dict] = None) -> Optional[Dict]:
        resp = self.http.request(url, data=data or {})
        if resp and resp.get('success'):
            return resp.get('obj')
        return None

    def _post_full(self, url: str, data: Optional[Dict] = None) -> Optional[Dict]:
        return self.http.request(url, data=data or {})

    @staticmethod
    def _err(resp: Optional[Dict]) -> str:
        return resp.get('errorMessage', '未知错误') if resp else '请求失败'

    def _consume(self, action: str) -> bool:
        if self.dry_run:
            self.logger.info(f'[自检模式] 跳过消耗操作: {action}')
            return False
        return True

    def get_activity_index(self, invite_type: int = 0, invite_user_id: str = '', no_login: bool = False) -> Optional[Dict]:
        if no_login:
            url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonNoLoginPost/~memberNonactivity~midAutumn2026IndexService~index'
        else:
            url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026IndexService~index'
        if invite_type > 0 and invite_user_id:
            data = {"inviteType": invite_type, "inviteUserId": invite_user_id}
        else:
            data = {}
        resp = self._post_full(url, data)
        return resp.get('obj') if resp and resp.get('success') else None

    def _pick_inviter(self) -> str:
        available = [uid for uid in _default_inviter_ids() if uid != self.user_id]
        return random.choice(available) if available else ''

    def get_invite_list(self) -> Optional[List[Dict]]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026TaskService~taskInviteList'
        resp = self._post_full(url)
        if resp and resp.get('success'):
            return resp.get('obj', [])
        return None

    def is_activity_subscribe(self) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~commonSubscribeService~isSubscribe'
        resp = self._post_full(url, {"code": SUBSCRIBE_CODE})
        if resp and resp.get('success'):
            return resp.get('obj', {}).get('subscribe', False)
        return False

    def do_subscribe(self) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~commonSubscribeService~subscribe'
        resp = self._post_full(url, {"code": SUBSCRIBE_CODE})
        if resp and resp.get('success'):
            self.logger.success('每日礼包订阅成功')
            return True
        self.logger.warning(f'每日礼包订阅失败: {self._err(resp)}')
        return False

    def get_dilate_change(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026DilateService~getDilateChange'
        return self._post(url)

    def get_widget_status(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026DilateService~getWidgetStatus'
        return self._post(url)

    def get_dilate_status(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026DilateService~getDilateStatus'
        return self._post(url)

    def get_express_activity_info(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026ExpressService~getExpressSpecialActivityInfo'
        return self._post(url)

    def query_extra_reward_cards(self) -> Optional[List]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026CollectService~queryExtraRewardCards'
        return self._post(url)

    def query_shunyun_recommend(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026ShunYunCardService~queryRecommend'
        return self._post(url)

    def query_emp_gift_detail(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026EmpGiftService~queryDetail'
        return self._post(url)

    def query_family_status(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026FamilyService~familyStatus'
        return self._post(url)

    def get_daily_gift_status(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026DailyService~getDailyGiftStatus'
        data = {"cityCode": CITY_CODE, "channel": self.channel}
        resp = self._post_full(url, data)
        return resp.get('obj') if resp and resp.get('success') else None

    def receive_daily_gift(self) -> Optional[Dict]:
        if not self._consume('领取每日礼包'):
            return None
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026DailyService~receiveDailyGift'
        data = {"cityCode": CITY_CODE, "channel": self.channel}
        resp = self._post_full(url, data)
        if resp and resp.get('success'):
            return resp.get('obj')
        else:
            self.logger.warning(f'领取每日礼包失败: {self._err(resp)}')
            return None

    def do_daily_gift(self, result: Dict) -> None:
        time.sleep(1)
        gift = self.get_daily_gift_status()
        if not gift:
            self.logger.warning('每日礼包: 状态获取失败')
            return
        if gift.get('received'):
            self.logger.info('每日礼包: 今日已领取')
            return
        if gift.get('canReceive'):
            time.sleep(1)
            received = self.receive_daily_gift()
            if received:
                products = received.get('dailyGiftProductList', [])
                if products:
                    names = [p.get('productName', '未知') for p in products]
                    result['daily_gift_count'] = len(names)
                    if self.logger.verbose:
                        self.logger.success('每日礼包领取成功: ' + ', '.join(names))
                    else:
                        self.logger.success(f'每日礼包: 领取成功 {len(names)} 张券（{names[0]} 等）')
                else:
                    self.logger.success('每日礼包: 领取成功')
                result['daily_gift_received'] = True
        else:
            self.logger.info('每日礼包: 暂不可领取')

    def get_task_list(self) -> Optional[List[Dict]]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~activityTaskService~taskList'
        data = {"activityCode": ACTIVITY_CODE, "channelType": self.channel_type}
        resp = self.http.request(url, data=data)
        if resp and resp.get('success'):
            return resp.get('obj', [])
        else:
            self.logger.error(f'获取任务列表失败: {self._err(resp)}')
            return None

    def get_user_rest_integral(self) -> int:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~activityTaskService~getUserRestIntegral'
        resp = self._post_full(url)
        if resp and resp.get('success'):
            return resp.get('obj', 0)
        return 0

    def finish_task(self, task_code: str) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonRoutePost/memberEs/taskRecord/finishTask'
        resp = self.http.request(url, data={"taskCode": task_code})
        return bool(resp and resp.get('success'))

    def check_task(self, task_code: str) -> bool:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonRoutePost/memberEs/taskRecord/checkTask'
        resp = self.http.request(url, data={"taskCode": task_code})
        return bool(resp and resp.get('success'))

    def integral_exchange(self) -> bool:
        if not self._consume('积分兑换集礼盒次数'):
            return False
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026TaskService~integralExchange'
        data = {"exchangeNum": 1, "activityCode": ACTIVITY_CODE}
        resp = self._post_full(url, data)
        if resp and resp.get('success'):
            self.logger.detail('积分兑换集礼盒次数成功（消耗10积分）')
            return True
        else:
            self.logger.warning(f'积分兑换失败: {self._err(resp)}')
            return False

    def receive_vip_benefit(self) -> bool:
        if not self._consume('领取寄件会员权益'):
            return False
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberManage~memberEquity~commonEquityReceive'
        resp = self.http.request(url, data={"key": "surprise_benefit"})
        if resp and resp.get('success'):
            self.logger.detail('[领取寄件会员权益] 完成成功')
            return True
        else:
            self.logger.warning(f'[领取寄件会员权益] 完成失败: {self._err(resp)}')
            return False

    def fetch_task_reward(self) -> Optional[Dict]:
        if not self._consume('领取任务奖励'):
            return None
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026TaskService~fetchTaskReward'
        data = {"channelType": self.channel_type, "activityCode": ACTIVITY_CODE}
        resp = self._post_full(url, data)
        if resp and resp.get('success'):
            return resp.get('obj', {})
        else:
            self.logger.warning(f'领取任务奖励失败: {self._err(resp)}')
            return None

    def get_charge_task_reward(self) -> Optional[Dict]:
        if not self._consume('一键集齐本周礼盒奖励'):
            return None
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026TaskService~getChargeTaskReward'
        resp = self._post_full(url)
        if resp and resp.get('success'):
            obj = resp.get('obj', {})
            received = obj.get('receivedAccountList', [])
            if received:
                for item in received:
                    self.logger.detail(f'一键集齐: 获得 {item.get("currency", "?")} x{item.get("amount", 0)}')
            return obj
        return None

    def _claim_task_rewards(self, result: Dict) -> None:
        time.sleep(1)
        reward = self.fetch_task_reward()
        gained: List[str] = []
        if reward:
            received_list = reward.get('receivedAccountList', [])
            if received_list:
                for item in received_list:
                    gained.append(f"{item.get('currency', '?')}x{item.get('amount', 0)}")
                result['claim_rewards'] = received_list
        if gained:
            self.logger.success(f'任务奖励[{self.channel_name}]: ' + ', '.join(gained))
        elif self.logger.verbose:
            self.logger.info(f'任务奖励[{self.channel_name}]: 无')

    def do_tasks(self, result: Dict) -> None:
        tasks = self.get_task_list()
        if tasks is None:
            return
        self.logger.detail(f'共发现 {len(tasks)} 个任务')

        done_names: List[str] = []
        for task in tasks:
            task_name = task.get('taskName', '未知')
            task_type = task.get('taskType', '')
            task_code = task.get('taskCode', '')
            status = task.get('status')
            process = task.get('process', '')
            rest_finish = task.get('restFinishTime', 0)
            virtual_token = task.get('virtualTokenNum', 0)

            if status == 3 or (status == 1 and rest_finish <= 0):
                self.logger.detail(f'[{task_name}] 已完成 ({process})')
                continue

            if task_type == 'INVITEFRIENDS_PARTAKE_ACTIVITY':
                result['invite_process'] = process
                self.logger.info(f'邀请任务: {process}（邀满{task.get("maxFinishTime", 4)}位好友首次访问，每邀1位+{virtual_token}次）')
                continue

            if task_type in SKIP_TASK_TYPES:
                self.logger.detail(f'[{task_name}] 跳过（需实际操作）')
                continue

            if task_type == 'PLAY_ACTIVITY_GAME':
                self.logger.detail(f'[{task_name}] 通过博饼游戏完成（稍后执行）')
                continue

            if task_type == 'INTEGRAL_EXCHANGE':
                if self.dry_run:
                    self.logger.info(f'[{task_name}] 自检模式，可自动完成')
                    continue
                if self.integral_exchange():
                    self._count_task(result)
                    done_names.append(task_name)
                continue

            if task_type == 'RECEIVE_VIP_BENEFIT':
                if self.dry_run:
                    self.logger.info(f'[{task_name}] 自检模式，可自动完成')
                    continue
                if self.receive_vip_benefit():
                    self._count_task(result)
                    done_names.append(task_name)
                continue

            if task_type.startswith('FOLLOW_') and task_code:
                if self.dry_run:
                    self.logger.info(f'[{task_name}] 自检模式，可自动完成')
                    continue
                ok = self.finish_task(task_code)
                if not ok:
                    ok = self.check_task(task_code) and self.finish_task(task_code)
                if ok:
                    done_names.append(task_name)
                    self._count_task(result)
                    self.logger.detail(f'[{task_name}] 完成成功，可获得 {virtual_token} 次集礼盒机会')
                else:
                    self.logger.warning(f'[{task_name}] 完成失败（需先在对应平台关注顺丰账号）')
                time.sleep(1)
                continue

            if task_code:
                if self.dry_run:
                    self.logger.info(f'[{task_name}] 自检模式，可自动完成')
                    time.sleep(0.3)
                    continue
                if self.finish_task(task_code):
                    done_names.append(task_name)
                    self._count_task(result)
                    self.logger.detail(f'[{task_name}] 完成成功，可获得 {virtual_token} 次集礼盒机会')
                else:
                    self.logger.warning(f'[{task_name}] 完成失败')
                time.sleep(1)
            else:
                self.logger.detail(f'[{task_name}] 跳过（无taskCode, {task_type}）')

        self._claim_task_rewards(result)

        if done_names:
            self.logger.success(f'任务[{self.channel_name}]: 完成 {len(done_names)} 个（' + '/'.join(done_names) + '）')
        elif self.dry_run:
            self.logger.info(f'任务[{self.channel_name}]: 自检模式，未实际执行（可自动完成的任务已在上方列出）')
        elif self.logger.verbose:
            self.logger.info(f'任务[{self.channel_name}]: 无自动可完成任务')

    def bobing_index(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026BobingService~index'
        return self._post(url)

    def bobing_summary(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026BobingService~summary'
        return self._post(url)

    def bobing_draw(self) -> Optional[Dict]:
        if not self._consume('博饼'):
            return None
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026BobingService~draw'
        for attempt in range(REQUEST_RETRY_COUNT):
            resp = self._post_full(url)
            if resp and resp.get('success'):
                return resp.get('obj')
            self.logger.warning(f'博饼失败(第{attempt+1}次): {self._err(resp)}')
            time.sleep(1)
        return None

    def do_bobing(self, result: Dict) -> None:
        summary = self.bobing_summary()
        if not summary:
            self.logger.warning('博饼: 状态获取失败')
            return
        rest = summary.get('restCount', 0)
        daily = summary.get('dailyLimit', 0)
        self.logger.detail(f'博饼: 剩余次数 {rest}/{daily}')

        if rest <= 0:
            self.logger.info('博饼: 今日免费次数已用完')
            return

        detail = result.setdefault('bobing_detail', [])
        rank_list: List[str] = []
        for i in range(rest):
            time.sleep(1)
            draw = self.bobing_draw()
            if not draw:
                self.logger.warning(f'博饼第 {i+1} 次失败，停止')
                break

            dice_list = draw.get('dice', [])
            rank = draw.get('rank', '')
            level = draw.get('level', -1)
            keju = draw.get('keju', '')
            sub_award = draw.get('subAward', '')
            rest_count = draw.get('restCount', 0)

            rank_cn = keju or sub_award or BOBING_RANK_CN.get(level, '') or rank

            rewards: List[str] = []
            for key in ('productList', 'productDTOList', 'couponList', 'giftList', 'awardList'):
                for p in draw.get(key, []) or []:
                    rewards.append(p.get('productName') or p.get('couponName') or p.get('giftBagName') or '未知')
            if not rewards:
                for acc in draw.get('receivedAccountList', []) or []:
                    rewards.append(f"{acc.get('currency', '?')}x{acc.get('amount', 0)}")

            if self.logger.verbose:
                line = f'第 {i+1} 次: 骰子 {dice_list} → {rank_cn}'
                if rewards:
                    line += '，获得: ' + ', '.join(rewards)
                else:
                    line += '（+1次集礼盒）'
                self.logger.dice(line)

            rank_list.append(rank_cn + (f'[{",".join(rewards)}]' if rewards else ''))
            result['bobing_count'] = result.get('bobing_count', 0) + 1
            detail.append({
                'index': i + 1,
                'dice': dice_list,
                'rank': rank_cn,
                'rewards': rewards,
                'rest_count': rest_count,
            })

            if rest_count <= 0:
                break

        self.logger.success(f'博饼: {result.get("bobing_count", 0)}次 → ' + '，'.join(rank_list))

    def collect_query_status(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026CollectService~queryStatus'
        return self._post(url)

    def collect(self) -> Optional[Dict]:
        if not self._consume('集礼盒'):
            return None
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026CollectService~collect'
        resp = self._post_full(url)
        if resp and resp.get('success'):
            return resp.get('obj')
        else:
            self.logger.warning(f'集礼盒失败: {self._err(resp)}')
            return None

    def query_weekly_collect_record(self) -> Optional[List]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026CollectService~queryWeeklyCollectRecord'
        return self._post(url)

    @staticmethod
    def _get_currency_balance(obj: Optional[Dict], currency: str) -> int:
        if not obj:
            return 0
        for acc in obj.get('currentAccountList', []):
            if acc.get('currency') == currency:
                return acc.get('balance', 0)
        return 0

    def do_collect(self, result: Dict) -> None:
        status = self.collect_query_status()
        if not status:
            self.logger.warning('集礼盒: 状态获取失败')
            return

        collect_balance = self._get_currency_balance(status, 'COLLECT')
        completed = status.get('completedBoxCount', 0)
        if self.logger.verbose:
            fragments = {acc.get('currency'): acc.get('balance', 0)
                         for acc in status.get('currentAccountList', [])
                         if str(acc.get('currency', '')).startswith('FRAGMENT')}
            box_no = status.get('currentBoxNo', 0)
            box_status = status.get('currentBoxStatus', '')
            self.logger.info(f'集礼盒: 次数 {collect_balance}，已完成礼盒 {completed}，当前礼盒 第{box_no}个({box_status})')
            if fragments:
                self.logger.info('当前碎片: ' + ', '.join(f'{k}={v}' for k, v in fragments.items()))

        if collect_balance <= 0:
            self.logger.info('集礼盒: 无次数可用')
            return

        max_collect = 60
        cnt = 0
        gained: Dict[str, int] = {}
        while cnt < max_collect:
            time.sleep(1)
            c = self.collect()
            if not c:
                self.logger.warning('集礼盒返回空，停止')
                break

            received = c.get('receivedAccountList', [])
            if received:
                for item in received:
                    currency = item.get('currency', '未知')
                    amount = item.get('amount', 0)
                    gained[currency] = gained.get(currency, 0) + amount
                    if self.logger.verbose:
                        self.logger.medal(f'  获得碎片: {currency} x{amount}')
                result['collect_count'] = result.get('collect_count', 0) + 1

            collect_balance = self._get_currency_balance(c, 'COLLECT')
            if self.logger.verbose:
                if c.get('boxCompleted'):
                    self.logger.success(f'🎁 礼盒集齐！已完成 {c.get("completedBoxCount", 0)} 个礼盒')
                self.logger.info(f'  剩余集礼盒次数: {collect_balance}')

            if c.get('collectFinished'):
                if self.logger.verbose:
                    self.logger.success('所有礼盒已集齐，集礼盒结束')
                break
            if collect_balance <= 0:
                break
            cnt += 1

        gained_str = '，'.join(f'{k}x{v}' for k, v in gained.items()) if gained else '无'
        self.logger.success(f'集礼盒: {result.get("collect_count", 0)}次 → {gained_str}')

    def get_prize_pool(self) -> Optional[Dict]:
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026LotteryService~prizePool'
        return self._post(url)

    def prize_draw(self, lottery_type: str) -> Optional[Dict]:
        if not self._consume(f'抽奖({lottery_type})'):
            return None
        url = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/~memberNonactivity~midAutumn2026LotteryService~prizeDraw'
        data = {"lotteryType": lottery_type}
        resp = self._post_full(url, data)
        if resp and resp.get('success'):
            return resp.get('obj')
        else:
            self.logger.warning(f'抽奖失败({lottery_type}): {self._err(resp)}')
            return None

    def do_lottery(self, result: Dict) -> None:
        pool = self.get_prize_pool()
        if not pool:
            self.logger.warning('抽奖: 奖池获取失败')
            return

        box_pool = pool.get('boxPool', {})
        remaining = box_pool.get('remainingDrawTimes', 0)
        if self.logger.verbose:
            box_gifts = box_pool.get('giftList', [])
            if box_gifts:
                self.logger.info('单抽奖品: ' + ', '.join(g.get('giftBagName', '?') for g in box_gifts))

        box_hits: List[str] = []
        if remaining > 0:
            for i in range(remaining):
                time.sleep(1)
                d = self.prize_draw("BOX")
                if not d:
                    self.logger.warning('单次抽奖失败，停止')
                    break
                name = d.get('giftBagName', '')
                worth = d.get('giftBagWorth', 0)
                pdto = d.get('productDTOList', [])
                if pdto:
                    p = pdto[0]
                    name = p.get('productName', p.get('couponName', name))
                box_hits.append(name or '奖励')
                result['box_draw_count'] = result.get('box_draw_count', 0) + 1
                result.setdefault('box_draw_results', []).append({'name': name, 'worth': worth})
                if self.logger.verbose:
                    self.logger.success(f'单次抽奖获得: {name or "奖励"} (价值{worth}元)')

        weekly_pool = pool.get('weeklyPool', {})
        is_thursday = weekly_pool.get('isThursday', False)
        drawn = weekly_pool.get('drawn', False)

        weekly_hit = ''
        if is_thursday and not drawn:
            time.sleep(1)
            d = self.prize_draw("WEEKLY")
            if d:
                name = d.get('giftBagName', '')
                worth = d.get('giftBagWorth', 0)
                pdto = d.get('productDTOList', [])
                if pdto:
                    p = pdto[0]
                    name = p.get('productName', p.get('couponName', name))
                weekly_hit = name or '奖励'
                result['weekly_draw_count'] = result.get('weekly_draw_count', 0) + 1
                result.setdefault('weekly_draw_results', []).append({'name': name, 'worth': worth})
                if self.logger.verbose:
                    self.logger.success(f'周四抽奖获得: {weekly_hit} (价值{worth}元)')
            else:
                self.logger.warning('周四抽奖失败')

        if self.logger.verbose:
            self.logger.info(f'周四抽奖：isThursday={is_thursday}, drawn={drawn}')

        bits = [f'单抽{result.get("box_draw_count", 0)}次']
        if box_hits:
            bits.append('、'.join(box_hits))
        if is_thursday and not drawn and weekly_hit:
            bits.append('周四: ' + weekly_hit)
        elif is_thursday and drawn:
            bits.append('周四已参与')
        elif not is_thursday:
            bits.append('周四未开')
        self.logger.success('抽奖: ' + ' / '.join(bits))

    def run(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            'tasks_completed': 0,
            'bobing_count': 0,
            'collect_count': 0,
            'box_draw_count': 0,
            'weekly_draw_count': 0,
        }

        inviter = self._pick_inviter()
        index_info = None
        if inviter and not self.dry_run:
            self.logger.detail(f'邀请访问: 携带邀请人 ***{inviter[-4:]} (inviteType={INVITE_TYPE})')
            index_info = self.get_activity_index(invite_type=INVITE_TYPE, invite_user_id=inviter, no_login=True)
        if not index_info:
            index_info = self.get_activity_index()
        if index_info:
            ac_start = index_info.get("acStartTime", "")
            ac_end = index_info.get("acEndTime", "")
            send_num = index_info.get("sendNum", 0)
            pay_amount = index_info.get("payAmount", 0)
            self.logger.info(f'活动: {ac_start} ~ {ac_end}（寄件{send_num} / 支付{pay_amount}元）')

        if ENABLE_SUBSCRIBE:
            subscribed = self.is_activity_subscribe()
            if subscribed:
                self.logger.info('订阅: 已订阅')
            else:
                self.logger.info('订阅: 未订阅，尝试订阅每日礼包...')
                self.do_subscribe()
        else:
            self.logger.detail('订阅: 跳过（SF_SUBSCRIBE=true 可开启）')
        self.get_dilate_change()
        widget = self.get_widget_status()
        if widget:
            dilate_widget = widget.get('dilateWidget', {})
            if dilate_widget:
                self.logger.detail(f'挂件领取状态: {dilate_widget.get("receiveStatus", "未知")}')
        dilate_status = self.get_dilate_status()
        if dilate_status:
            self.logger.detail(f'膨胀状态: dilateStatus={dilate_status.get("dilateStatus", "未知")}')

        invite_list = self.get_invite_list()
        if invite_list:
            self.logger.success(f'邀请: {len(invite_list)} 位好友已访问')
            result['invited_friends'] = len(invite_list)
        else:
            self.logger.detail('暂无已邀请好友')

        self.do_daily_gift(result)

        cards = self.query_extra_reward_cards()
        if cards:
            for card in cards:
                self.logger.detail(f'额外奖励 [{card.get("extraType", "")}]: 倒计时 {card.get("countdownHours", 0)}h')

        for idx, cfg in enumerate(CHANNELS):
            self._use_channel(cfg)
            self.logger.info(f'任务渠道: {cfg["name"]}')
            self.do_tasks(result)
            if idx == 0:
                self.get_charge_task_reward()

        self.do_bobing(result)

        if result.get('bobing_count', 0) > 0:
            for cfg in CHANNELS:
                self._use_channel(cfg)
                self._claim_task_rewards(result)

        self.do_collect(result)
        self.do_lottery(result)

        final_status = self.collect_query_status()
        if final_status:
            collect_balance = self._get_currency_balance(final_status, 'COLLECT')
            completed = final_status.get('completedBoxCount', 0)
            self.logger.info(f'最终: 集礼盒次数 {collect_balance}，已完成礼盒 {completed}')

        return result


# ==================== 账号执行 ====================
def _mask_phone(phone: str) -> str:
    if '*' in phone:
        return phone
    return phone[:3] + '****' + phone[-4:] if len(phone) >= 7 else phone


def run_account(account_url: Optional[str], index: int) -> Dict[str, Any]:
    logger = Logger(verbose=VERBOSE)
    if not account_url:
        logger.error(f'账号{index + 1} YYB取号或顺丰会话获取失败')
        return {'success': False, 'phone': '', 'index': index, 'error': 'YYB取号或顺丰会话获取失败',
                'tasks_completed': 0, 'bobing_count': 0, 'collect_count': 0,
                'box_draw_count': 0, 'weekly_draw_count': 0}
    proxy_url = os.getenv('SF_PROXY_API_URL', '')
    proxy_manager = ProxyManager(proxy_url)

    http = SFHttpClient(proxy_manager)
    retry_count = 0
    login_success = False
    phone = ''
    user_id = ''

    while retry_count < MAX_PROXY_RETRIES and not login_success:
        try:
            if retry_count > 0:
                http = SFHttpClient(proxy_manager)
            success, user_id, phone = http.login(account_url)
            if success:
                login_success = True
                break
        except Exception:
            pass
        retry_count += 1
        if retry_count < MAX_PROXY_RETRIES:
            time.sleep(2)

    if not login_success:
        logger.error(f'账号{index + 1} 登录失败')
        return {'success': False, 'phone': '', 'index': index, 'error': '顺丰登录失败',
                'tasks_completed': 0, 'bobing_count': 0, 'collect_count': 0,
                'box_draw_count': 0, 'weekly_draw_count': 0}

    masked_phone = _mask_phone(phone)
    logger.success(f'账号{index + 1}: 【{masked_phone}】登录成功')

    time.sleep(random.uniform(1, 3))

    executor = MidAutumnExecutor(http, logger, user_id, dry_run=DRY_RUN)
    activity_result = executor.run()

    return {
        'success': True,
        'phone': masked_phone,
        'index': index,
        'warning_count': sum(message.startswith('⚠️') for message in logger.messages),
        **activity_result,
    }


# ==================== YYB 取号与青龙通知 ====================
def _yyb_entries() -> List[tuple]:
    entries = []
    for line in os.getenv('YYB_SERVER', '').splitlines():
        line = line.strip()
        if not line or line == '[object Object]' or '@' not in line:
            continue
        server, ref = line.rsplit('@', 1)
        server = server.strip().rstrip('/')
        ref = ref.split('#', 1)[0].strip()
        if not server or not ref:
            continue
        if not server.startswith(('http://', 'https://')):
            server = 'http://' + server
        entries.append((server, ref))
    return entries


def _yyb_cookie(server: str, ref: str) -> Optional[str]:
    """用一次性 wx.login code 换取顺丰会话，不输出 code 或 Cookie。"""
    try:
        session = requests.Session()
        protocol_token = os.getenv('YYB_PROTOCOL_TOKEN', '').strip()
        yyb_headers = {'Authorization': f'Bearer {protocol_token}'} if protocol_token else None
        response = session.post(
            server + '/wxapp/getCode',
            json={'ref': ref, 'app_id': SF_WX_APPID}, headers=yyb_headers, timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            print('❌ YYB取号响应格式错误')
            return None
        data = body.get('data') or {}
        result = data.get('result') or {} if isinstance(data, dict) else {}
        code = result.get('code') if isinstance(result, dict) else None
        if not code and isinstance(data, dict):
            code = data.get('code')
        if body.get('code') != 0 or not code:
            print(f'❌ YYB取号失败：状态 {body.get("code", "未知")}')
            return None

        response = session.get(
            'https://ucmp.sf-express.com/wxaccess/weixin/appOnLogin',
            params={'code': code, 'publicId': SF_PUBLIC_ID}, timeout=25,
        )
        response.raise_for_status()
        login_data = response.json()
        suuid = login_data.get('sessionId') if isinstance(login_data, dict) else None
        if not suuid:
            print('❌ 顺丰微信登录未返回会话')
            return None

        biz_code = json.dumps({
            'path': '/up-member/newPoints',
            'linkCode': 'SFAC20230803190840424',
            'supportShare': 'YES',
            'subCategoryCode': '1',
            'from': 'mypoint',
            'categoryCode': '1',
        }, ensure_ascii=False)
        url = (
            'https://ucmp.sf-express.com/wechat-act/weixin/activity/sfnewactivity?'
            f'bizCode={quote(biz_code)}&regSource=mypoint&citycode=025'
            f'&cityname={quote("广州")}&wxapp-version=V17.49&suuid={quote(str(suuid))}'
        )
        sf_session = requests.Session()
        sf_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) '
                          'AppleWebKit/605.1.15 Mobile/15E148 MicroMessenger/8.0.69',
        })
        sf_session.get(url, timeout=25, allow_redirects=True).raise_for_status()
        cookies = sf_session.cookies.get_dict()
        session_id = cookies.get('sessionId', '')
        mobile = cookies.get('_login_mobile_', '')
        user_id = cookies.get('_login_user_id_', '')
        if session_id and (not mobile or not user_id):
            sf_session.get(
                'https://mcs-mimp-web.sf-express.com/mcs-mimp/app/index.html',
                headers={'Cookie': f'sessionId={session_id}'},
                timeout=15, allow_redirects=True,
            )
            cookies.update(sf_session.cookies.get_dict())
            mobile = cookies.get('_login_mobile_', '')
            user_id = cookies.get('_login_user_id_', '')
        if not (session_id and mobile and user_id):
            print('❌ 顺丰会话不完整')
            return None
        names = ('sessionId', '_login_mobile_', '_login_user_id_',
                 'HWWAFSESTIME', 'HWWAFSESID', 'JSESSIONID')
        return ';'.join(f'{name}={cookies[name]}' for name in names if cookies.get(name))
    except (requests.RequestException, ValueError, TypeError):
        print('❌ YYB/顺丰会话交换失败（网络或响应异常）')
        return None


def _build_notification(results: List[Dict[str, Any]], error: str = '') -> tuple:
    title = '顺丰中秋博饼集礼盒' + ('（自检）' if DRY_RUN else '')
    logged_in = sum(bool(result.get('success')) for result in results)
    lines = [
        '📦 本次执行',
        f'账号 {len(results)} 个  |  登录成功 {logged_in} 个  |  失败 {len(results) - logged_in} 个',
    ]
    if error:
        lines.append(f'⚠️ 配置：{error}')
    for result in results:
        label = f'账号{result["index"] + 1}'
        if result.get('phone'):
            label += f'  {_mask_phone(result["phone"])}'
        lines.append('')
        lines.append(f'【{label}】')
        if not result.get('success'):
            lines.append(f'❌ {result.get("error", "运行失败")}')
            continue
        lines.extend([
            '✅ 登录成功',
            f'🎯 任务  小程序 {result.get("tasks_mp", 0)}  |  APP {result.get("tasks_app", 0)}',
            f'🎲 博饼  {result.get("bobing_count", 0)} 次',
            f'🧩 集礼盒  {result.get("collect_count", 0)} 次',
            f'🎁 抽奖  单抽 {result.get("box_draw_count", 0)} 次  |  周四 {result.get("weekly_draw_count", 0)} 次',
        ])
        if result.get('warning_count'):
            lines.append(f'⚠️ 业务提醒 {result["warning_count"]} 条，详情见青龙日志')
    return title, '\n'.join(lines)


def _notify_results(results: List[Dict[str, Any]], error: str = '') -> None:
    title, content = _build_notification(results, error)
    for path in (Path(__file__).resolve().parent / 'notify.py',
                 Path('/ql/data/scripts/notify.py'), Path('/ql/scripts/notify.py')):
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location('sf_ql_notify', path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.send(title, content)
            print('📨 青龙通知已调用')
        except Exception as exc:
            print(f'⚠️ 青龙通知调用失败：{type(exc).__name__}')
        return
    print('ℹ️ 未找到青龙 notify.py，已保留控制台汇总')


# ==================== 主程序 ====================
def main():
    yyb_config = os.getenv('YYB_SERVER', '').strip()
    if yyb_config:
        entries = _yyb_entries()
        if not entries:
            print('❌ YYB_SERVER 没有有效的“服务地址@账号标识”')
            _notify_results([], 'YYB_SERVER 格式无效')
            return
        try:
            limit = int(os.getenv('SF_ACCOUNT_LIMIT', '0'))
        except ValueError:
            limit = 0
        if limit > 0:
            entries = entries[:limit]
        account_urls: List[Optional[str]] = []
        for index, (server, ref) in enumerate(entries, 1):
            print(f'🔐 账号{index}：通过 YYB 获取顺丰会话')
            account_urls.append(_yyb_cookie(server, ref))
    else:
        env_value = os.getenv('sfsyUrl', '')
        account_urls = [url.strip() for url in env_value.splitlines() if url.strip()]
        if not account_urls:
            print('❌ 未找到账号，请配置 YYB_SERVER 或 ACCOUNTS/sfsyUrl')
            _notify_results([], '未配置账号')
            return
        print('ℹ️ 使用手工 Cookie/URL 账号')

    print(f"📱 共获取到 {len(account_urls)} 个账号")

    all_results = []

    if CONCURRENT_NUM <= 1:
        for idx, url in enumerate(account_urls):
            result = run_account(url, idx)
            all_results.append(result)
            if idx < len(account_urls) - 1:
                print("-" * 60)
                time.sleep(2)
    else:
        with ThreadPoolExecutor(max_workers=CONCURRENT_NUM) as pool:
            futures = {pool.submit(run_account, url, idx): idx for idx, url in enumerate(account_urls)}
            for future in as_completed(futures):
                all_results.append(future.result())

    all_results.sort(key=lambda x: x['index'])

    try:
        with open(RESULT_FILE, 'a', encoding='utf-8') as f:
            for r in all_results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        print(f"📄 结果已保存到 {RESULT_FILE}")
    except OSError as e:
        print(f"⚠️ 结果保存失败: {e}")

    print("=" * 60)
    print(f"📊 中秋博饼集礼盒活动汇总{'（自检模式）' if DRY_RUN else ''}")
    print("=" * 60)
    for result in all_results:
        phone = result.get('phone', '未知')
        masked_phone = _mask_phone(phone)
        if result.get('success'):
            print(f"  {masked_phone}: 小程序任务 {result.get('tasks_mp', 0)} / APP任务 {result.get('tasks_app', 0)} | "
                  f"邀请 {result.get('invited_friends', 0)}人({result.get('invite_process', '-')}) | "
                  f"博饼 {result.get('bobing_count', 0)}次 | "
                  f"集礼盒 {result.get('collect_count', 0)}次 | "
                  f"单次抽奖 {result.get('box_draw_count', 0)}次 | "
                  f"周四抽奖 {result.get('weekly_draw_count', 0)}次")
        else:
            print(f"  {masked_phone}: 登录失败")
    print("=" * 60)
    _notify_results(all_results)


if __name__ == '__main__':
    main()
