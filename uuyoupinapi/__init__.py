import random
import string
from venv import logger
import json
import requests
import time
from utils.logger import get_logger
from decimal import Decimal as d
logger = get_logger()


def generate_random_string(length):
    """
    生成指定长度的字符串，包含 A-Z, a-z 和数字
    :param length: 字符串长度
    :return: 随机字符串
    """
    letters_and_digits = string.ascii_letters + string.digits
    return "".join(random.choice(letters_and_digits) for i in range(length))


class UUAccount:
    def __init__(self, token):
        """
        :param token: 通过抓包获得的token
        """
        self.session = requests.Session()
        self.ignore_list = []
        random.seed(token)
        self.device_info = {
            "deviceId": generate_random_string(24),
            "deviceType": generate_random_string(6),
            "hasSteamApp": 0,
            "systemName ": "Android",
            "systemVersion": "13",
        }
        self.session.headers.update(
            {
                "authorization": "Bearer " + token,
                "content-type": "application/json; charset=utf-8",
                "user-agent": "okhttp/3.14.9",
                "app-version": "5.12.1",
                "apptype": "4",
                "devicetoken": self.device_info["deviceId"],
                "deviceid": self.device_info["deviceId"],
                "platform": "android",
            }
        )
        try:
            info = self.call_api("GET", "/api/user/Account/getUserInfo").json()
            self.nickname = info["Data"]["NickName"]
            self.userId = info["Data"]["UserId"]
        except KeyError:
            raise Exception("悠悠有品账号登录失败，请检查token是否正确")

    @staticmethod
    def __random_str(length):
        return "".join(random.sample(string.ascii_letters + string.digits, length))

    @staticmethod
    def get_token_automatically():
        """
        引导用户输入手机号，发送验证码，输入验证码，自动登录，并且返回token
        :return: token
        """
        phone_number = input("输入手机号：")
        session_id = UUAccount.get_random_session_id()
        print("随机生成的session_id：", session_id)
        print(
            "发送验证码结果：",
            UUAccount.send_login_sms_code(phone_number, session_id)["Msg"],
        )
        sms_code = input("输入验证码：")
        response = UUAccount.sms_sign_in(phone_number, sms_code, session_id)
        print("登录结果：", response["Msg"])
        got_token = response["Data"]["Token"]
        print("token：", got_token)
        return got_token

    @staticmethod
    def get_random_session_id():
        return UUAccount.__random_str(32)

    @staticmethod
    def send_login_sms_code(phone, session: str):
        """
        发送登录短信验证码
        :param phone: 手机号
        :param session: 可以通过UUAccount.get_random_session_id()获得
        :return:
        """
        return requests.post(
            "https://api.youpin898.com/api/user/Auth/SendSignInSmsCode",
            json={"Mobile": phone, "Sessionid": session},
        ).json()

    @staticmethod
    def sms_sign_in(phone, code, session):
        """
        通过短信验证码登录，返回值内包含Token
        :param phone: 发送验证码时的手机号
        :param code: 短信验证码
        :param session: 可以通过UUAccount.get_random_session_id()获得，必须和发送验证码时的session一致
        :return:
        """
        return requests.post(
            "https://api.youpin898.com/api/user/Auth/SmsSignIn",
            json={"Code": code, "SessionId": session, "Mobile": phone, "TenDay": 1},
        ).json()

    def get_user_nickname(self):
        return self.nickname

    def send_device_info(self):
        return self.call_api(
            "GET",
            "/api/common/ClientInfo/AndroidInfo",
            data={
                "DeviceToken": self.device_info["deviceId"],
                "Sessionid": self.device_info["deviceId"],
            },
        )

    def call_api(self, method, path, data=None):
        """
        调用API
        :param method: GET, POST, PUT, DELETE
        :param path: 请求路径
        :param data: 发送的数据
        :return:
        """
        url = "https://api.youpin898.com" + path
        if method == "GET":
            return self.session.get(url, params=data)
        elif method == "POST":
            return self.session.post(url, json=data)
        elif method == "PUT":
            return self.session.put(url, data=data)
        elif method == "DELETE":
            return self.session.delete(url)
        else:
            raise Exception("Method not supported")

    def get_wait_deliver_list(self, game_id=730, return_offer_id=True):
        """
        获取待发货列表
        :param return_offer_id: 默认为True，是否返回steam交易报价号
        :param game_id: 游戏ID，默认为730(CSGO)
        :return: 待发货列表，格式为[{'order_id': '订单号', 'item_name': '物品名称', 'offer_id': 'steam交易报价号'}... , ...]
        """
        toDoList_response = self.call_api(
            "POST",
            "/api/youpin/bff/trade/todo/v1/orderTodo/list",
            data={
                "userId": self.userId,
                "pageIndex": 1,
                "pageSize": 100,
                "Sessionid": self.device_info["deviceId"],
            },
        ).json()
        toDoList = dict()
        for order in toDoList_response["data"]:
            if order["orderNo"] not in self.ignore_list:
                logger.debug(
                    "[UUAutoAcceptOffer] 订单号为"
                    + order["orderNo"]
                    + "的订单已经被忽略"
                )
                toDoList[order["orderNo"]] = order
        data_to_return = []
        if len(toDoList.keys()) != 0:
            data = self.call_api(
                "POST",
                "/api/youpin/bff/trade/sale/v1/sell/list",
                data={
                    "keys": "",
                    "orderStatus": "140",
                    "pageIndex": 1,
                    "pageSize": 100,
                },
            ).json()["data"]
            for order in data["orderList"]:
                if int(order["offerType"]) == 2:
                    if order["tradeOfferId"] is not None:
                        del toDoList[order["orderNo"]]
                        data_to_return.append(
                            {
                                "offer_id": order["tradeOfferId"],
                                "item_name": order["productDetail"]["commodityName"],
                            }
                        )
        if len(toDoList.keys()) != 0:
            for order in list(toDoList.keys()):
                try:
                    orderDetail = self.call_api(
                        "POST",
                        "/api/youpin/bff/order/v2/detail",
                        data={
                            "orderId": order,
                            "Sessionid": self.device_info["deviceId"],
                        },
                    ).json()
                    orderDetail = orderDetail["data"]["orderDetail"]
                    data_to_return.append(
                        {
                            "offer_id": orderDetail["offerId"],
                            "item_name": orderDetail["productDetail"]["commodityName"],
                        }
                    )
                    del toDoList[order]
                except TypeError:
                    logger.error(
                        "[UUAutoAcceptOffer] 订单号为"
                        + order
                        + "的订单未能获取到Steam交易报价号，可能是悠悠系统错误或者需要卖家手动发送报价。该报价已经加入忽略列表。"
                    )
                    self.ignore_list.append(order)
                    del toDoList[order]
        if len(toDoList.keys()) != 0:
            logger.warning(
                "[UUAutoAcceptOffer] 有订单未能获取到Steam交易报价号，订单号为："+
                str(toDoList.keys()),
            )
        return data_to_return
