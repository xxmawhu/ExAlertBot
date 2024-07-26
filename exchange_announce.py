import time
import datetime
import json
import base64
import hmac
import hashlib
import shelve
from loguru import logger
import pandas as pd
from dateutil import parser
from opencc import OpenCC
import requests
import config


def convert_to_simplified(text):
    cc = OpenCC('t2s')  # t2s 表示繁体到简体
    simplified_text = cc.convert(text)
    return simplified_text


def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign


class ExchangeAnnounce:
    cfg = config.Config("config.ini")
    msg_status = shelve.open(".msg_status", writeback=True)

    def __init__(self, channel, title, date, content):
        self.channel = channel
        self.title = title
        self.date = date
        self.content = content
        self.addr = ExchangeAnnounce.cfg.get_value("feishu.addr")
        self.secret = ExchangeAnnounce.cfg.get_value("feishu.secret")
        self.max_msg_days = ExchangeAnnounce.cfg.get_intvalue("base.max_msg_days", 7)
        key = self.__str__()
        if key not in self.msg_status:
            self.msg_status[key] = 0
            self.msg_status.sync()

    def __str__(self):
        return f"{self.channel}__{self.title}__{self.content}"

    def update(self):
        if ExchangeAnnounce.cfg.update_config():
            self.addr = ExchangeAnnounce.cfg.get_value("feishu.addr")
            self.secret = ExchangeAnnounce.cfg.get_value("feishu.secret")

    def send(self):
        self.update()
        key = str(self)
        if self.msg_status[key] > 0:
            return
        timestamp = str(int(time.time()))
        try:
            s = parser.parse(self.date, fuzzy=True).strftime("%Y-%m-%d")
            if (
                pd.Timestamp.now().tz_localize(None) - pd.to_datetime(s).tz_localize(None)
            ).days > self.max_msg_days:
                logger.warning("{} {} more than {} days ago", self.title, self.date, self.max_msg_days)
                return
        except Exception as e:
            logger.error("{}", e)
        sign = gen_sign(timestamp, self.secret)
        channel = convert_to_simplified(self.channel)
        title = convert_to_simplified(self.title)
        content = convert_to_simplified(self.content)
        json_data = json.dumps(
            {
                "timestamp": timestamp,
                "sign": sign,
                "msg_type": "text",
                "content": {
                    "text": f'来自: {channel}\n标题: {title}\n发布时间: {self.date}\n内容: {content}'
                }
            }
        )
        try:
            response = requests.post(
                self.addr,
                data=json_data,
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )
            if response.status_code == 200:
                self.msg_status[key] = int(datetime.datetime.now().strftime("%Y%m%d"))
                self.msg_status.sync()
                logger.info("send {}@{} success!", self.title, self.date)
        except Exception as e:
            logger.error("{}", e)


def test():
    ExchangeAnnounce("测试", "test", "2024-07-24", "这是个测试").send()


if __name__ == "__main__":
    test()
