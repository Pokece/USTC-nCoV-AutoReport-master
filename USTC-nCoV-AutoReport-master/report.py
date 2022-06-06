# encoding=utf8
import requests
import json
import time
import datetime
import pytz
import re
import sys
import argparse
from bs4 import BeautifulSoup
import pytesseract
from PIL import Image, ImageDraw
import numpy as np
import cv2
import re
import base64
class Report(object):
    def __init__(self, stuid, password, data_path, emergency_data):
        self.stuid = stuid
        self.password = password
        self.data_path = data_path
        self.run_status = "OK"
        self.emergency_data = emergency_data.split(",")
    def report(self):
        loginsuccess = False
        retrycount = 1
        while (not loginsuccess) and retrycount:
            session = self.login()
            cookies = session.cookies
            getform = session.get("https://weixine.ustc.edu.cn/2020")
            retrycount = retrycount - 1
            if getform.url != "https://weixine.ustc.edu.cn/2020/home":
                print("Login Failed! Retrying...")
            else:
                print("Login Successful!")
                loginsuccess = True
        if not loginsuccess:
            self.run_status = "LOGIN FAILED"
            return False
        data = getform.text
        data = data.encode('ascii','ignore').decode('utf-8','ignore')
        soup = BeautifulSoup(data, 'html.parser')
        token = soup.find("input", {"name": "_token"})['value']

        with open(self.data_path, "r+") as f:
            data = f.read()
            data = json.loads(data)
            data["_token"]=token
            data["jinji_lxr"] = self.emergency_data[0]
            data["jinji_guanxi"] = self.emergency_data[1]
            data["jiji_mobile"] = self.emergency_data[2]

        headers = {
            'authority': 'weixine.ustc.edu.cn',
            'origin': 'https://weixine.ustc.edu.cn',
            'upgrade-insecure-requests': '1',
            'content-type': 'application/x-www-form-urlencoded',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.100 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'referer': 'https://weixine.ustc.edu.cn/2020/home',
            'accept-language': 'zh-CN,zh;q=0.9',
            'Connection': 'close',
            'cookie': "PHPSESSID=" + cookies.get("PHPSESSID") + ";XSRF-TOKEN=" + cookies.get("XSRF-TOKEN") + ";laravel_session="+cookies.get("laravel_session"),
        }

        url = "https://weixine.ustc.edu.cn/2020/daliy_report"
        session.post(url, data=data, headers=headers)
        data = session.get("https://weixine.ustc.edu.cn/2020").text
        soup = BeautifulSoup(data, 'html.parser')
        pattern = re.compile("202[0-9]-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
        token = soup.find(
            "span", {"style": "position: relative; top: 5px; color: #666;"})
        flag = False
        
        if pattern.search(token.text) is not None:
            date = pattern.search(token.text).group()
            print("Latest report: " + date)
            date = date + " +0800"
            reporttime = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S %z")
            timenow = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
            delta = timenow - reporttime
            if delta.days < 0:
                delta = reporttime - timenow
            print("{} second(s) difference.".format(delta.seconds))
            # print("{} second(s) before.".format(delta.seconds))
            if delta.seconds < 120:
                flag = True
       
        if flag == False:
            self.run_status = "REPORT FAILED"
            print("Report FAILED!")
        else:
            print("Report SUCCESSFUL!")
        return flag

    def login(self):
        url = "https://passport.ustc.edu.cn/login?service=http%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin"
        session = requests.Session()

        # get CAS_LT
        response = session.get(url)
        response = BeautifulSoup(response.content, 'html.parser')
        login_form = response.find_all(class_='loginForm form-style')[0]
        CAS_LT = login_form.find_next(id='CAS_LT')['value']
        # get validate code
        vcode = self.get_vcode(session)
        data = {
            'model': 'uplogin.jsp',
            'service': 'https://weixine.ustc.edu.cn/2020/caslogin',
            'username': self.stuid,
            'password': str(self.password),
            'warn': '',
            'showCode': '1',
            'CAS_LT': CAS_LT,
            'LT': vcode,
            'button': '',
        }

        session.post(url, data=data)

        print("login...")
        return session
    def get_vcode(self, session):
        response = session.get("https://passport.ustc.edu.cn/validatecode.jsp?type=login")
        image = response.content
        with open("img.png", "wb") as f:
            f.write(response.content)
        image=cv2.imread('img.png')
        # text = recognize_text(image)
        kernel = np.ones((3,3),np.uint8)
        image = cv2.dilate(image,kernel,iterations = 1)
        image = Image.fromarray(image)
        image.show()
        text = pytesseract.image_to_string(image)
        print("'" + text + "'")
        vcode = re.findall("\d+", text)[0][0:4]
        print("'" + vcode + "'")
        # print(response.content)
        return vcode

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='URC nCov auto report script.')
    parser.add_argument('data_path', help='path to your own data used for post method', type=str)
    parser.add_argument('stuid', help='your student number', type=str)
    parser.add_argument('password', help='your CAS password', type=str)
    parser.add_argument('emergency_data', help='emergency data', type=str)
    
    args = parser.parse_args()

    autorepoter = Report(stuid=args.stuid, password=args.password, data_path=args.data_path, emergency_data=args.emergency_data)
    count = 5
    while count != 0:
        ret = autorepoter.report()
        if ret != False:
            break
        print("Report Failed, retry...")
        count = count - 1
    if count != 0:
        exit(0)
    else:
        # last run info
        if(autorepoter.run_status == "LOGIN FAILED"):
            exit_code = 16
        elif(autorepoter.run_status == "REPORT FAILED"):
            exit_code = 32
        else:
            exit_code = 64
        exit(exit_code)
