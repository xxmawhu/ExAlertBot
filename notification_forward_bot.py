import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dateutil.parser import parse
import datetime
import time
import json
import os
import hashlib
import base64
import hmac
import requests

SECRET = "sqNvQd0igvZ1bKmqB4XRXc"
BOT_ADDR = "https://open.feishu.cn/open-apis/bot/v2/hook/a1d51ec4-5d6a-4912-8cdd-87c0ec9a648c"
file_path = 'last_update.txt'  # specify your file path

if not os.path.exists(file_path):
    with open(file_path, 'w') as file:
        file.write('\n' * 6)

with open(file_path, 'r') as file:
    LAST_UPDATE = file.readlines()

def gen_sign(timestamp, secret):
    # Splicing timestamp and secret
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    # Perform base64 processing on the result
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def send_to_bot(origin, subject, date, content):
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, SECRET)
    json_data = json.dumps({
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "text",
        "content": {
                "text": f'来自: {origin}\n标题: {subject}\n发布时间: {date}\n内容: {content}'
        }
    })
    response = requests.post(BOT_ADDR, data=json_data, headers={'Content-Type': 'application/json'})

    # Check the response
    if response.status_code == 200:
        print('Webhook POST succeeded:', response.text)
    else:
        print('Webhook POST failed:', response.text)

def parse_okx(driver):
    url = f'https://www.okx.com/status'
    driver.get(url)
    driver.implicitly_wait(3)
    upgrade = driver.find_element(By.CSS_SELECTOR, ".status-list-component.upgrade-list.okx").find_element(By.XPATH, ".//li[1]")
    time = upgrade.find_element(By.CSS_SELECTOR, ".bottom").text
    title = upgrade.find_element(By.CSS_SELECTOR, ".top").text
    content = upgrade.find_element(By.CSS_SELECTOR, ".impact-description").text
    if time + '\n' != LAST_UPDATE[0]:
        LAST_UPDATE[0] = time + '\n'
        send_to_bot('OKEx_系统维护', title, time, content)
    fault = driver.find_element(By.CSS_SELECTOR, ".status-list-component.fault-list.okx").find_element(By.XPATH, ".//li[1]")
    time = fault.find_element(By.CSS_SELECTOR, ".bottom").text
    title = fault.find_element(By.CSS_SELECTOR, ".top").text
    content = fault.find_element(By.CSS_SELECTOR, ".fault-item-link-container").get_attribute('href')
    if time + '\n' != LAST_UPDATE[1]:
        LAST_UPDATE[1] = time + '\n'
        send_to_bot('OKEx_故障', title, time, content)

def parse_bn(driver):
    url = f'https://www.binance.com/zh-CN/support/announcement/%E5%B8%81%E5%AE%89api%E6%9B%B4%E6%96%B0?c=51'
    driver.get(url)
    driver.implicitly_wait(8)
    try:
        cookie = driver.find_element(By.ID, ".onetrust-accept-btn-handler")
        cookie.click()
    except:
        pass
    upgrade = driver.find_element(By.CSS_SELECTOR, ".css-1tl1y3y")
    time = upgrade.find_element(By.CSS_SELECTOR, ".css-eoufru").text
    title = upgrade.find_element(By.CSS_SELECTOR, ".css-1yxx6id").get_attribute('outerHTML')
    soup = BeautifulSoup(title, 'html.parser')
    title = soup.div.text
    time = soup.h6.text
    title = title.replace(time, '', 1)
    content = upgrade.find_element(By.XPATH, './/a').get_attribute('href')
    if time + '\n' != LAST_UPDATE[2]:
        LAST_UPDATE[2] = time + '\n'
        send_to_bot('币安_API更新', title, time, content)
        
    url = f'https://www.binance.com/zh-CN/support/announcement/%E4%B8%8B%E6%9E%B6%E8%AE%AF%E6%81%AF?c=161'
    driver.get(url)
    driver.implicitly_wait(8)
    try:
        cookie = driver.find_element(By.ID, ".onetrust-accept-btn-handler")
        cookie.click()
    except:
        pass
    fault = driver.find_element(By.CSS_SELECTOR, ".css-1tl1y3y")
    time = fault.find_element(By.CSS_SELECTOR, ".css-eoufru").text
    title = fault.find_element(By.CSS_SELECTOR, ".css-1yxx6id").get_attribute('outerHTML')
    soup = BeautifulSoup(title, 'html.parser')
    title = soup.div.text
    time = soup.h6.text
    title = title.replace(time, '', 1)
    content = fault.find_element(By.XPATH, './/a').get_attribute('href')
    if time + '\n' != LAST_UPDATE[3]:
        LAST_UPDATE[3] = time + '\n'
        send_to_bot('币安_下架讯息', title, time, content)

def parse_bybit(driver):
    url = f'https://announcements.bybit.com/zh-TW/?category=maintenance_updates'
    driver.get(url)
    driver.implicitly_wait(3)
    upgrade = driver.find_element(By.CSS_SELECTOR, ".article-list").find_element(By.XPATH, './/a')
    content = upgrade.get_attribute('href')
    title = upgrade.find_element(By.CSS_SELECTOR, '.article-item-title').text
    time = upgrade.find_element(By.CSS_SELECTOR, '.article-item-date').text
    if time + '\n' != LAST_UPDATE[4]:
        LAST_UPDATE[4] = time + '\n'
        send_to_bot('Bybit_维护和升级', title, time, content)
        
    url = f'https://announcements.bybit.com/zh-TW/?category=delistings'
    driver.get(url)
    driver.implicitly_wait(3)
    fault = driver.find_element(By.CSS_SELECTOR, ".article-list").find_element(By.XPATH, './/a')
    content = fault.get_attribute('href')
    title = fault.find_element(By.CSS_SELECTOR, '.article-item-title').text
    time = fault.find_element(By.CSS_SELECTOR, '.article-item-date').text
    if time + '\n' != LAST_UPDATE[5]:
        LAST_UPDATE[5] = time + '\n'
        send_to_bot('Bybit_下架讯息', title, time, content)

service = webdriver.ChromeService(executable_path='./chromedriver-linux64/chromedriver')
driver = webdriver.Chrome(service=service)

parse_okx(driver)
parse_bn(driver)
parse_bybit(driver)
driver.quit()

with open(file_path, 'w') as file:
    file.writelines(LAST_UPDATE)

print(LAST_UPDATE)


