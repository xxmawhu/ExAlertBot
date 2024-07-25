import urllib.parse
import re
import datetime
import time
import json
import os
import hashlib
import base64
import hmac
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse
from playwright.sync_api import sync_playwright
from loguru import logger
import config
import exchange_announce

logger.remove(handler_id=None)
logger.add(
    "log/announce.{time:YYYYMMDD}",
    rotation="00:00",
    retention=datetime.timedelta(days=7),
    backtrace=True,
    diagnose=True,
    enqueue=True,
)

cfg = config.Config("config.ini")


def send_to_bot(origin, subject, date, content):
    a = exchange_announce.ExchangeAnnounce(origin, subject, date, content)
    a.send()


def transform_string(s):
    # Percent encode Chinese characters
    encoded_str = urllib.parse.quote(s, safe='')

    # Replace all fullwidth symbols with "-"
    # Assuming fullwidth symbols are in the range U+FF01 to U+FF5E
    for char in range(0xFF01, 0xFF5E + 1):
        encoded_str = encoded_str.replace(chr(char), '-')

    # Replace all whitespace with ""
    encoded_str = encoded_str.replace(' ', '')
    encoded_str = encoded_str.replace('%20', '')
    encoded_str = encoded_str.replace('%2f', '-').replace('%2F', '-')
    # Convert all uppercase letters to lowercase
    encoded_str = encoded_str.lower()

    return encoded_str


def standardize_date(date_str):
    try:
        # Replace Chinese characters with a hyphen
        cleaned_date_str = re.sub(r'[\u4e00-\u9fff]', '-', date_str)
        # Parse the cleaned date string
        date = parse(cleaned_date_str)
        # Format the date object into 'YYYY-MM-DD' format
        standardized_date = date.strftime('%Y-%m-%d')
        return standardized_date
    except ValueError:
        logger.error(f"Could not parse date: {date_str}")
        return None


def parse_relativeTime_to_datetime(relative_time_str):
    hours_regex = r"(\d+)\s小时"
    minutes_regex = r"(\d+)\s分钟"
    seconds_regex = r"(\d+)\s秒"

    hours_match = re.search(hours_regex, relative_time_str)
    minutes_match = re.search(minutes_regex, relative_time_str)
    seconds_match = re.search(seconds_regex, relative_time_str)

    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = int(seconds_match.group(1)) if seconds_match else 0

    now = datetime.datetime.now()

    target_datetime = now - datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
    target_datetime = target_datetime.replace(microsecond=0)
    return target_datetime


def parse_okx_announcements():
    url = "https://www.okx.com/cn/help/category/announcements"
    try:
        res = requests.get(url, timeout=30)
    except Exception as e:
        logger.error("Netowrk error when sending the request: {}", e)
        return

    if res.status_code == 200:
        soup = BeautifulSoup(res.content, 'html.parser')
        latest_news = soup.find("script", id="appState")
        data = json.loads(latest_news.string)
        logger.info("{}", data['appContext'])
        for item in data['appContext']['initialProps']['articleList']['items']:
            title = item['title']
            publishTime = item['publishTime']
            content = "https://www.okx.com/cn/help/" + item['slug']
            send_to_bot('OKEx_公告', title, publishTime, content)


def parse_okx():
    url = 'https://www.okx.com/status'

    try:
        response = requests.get(url, timeout=30)
    except Exception as e:
        logger.error("Netowrk error when sending the request: {}", e)
        return

    if response.status_code == 200:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Locate the fault list item
        fault_list = soup.select_one(".status-list-component.fault-list.okx")
        first_fault_item = fault_list.select_one("li:nth-of-type(1)") if fault_list else None
        # Extract the time, title, and content
        if first_fault_item:
            time = first_fault_item.select_one(".bottom"
                                               ).text if first_fault_item.select_one(".bottom") else None
            title = first_fault_item.select_one(".top").text if first_fault_item.select_one(".top") else None
            content_link_container = first_fault_item.select_one(".fault-item-link-container")
            content = 'https://www.okx.com' + content_link_container['href'
                                                                     ] if content_link_container else None

            send_to_bot('OKEx_故障', title, time, content)
        else:
            logger.error('No fault items found')

        # Locate the upgrade list item
        upgrade_list = soup.select_one(".status-list-component.upgrade-list.okx")
        first_upgrade_item = upgrade_list.select_one("li:nth-of-type(1)") if upgrade_list else None
        # Extract the time, title, and content
        if first_upgrade_item:
            time = first_upgrade_item.select_one(".bottom"
                                                 ).text if first_upgrade_item.select_one(".bottom") else None
            title = first_upgrade_item.select_one(".top"
                                                  ).text if first_upgrade_item.select_one(".top") else None
            content = first_upgrade_item.select_one(
                ".impact-description"
            ).text if first_upgrade_item.select_one(".impact-description") else None

            send_to_bot('OKEx_系统维护', title, time, content)
        else:
            logger.info('No upgrade items found')
    else:
        logger.error(f'Failed to retrieve page with status code: {response.status_code}')