class UUAccount1:
    def __init__(self, token):
        """
        :param token: 通过抓包获得的token
        """
        self.token="Bearer " + token
        self.session = requests.Session()
        self.ignore_list = []
        random.seed(token)
        self.device_info = {
            "deviceId":'ZXgXZdyreI0DACiYLNC/Oad4',#此处需要修改这个需要是你登录时提交给服务器的deviceID，切记不能是随机生成，否则部分api无法使用。最好是直接抓包来获取DeviceID
            "deviceType": generate_random_string(6),
            "hasSteamApp": 0,
            "systemName ": "Android",
            "systemVersion": "13",
        }
        self.session.headers.update(
            {
                'DeviceToken': self.device_info["deviceId"],
                'DeviceId': self.device_info["deviceId"],
                'platform': 'android',
                'package-type': 'uuyp',
                'Content-Encoding': 'gzip',
                'App-Version': '5.10.1',
                'Device-Info': str(self.device_info),
                'AppType': '7',
                'Authorization':"Bearer " + self.token,
                'Content-Type': 'application/json; charset=utf-8',
                'Host': 'api.youpin898.com',
                'Connection': 'Keep-Alive',
                # 'Accept-Encoding': 'gzip',
                'User-Agent': 'okhttp/3.14.9',
            }
        )
        try:
            info = self.call_api("GET", "/api/user/Account/getUserInfo").json()
            self.nickname = info["Data"]["NickName"]
            self.userId = info["Data"]["UserId"]
        except KeyError:
            raise Exception("悠悠有品账号登录失败，请检查token是否正确")

    @staticmethod
    def __random_str(length):
        return "".join(random.sample(string.ascii_letters + string.digits, length))

    @staticmethod
    def get_token_automatically():
        """
        引导用户输入手机号，发送验证码，输入验证码，自动登录，并且返回token
        :return: token
        """
        phone_number = input("输入手机号：")
        session_id = UUAccount.get_random_session_id()
        print("随机生成的session_id：", session_id)
        print(
            "发送验证码结果：",
            UUAccount.send_login_sms_code(phone_number, session_id)["Msg"],
        )
        sms_code = input("输入验证码：")
        response = UUAccount.sms_sign_in(phone_number, sms_code, session_id)
        print("登录结果：", response["Msg"])
        got_token = response["Data"]["Token"]
        print("token：", got_token)
        return got_token

    @staticmethod
    def get_random_session_id():
        return UUAccount.__random_str(32)

    @staticmethod
    def send_login_sms_code(phone, session: str):
        """
        发送登录短信验证码
        :param phone: 手机号
        :param session: 可以通过UUAccount.get_random_session_id()获得
        :return:
        """
        return requests.post(
            "https://api.youpin898.com/api/user/Auth/SendSignInSmsCode",
            json={"Mobile": phone, "Sessionid": session},
        ).json()

    @staticmethod
    def sms_sign_in(phone, code, session):
        """
        通过短信验证码登录，返回值内包含Token
        :param phone: 发送验证码时的手机号
        :param code: 短信验证码
        :param session: 可以通过UUAccount.get_random_session_id()获得，必须和发送验证码时的session一致
        :return:
        """
        return requests.post(
            "https://api.youpin898.com/api/user/Auth/SmsSignIn",
            json={"Code": code, "SessionId": session, "Mobile": phone, "TenDay": 1},
        ).json()

    def get_user_nickname(self):
        return self.nickname

    def send_device_info(self):
        return self.call_api(
            "GET",
            "/api/common/ClientInfo/AndroidInfo",
            data={
                "DeviceToken": self.device_info["deviceId"],
                "Sessionid": self.device_info["deviceId"],
            },
        )

    def call_api(self, method, path, data=None):
        """
        调用API
        :param method: GET, POST, PUT, DELETE
        :param path: 请求路径
        :param data: 发送的数据
        :return:
        """
        url = "https://api.youpin898.com" + path
        if method == "GET":
            return self.session.get(url, params=data)
        elif method == "POST":
            return self.session.post(url, json=data)
        elif method == "PUT":
            return self.session.put(url, data=data)
        elif method == "DELETE":
            return self.session.delete(url)
        else:
            raise Exception("Method not supported")

    def get_wait_deliver_list(self, game_id=730, return_offer_id=True):
        """
        获取待发货列表
        :param return_offer_id: 默认为True，是否返回steam交易报价号
        :param game_id: 游戏ID，默认为730(CSGO)
        :return: 待发货列表，格式为[{'order_id': '订单号', 'item_name': '物品名称', 'offer_id': 'steam交易报价号'}... , ...]
        """
        toDoList_response = self.call_api(
            "POST",
            "/api/youpin/bff/trade/todo/v1/orderTodo/list",
            data={
                "userId": self.userId,
                "pageIndex": 1,
                "pageSize": 100,
                "Sessionid": self.device_info["deviceId"],
            },
        ).json()
        toDoList = dict()
        for order in toDoList_response["data"]:
            if order["orderNo"] not in self.ignore_list:
                logger.debug(
                    "[UUAutoAcceptOffer] 订单号为"
                    + order["orderNo"]
                    + "的订单已经被忽略"
                )
                toDoList[order["orderNo"]] = order
        data_to_return = []
        if len(toDoList.keys()) != 0:
            data = self.call_api(
                "POST",
                "/api/youpin/bff/trade/sale/v1/sell/list",
                data={
                    "keys": "",
                    "orderStatus": "140",
                    "pageIndex": 1,
                    "pageSize": 100,
                },
            ).json()["data"]
            for order in data["orderList"]:
                if int(order["offerType"]) == 2:
                    if order["tradeOfferId"] is not None:
                        del toDoList[order["orderNo"]]
                        data_to_return.append(
                            {'offerType':2,
                                "offer_id": order["tradeOfferId"],
                                "item_name": order["productDetail"]["commodityName"],
                            }
                        )
                        print(data_to_return)
                if int(order["offerType"]) == 1:
                    if order['orderStatusDesc'] == '等待Steam令牌确认 -s':
                        response = self.call_api(
                            "POST", "/api/youpin/bff/trade/v1/order/query/detail", data={"orderNo": order["orderNo"]}
                        ).json()  # 接受steamid
                        print(response)
                        del toDoList[order["orderNo"]]
                        data_to_return.append({'offerType': 1,
                                               "item_name": order["productDetail"]["commodityName"],
                                               "offer_id": None,
                                               'steamid': response['data']['sendUser']['receiveOfferSteamId']
                                               })
                        print(data_to_return)
                    if order['orderStatusDesc'] == '等待您发送报价 -s' or order[
                        'orderStatusDesc'] == '报价发送中 -s':  # 发送订单并接受steamid
                        # 发送报价
                        print(order["orderNo"])
                        headers = {
                            'DeviceToken': self.device_info["deviceId"],
                            'DeviceId': self.device_info["deviceId"],
                            'platform': 'android',
                            'package-type': 'uuyp',
                            'Content-Encoding': 'gzip',
                            'App-Version': '5.10.1',
                            'Device-Info': str(self.device_info),
                            'AppType': '7',
                            'Authorization': 'Bearer ' +self.token,
                            'Content-Type': 'application/json; charset=utf-8',
                            'Host': 'api.youpin898.com',
                            'Connection': 'Keep-Alive',
                            # 'Accept-Encoding': 'gzip',
                            'User-Agent': 'okhttp/3.14.9',
                        }
                        json_data = {
                            'orderNo': order["orderNo"],
                            'Sessionid': self.device_info["deviceId"]
                        }
                        response = requests.put(
                            'https://api.youpin898.com/api/youpin/bff/trade/v1/order/sell/delivery/send-offer',
                            headers=headers,
                            json=json_data,
                            verify=False,
                        )
                        print(response.json()['msg'])
                        # 获取一下是否成功
                        # 获取steamid
                        response = self.call_api(
                            "POST", "/api/youpin/bff/trade/v1/order/query/detail", data={"orderNo": order["orderNo"]}
                        ).json()
                        del toDoList[order["orderNo"]]
                        data_to_return.append({'offerType': 1,
                                               "item_name": order["productDetail"]["commodityName"],
                                               "offer_id": None,
                                               'steamid': response['data']['sendUser']['receiveOfferSteamId']
                                               })
        if len(toDoList.keys()) != 0:#目前猜测是租赁的api
            for order in list(toDoList.keys()):
                try:
                    orderDetail = self.call_api(
                        "POST",
                        "/api/youpin/bff/order/v2/detail",
                        data={
                            "orderId": order,
                            "Sessionid": self.device_info["deviceId"],
                        },
                    ).json()
                    orderDetail = orderDetail["data"]["orderDetail"]
                    data_to_return.append(
                        {'offerType':2,
                            "offer_id": orderDetail["offerId"],
                            "item_name": orderDetail["productDetail"]["commodityName"],
                        }
                    )
                    del toDoList[order]
                except TypeError:
                    logger.error(
                        "[UUAutoAcceptOffer] 订单号为"
                        + order
                        + "的订单未能获取到Steam交易报价号，可能是悠悠系统错误或者需要卖家手动发送报价。该报价已经加入忽略列表。"
                    )
                    self.ignore_list.append(order)
                    del toDoList[order]
        if len(toDoList.keys()) != 0:
            logger.warning(
                "[UUAutoAcceptOffer] 有订单未能获取到Steam交易报价号，订单号为："+
                str(toDoList.keys()),
            )
        return data_to_return
    def search(self,keyword): #悠悠简易买饰品的搜索api
    #   {
    #   "commodityName" : "印花 | Copenhagen Wolves | 2014年 DreamHack 锦标赛",
    #   "templateId" : 57285,
    #   "label" : null,
    #   "clickNum" : 0,
    #   "leaseNum" : 0,
    #   "leaseNumber" : 0,
    #   "sellNum" : 4}
        a={"keyWords":str(keyword),"listType":50,"Sessionid":self.device_info['deviceId']}

        response=self.call_api('POST','/api/homepage/search/match',data=a)
        return response.json()
    def send_offer(self,orderNO): #orderNO为需要发送报价的的订单号，在代办列表中可以找到
        headers = {
            'DeviceToken': self.device_info["deviceId"],
            'DeviceId': self.device_info["deviceId"],
            'platform': 'android',
            'package-type': 'uuyp',
            'Content-Encoding': 'gzip',
            'App-Version': '5.10.1',
            'Device-Info': str(self.device_info),
            'AppType': '7',
            'Authorization': 'Bearer ' + self.token,
            'Content-Type': 'application/json; charset=utf-8',
            'Host': 'api.youpin898.com',
            'Connection': 'Keep-Alive',
            # 'Accept-Encoding': 'gzip',
            'User-Agent': 'okhttp/3.14.9',
        }
        json_data = {
            'orderNo': orderNO,
            'Sessionid': self.device_info["deviceId"]
        }
        response = requests.put(
            'https://api.youpin898.com/api/youpin/bff/trade/v1/order/sell/delivery/send-offer',
            headers=headers,
            json=json_data,
            verify=False,
        ).json()
        return response
    def commondity_onMarket(self,templateId,maxAbrade=None,minAbrade=None):   #返回当前templateid饰品的在售信息


        json_data = {
            'hasSold': 'true',
            'haveBuZhangType': 0,
            'listSortType': '1',
            'listType': 10,
            'mergeFlag': 0,
            'pageIndex': 1,
            'pageSize': 30,
            'sortType': '1',
            'sortTypeKey': '',
            'status': '20',
            'stickerAbrade': 0,
            'stickersIsSort': False,
            'templateId': str(templateId),
            'ultraLongLeaseMoreZones': 0,
            'userId': str(self.userId),
            'Sessionid':self.device_info['deviceId'],
        }
        if maxAbrade != None and minAbrade != None:
            json_data['maxAbrade'] = str(maxAbrade)
            json_data['minAbrade'] = str(minAbrade)

        response=self.call_api('POST','/api/homepage/v2/detail/commodity/list/sell',data=json_data)
        return response.json()['Data']['CommodityList']


    def GetUserInventoryDataList(self,Ismerge=1,status=5):#获得全部库存的详细信息 AssetStatus 5是全部库存 0是待上架库存 IsMerge是是否折叠 1是折叠 0是展开
        json_data = {
            'PageSize': 1000,
            'IsRefresh': True,
            'PageIndex': 1,
            'AssetStatus': status,
            'RefreshType': 2,
            'AppType': '4',
            'IsMerge': Ismerge,
            'GameID': 730,
            'Sessionid': self.device_info['deviceId'],
        }
        response=self.call_api('POST','/api/commodity/Inventory/GetUserInventoryDataListV3',data=json_data)
        return response.json()
    def bid_detail_list(self,status): #本账户正在求购界面 求购中状态值为20 暂停状态值为30
        data={"pageIndex":1,
              "pageSize":500,
              "status":status,
              "Sessionid":self.device_info['deviceId'],
              }
        response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/searchPurchaseOrderList',data=data )
        return response.json()['data']
    def bid_method(self,method,templateId,number='',price=''):    #求购方法集  每个方法什么意思看对应备注    templateID为饰品唯一编号   
        if method == 'mark_up':#一键加价
            response=self.bid_detail_list(status=20)
            print(response)
            NO=[i['orderNo'] for i in response if i['templateId']==int(templateId)][0]
            time.sleep(3)
            print(NO)
            data={"purchaseNo":str(NO),"Sessionid":self.device_info['deviceId']}
            rankFirstPrice=self.call_api('POST','/api/youpin/bff/trade/purchase/order/markUpPreCheck',data=data).json()['data']['rankFirstPrice']
            time.sleep(3)
            print(rankFirstPrice)
            data={"confirm":False,"purchaseNo":str(NO),"purchasePrice":str(rankFirstPrice),"Sessionid":self.device_info['deviceId']}
            response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/markUp',data=data).json()
        elif method == 'update1': #修改求购(求购中的订单)
            try:
                response = self.bid_detail_list(status=20)
                NO = [i['orderNo'] for i in response if i['templateId'] == int(templateId)][0]
                supplyQuantity=[i['buyQuantity'] for i in response if i['templateId'] == int(templateId)][0]
                time.sleep(3)
                data={"templateId":int(templateId),"purchasePrice":price,"purchaseNum":number,"needPaymentAmount":float(d(str(price))*d(str(number))),"incrementServiceCode":[1001],"totalAmount":float(d(str(price))*d(str(number))),"orderNo":str(NO),"supplyQuantity":supplyQuantity,"payConfirmFlag":False,"repeatOrderCancelFlag":False}
                response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/updatePurchaseOrder',data=data ).json()
            except:
                return 'there is none items in order!!'
        elif method == 'update2': #修改求购(暂停的订单)(注意修改完自动从暂停变为求购状态！！！)
            response = self.bid_detail_list(status=30)
            NO = [i['orderNo'] for i in response if i['templateId'] == int(templateId)][0]
            supplyQuantity=[i['buyQuantity'] for i in response if i['templateId'] == int(templateId)][0]
            time.sleep(3)
            data={"templateId":int(templateId),"purchasePrice":price,"purchaseNum":number,"needPaymentAmount":float(d(str(price))*d(str(number))),"incrementServiceCode":[1001],"totalAmount":float(d(str(price))*d(str(number))),"orderNo":str(NO),"supplyQuantity":supplyQuantity,"payConfirmFlag":False,"repeatOrderCancelFlag":False}
            print(data)
            response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/updatePurchaseOrder',data=data ).json()
        elif method == 'save'  : #添加求购 返回orderNo（每个求购的编号）
            data={"templateId":int(templateId),"purchasePrice":price,"purchaseNum":number,"needPaymentAmount":float(d(str(price))*d(str(number))),"incrementServiceCode":[1001],"totalAmount":float(d(str(price))*d(str(number))),"payConfirmFlag":False,"repeatOrderCancelFlag":True}
            # print(data)
            response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/savePurchaseOrder',data=data).json()
        elif method == 'pause' :#暂停正在求购的订单
            try:
                response = self.bid_detail_list(status=20)
                NO = [i['orderNo'] for i in response if i['templateId'] == int(templateId)][0]
                time.sleep(3)
                data={"orderNoList":[str(NO)],"Sessionid":self.device_info['deviceId']}
                response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/pausePurchaseOrder',data=data).json()
            except:
                return 'there is none items in order!!'
        elif method == 'open': #把暂定的求购订单重新开启
            response = self.bid_detail_list(status=30)
            NO = [i['orderNo'] for i in response if i['templateId'] == int(templateId)][0]
            time.sleep(3)
            data={"orderNoList":[str(NO)],"Sessionid":self.device_info['deviceId']}
            response=self.call_api('POST', '/api/youpin/bff/trade/purchase/order/openPurchaseOrder', data=data).json()

        elif method == 'delete1':#删除求购中的求购单
            response = self.bid_detail_list(status=20)
            NO = [i['orderNo'] for i in response if i['templateId'] == int(templateId)][0]
            time.sleep(3)
            data={"orderNoList":[str(NO)],"Sessionid":self.device_info['deviceId']}
            response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/deletePurchaseOrder',data=data).json()
        elif method == 'delete2':#删除暂停中的求购单
            response = self.bid_detail_list(status=30)
            NO = [i['orderNo'] for i in response if i['templateId'] == int(templateId)][0]
            time.sleep(3)
            data = {"orderNoList": [str(NO)], "Sessionid": self.device_info['deviceId']}
            response = self.call_api('POST', '/api/youpin/bff/trade/purchase/order/deletePurchaseOrder',data=data).json()
        else:
            print('the method is not be supported!!!')
            response='the method is not be supported!!!'
        return response
    def fast_sale_list(self):  #秒出货界面 信息格式为
        data={"Sessionid":self.device_info['deviceId']}
        response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/getFastShipmentTemplateInfoList',data=data).json()['data']
        return response

    def getTemplatePurchaseOrderList(self,templateId):  #获得指定templaId的求购信息
        data={"pageIndex":1,"pageSize":20,"showMaxPriceFlag":False,"templateId":int(templateId),"Sessionid":self.device_info['deviceId']}
        response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/getTemplatePurchaseOrderList',data=data).json()['data']
        return response

    def on_sale(self,isMerge=1): #isMerge 1是折叠 0是展开 默认折叠   该账户在售的饰品信息
        try:
            data={"pageIndex":1,"pageSize":1000,"whetherMerge":isMerge,"Sessionid":self.device_info['deviceId']}
            response=self.call_api('POST','/api/youpin/bff/new/commodity/v1/commodity/list/sell',data=data).json()['data']['commodityInfoList']
            return response
        except:
            print('there is nothing on sale!')
            return False
    def price_change(self,templateId,price,response=None):  #在售商品改价 response 要添加已经展开的，既isMerge=0
        if response == None:
            response=self.on_sale(isMerge=0)
            Commoditys=[{"CommodityId":i['id'],"Price":str(price),"Remark":None,"IsCanSold":True} for i in response if i['templateId'] == int(templateId)]
            time.sleep(2)
            data={"Commoditys":Commoditys}
            print(data)
            response=self.call_api('PUT','/api/commodity/Commodity/PriceChangeWithLeaseV2',data=json.dumps(data)).json()
            return response
        else:
            Commoditys = [{"CommodityId": i['id'], "Price": str(price), "Remark": None, "IsCanSold": True} for i in response if i['templateId'] == int(templateId)]
            time.sleep(2)
            data = {"Commoditys": Commoditys}
            print(data)
            response = self.call_api('PUT', '/api/commodity/Commodity/PriceChangeWithLeaseV2', data=json.dumps(data)).json()
            return response

    def SellInventory(self,templateId,price=None,number=None,response=None):  #上架商品 price为NONE 代表价格自动为底价-0.01  number目前无法修改  response是仓库信息，如果传入变量则可以减少请求量
        if response == None:
            if number == None and price == None:
                response=self.GetUserInventoryDataList(status=0,Ismerge=0)['Data']['ItemsInfos']
                ItemsInfos=[{"AssetId":i['SteamAssetId'],"Price":str(d(str(i['TemplateInfo']['MarkPrice']))-d('0.01'))}for i in response if i['TemplateInfo']['Id'] == int(templateId)]
                data={"GameID":730,"ItemInfos":ItemsInfos}
                time.sleep(2)
                response=self.call_api('POST','/api/commodity/Inventory/SellInventoryWithLeaseV2',data=data).json()
                return response
            elif number == None:
                response = self.GetUserInventoryDataList(status=0, Ismerge=0)['Data']['ItemsInfos']
                ItemsInfos = [{"AssetId": i['SteamAssetId'], "Price":str(price)} for i in response if i['TemplateInfo']['Id'] == int(templateId)]
                data = {"GameID": 730, "ItemInfos": ItemsInfos}
                time.sleep(2)
                response = self.call_api('POST', '/api/commodity/Inventory/SellInventoryWithLeaseV2', data=data).json()
                return response
            else:
                print('这里添加根据number调整上架数量，以后添加。')
        else:
            if number == None and price == None:
                response=response['Data']['ItemsInfos']
                ItemsInfos=[{"AssetId":i['SteamAssetId'],"Price":str(d(str(i['TemplateInfo']['MarkPrice']))-d('0.01'))}for i in response if i['TemplateInfo']['Id'] == int(templateId)]
                data={"GameID":730,"ItemInfos":ItemsInfos}
                time.sleep(2)
                response=self.call_api('POST','/api/commodity/Inventory/SellInventoryWithLeaseV2',data=data).json()
                return response
            elif number == None:
                response = response['Data']['ItemsInfos']
                ItemsInfos = [{"AssetId": i['SteamAssetId'], "Price":str(price)} for i in response if i['TemplateInfo']['Id'] == int(templateId)]
                data = {"GameID": 730, "ItemInfos": ItemsInfos}
                time.sleep(2)
                response = self.call_api('POST', '/api/commodity/Inventory/SellInventoryWithLeaseV2', data=data).json()
                return response
            else:
                print('这里添加根据number调整上架数量，以后添加。')

    def get_user_info(self):#返回账户当前信息（包括敏感信息！！！）
        data={'DeviceToken':self.device_info['deviceId'],'source':2,'Sessionid':self.device_info['deviceId']}
        response=self.call_api('GET','/api/user/Account/getUserInfo').json()['Data']
        return response

    def PurchaseMoney(self,money=None):#将balance转到purchasMoney账户上
        if money == None:#会将所有钱都转到求购账户中
            price =self.get_user_info()['TotalMoney']
            if price >=10:
                time.sleep(4)
                data={"tranferMoney":str(price),"Sessionid":self.device_info['deviceId']}
                response=self.call_api('POST','/api/youpin/bff/user/v1/assets/money/transfer/purchaseMoney',data=data).json()
                return
            else:
                print('向求购的转账必须大于10元')
                return '向求购的转账必须大于10元'
        elif float(money) <10:
            print('向求购的转账必须大于10元')
            return '向求购的转账必须大于10元'

        else:
            data = {"tranferMoney": str(money), "Sessionid": self.device_info['deviceId']}
            response = self.call_api('POST', '/api/youpin/bff/user/v1/assets/money/transfer/purchaseMoney',data=data).json()
            return response


    def order_switch(self,status):#打开或者关闭求购 0为关闭  1为打开
        #先检测一下当前求购账户的状态
        status_now=self.call_api('GET','/api/youpin/bff/new/commodity/v3/purchase/user/info').json()
        time.sleep(2)
        if int(status_now['data']['userStatus']) == int(status):
            print('重复命令！！')
            return False
        else:
            data={"status":int(status),"Sessionid":self.device_info['deviceId']}
            response=self.call_api('POST','/api/youpin/bff/trade/purchase/order/changeUserPurchaseStatus',data=data).json()
            print(response['msg'])
            return True