def parse_bn():
    url = "https://www.binance.com/zh-CN/support/announcement/%E4%B8%8B%E6%9E%B6%E8%AE%AF%E6%81%AF?c=161"

    try:
        response = requests.get(url, timeout=30)
    except Exception as e:
        logger.error(f"Netowrk error when sending the request: {e}")
        return

    if response.status_code != 200:
        logger.error(f"Failed to retrieve {url}")

    soup = BeautifulSoup(response.content, 'html.parser')
    app_data_element = soup.find('script', id='__APP_DATA')
    data = json.loads(app_data_element.string)
    for i in data["appState"]["loader"]["dataByRouteId"].values():
        if "catalogs" in i:
            data = i["catalogs"]
    for i in data:
        if i["catalogName"] == "币安API更新":
            data = i["articles"][0]
            title = data["title"]
            time = data["releaseDate"]
            timestamp_s = time / 1000.0
            date_utc = datetime.datetime.utcfromtimestamp(timestamp_s)
            date_str = date_utc.strftime('%Y-%m-%d')
            content = transform_string(title)
            if content[-1] != "-":
                content = content + "-"
            content = content + data["code"]
            content = f"https://www.binance.com/zh-CN/support/announcement/{content}"
            send_to_bot('币安_API更新', title, date_str, content)
        elif i["catalogName"] == "下架讯息":
            data = i["articles"][0]
            title = data["title"]
            time = data["releaseDate"]
            timestamp_s = time / 1000.0
            date_utc = datetime.datetime.utcfromtimestamp(timestamp_s)
            date_str = date_utc.strftime('%Y-%m-%d')
            content = transform_string(title)
            if content[-1] != "-":
                content = content + "-"
            content = content + data["code"]
            content = f"https://www.binance.com/zh-CN/support/announcement/{content}"
            send_to_bot('币安_下架讯息', title, date_str, content)


def parse_bybit():
    categories = {
        'https://announcements.bybit.com/zh-TW/?category=maintenance_updates':
            {
                'index': 4,
                'label': 'Bybit_维护和升级',
                "headers":
                    {
                        'Accept':
                            'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Encoding':
                            'gzip, deflate, br',
                        'Accept-Language':
                            'en-US,en;q=0.9,zh-CN;q=0.8,zh-TW;q=0.7,zh;q=0.6',
                        'Cache-Control':
                            'no-cache',
                        'Cookie':
                            'YOUR_COOKIE_HERE',
                        'Pragma':
                            'no-cache',
                        'Sec-Ch-Ua':
                            '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
                        'Sec-Ch-Ua-Mobile':
                            '?0',
                        'Sec-Ch-Ua-Platform':
                            '"Windows"',
                        'Sec-Fetch-Dest':
                            'document',
                        'Sec-Fetch-Mode':
                            'navigate',
                        'Sec-Fetch-Site':
                            'same-origin',
                        'Sec-Fetch-User':
                            '?1',
                        'Upgrade-Insecure-Requests':
                            '1',
                        # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                        'User-Agent':
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.140 Safari/537.36 Edge/17.17134'
                    }
            },
        'https://announcements.bybit.com/zh-TW/?category=delistings':
            {
                'index': 5,
                'label': 'Bybit_下架讯息',
                "headers":
                    {
                        'Accept':
                            'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Encoding':
                            'gzip, deflate, br',
                        'Accept-Language':
                            'en-US,en;q=0.9,zh-CN;q=0.8,zh-TW;q=0.7,zh;q=0.6',
                        'Cache-Control':
                            'no-cache',
                        'Cookie':
                            'YOUR_COOKIE_HERE',
                        'Pragma':
                            'no-cache',
                        'Sec-Ch-Ua':
                            '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
                        'Sec-Ch-Ua-Mobile':
                            '?0',
                        'Sec-Ch-Ua-Platform':
                            '"Windows"',
                        'Sec-Fetch-Dest':
                            'document',
                        'Sec-Fetch-Mode':
                            'navigate',
                        'Sec-Fetch-Site':
                            'same-origin',
                        'Sec-Fetch-User':
                            '?1',
                        'Upgrade-Insecure-Requests':
                            '1',
                        # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                        'User-Agent':
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.140 Safari/537.36 Edge/17.17134'
                    }
            }
    }

    for url, category_info in categories.items():
        try:
            response = requests.get(url, headers=category_info["headers"], timeout=30)
        except Exception as e:
            logger.error(f"Netowrk error when sending the request: {e}")
            return

        if response.status_code != 200:
            logger.error(f'Failed to retrieve {url}')
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        article_item = soup.select_one(".article-list a")
        if not article_item:
            logger.error(f'No article item found on {url}')
            continue

        content_link = "https://announcements.bybit.com" + article_item['href']
        title_text = article_item.select_one('.article-item-title').text
        time_text = article_item.select_one('.article-item-date').text
        time_text = standardize_date(time_text)
        send_to_bot(category_info['label'], title_text, time_text, content_link)


def parse_kucoin():

    def get_DeltaTime(target_time_str):
        target_time_format = "%d/%m/%Y %H:%M:%S"
        target_time = datetime.datetime.strptime(target_time_str, target_time_format)
        now = datetime.datetime.now()
        difference = target_time - now
        return difference

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()

        def child_parse_kucoin(suffix, index):
            url = f"https://www.kucoin.com/zh-hant/announcement/{suffix}"
            if suffix == "new-listings":
                suffix = '新币上新'
            elif suffix == "maintenance-updates":
                suffix = '系统维护'
            elif suffix == "delistings":
                suffix = '币种下线'

            page.goto(url)
            page.wait_for_timeout(5000)

            soup = BeautifulSoup(page.content(), 'html.parser')
            app_data_element = soup.find_all('a', class_="css-1xt67dr")

            for idx, data in enumerate(app_data_element):
                link = 'https://www.kucoin.com' + data['href']
                contents = data.get_text(' --- ')
                contents = contents.split(' --- ')
                title, date = contents[0], contents[-1]
                send_to_bot(f"Kucoin_{suffix}", title, date, link)

        child_parse_kucoin('maintenance-updates', 7)
        child_parse_kucoin('delistings', 8)


def parse_gate():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.gate.io/zh/articlelist/ann/1")
        page.wait_for_timeout(5000)

        def child_parse_gate(suffix, index):
            if suffix == "新币上线":
                button_xpath = '//html/body/div[1]/div[1]/div/div[1]/div[2]/div/div/div[6]/div'
            elif suffix == "币种下线":
                button_xpath = '//html/body/div[1]/div[1]/div/div[1]/div[2]/div/div/div[7]/div'

            page.evaluate(
                '''(xpath) => {
                const element = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (element) element.click();
            }''', button_xpath
            )
            page.wait_for_timeout(5000)  # 5 seconds

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            app_data_element = soup.find_all('a', class_="article-list-item-title")
            app_update = soup.find_all('span', class_="article-list-info-timer article-list-item-info-item")
            for idx, data in enumerate(app_data_element):
                link = 'https://www.gate.io' + data['href']
                title = data.get_text().strip()
                date = app_update[idx].get_text().strip()
                send_to_bot(f"Gate.io_{suffix}", title, parse_relativeTime_to_datetime(date), link)

        child_parse_gate('币种下线', 10)
        browser.close()


exchange_list = cfg.get_list("base.exchange")
if "OKEX" in exchange_list:
    parse_okx_announcements()
    parse_okx()
if "BINANCE" in exchange_list:
    parse_bn()
if "BYBIT" in exchange_list:
    parse_bybit()
if "KUCOIN" in exchange_list:
    parse_kucoin()
if "GATE" in exchange_list:
    parse_gate()
