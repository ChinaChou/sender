#encoding:utf-8
import datetime
import smtplib
import json
import logging
import pickle
import os
from flask import Flask
from flask_restful import Api,Resource,reqparse
from email.mime.text import MIMEText
from email.utils import formataddr
from email.header import Header
from urllib.request import Request,urlopen


app = Flask(__name__)
api = Api(app)

logger = logging.Logger("fxd")
formatter = logging.Formatter(fmt='%(asctime)s %(filename)s [line:%(lineno)d] %(levelname)s %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

init_token = {
    1: {"token": "", "apply_time": 0, "expires": 0},
    1000002: {"token": "", "apply_time": 0, "expires": 0},
    1000003: {"token": "", "apply_time": 0, "expires": 0}
}
data_file = "/opt/token_cache.data"
if os.path.getsize(data_file) <= 0:
    with open(data_file,'wb') as f:
        pickle.dump(init_token,f)
    logger.info("inited token file")

class Wechat(Resource):
    corp_id = "wx222e742cdf473820"
    app_info = {
        1: "xKWBzqccTgGd9E4DgtohozveeR7KffQ4_vZELza4q34",
        1000002: "SagsHGWZbBXgqU2b7A8uEYCNKU7omdgY9L1pnIo5DUI",
        1000003: "72xUUGmrOs9V_E7coumAKNKqvo_OfdNCLVuiu4AtzGo"
    }
    reciver_groups = (1, 2, 3, 4)
    logger.info("inited app_info")
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("content",type=str,required=True,help="Wechat content can't be empty")
        parser.add_argument("tos",type=str,required=True,help="Wechat recipient can't be empty")
        args = parser.parse_args()
        app_id = int(args["tos"].split(",")[0])
        group_id = int(args["tos"].split(",")[1])
        msg = args["content"]
        if app_id in self.app_info.keys() and group_id in self.reciver_groups and msg:
            access_token = self._get_token(app_id,self.app_info[app_id])
            if access_token:
                logger.info("start to send msg")
                result = self._send_message(access_token,app_id,group_id,msg)
                logger.info("stop to send msg")
                if result:
                    return {"code": 0, "message": "success"}
                else:
                    return {"code": 10001, "message": "Failed to send message with access_token"}
            else:
                return {"code": 10003, "message": "Failed to get access_token from qyapi.weixin.qq.com"}
        else:
            return {"code": 10005, "message": "app_id, group_id, and message one or all of them is invalided"}

    def _get_token(self,app_id,secret,timeout=5):
        token_cache = self._get_data()
        current_timestamp = datetime.datetime.timestamp(datetime.datetime.now())
        delta_time = current_timestamp - token_cache[app_id]["apply_time"]
        if delta_time > token_cache[app_id]["expires"]:
            try:
                res = urlopen("https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={0}&corpsecret={1}".format(self.corp_id,secret),timeout=timeout)
            except Exception as e:
                logger.error("Failed to get token from qyapi.weixin.qq.com with exception: {0}".format(str(e)))
            else:
                result = json.loads(res.read())
                res.close()
                current_timestamp = datetime.datetime.timestamp(datetime.datetime.now())
                access_token = result["access_token"]
                expires = result["expires_in"]
                token_cache[app_id]["token"] = access_token
                token_cache[app_id]["apply_time"] = current_timestamp
                token_cache[app_id]["expires"] = expires
                self._save_data(token_cache)
                return access_token
        else:
            return token_cache[app_id]["token"]

    def _send_message(self,token,app_id,group_id,message,timeout=2):
        msg_template = {
            "toparty": "",
            "msgtype": "text",
            "agentid": 0,
            "text": {"content": ""},
            "safe": 0
        }
        msg_template["toparty"] = "{0}".format(group_id)
        msg_template["agentid"] = app_id
        msg_template["text"]["content"] = message
        msg = json.dumps(msg_template,ensure_ascii=False).encode()
        try:
            req = Request("https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={0}".format(token),data=msg,headers={"Content-Type":"application/json"})
            res = urlopen(req,timeout=timeout)
        except Exception as e:
            logger.error("Failed to send message with exception {0}".format(str(e)))
        else:
            result = json.loads(res.read())
            res.close()
            if result["errcode"] == 0:
                return True
    
    def _save_data(self,data):
        with open(data_file,"wb") as f:
            pickle.dump(data,f)

    def _get_data(self):
        with open(data_file,'rb') as f:
            ret = pickle.load(f)
        return ret

class Email(Resource):
    smtp_host = "mail.faxindai.com"
    smtp_port = 25
    smtp_timeout = 5
    smtp_from = "zhoubao@faxindai.com"
    smtp_passwd = "email@awp"

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("subject",type=str,required=True,help="Email subject can't be empty")
        parser.add_argument("content",type=str,required=True,help="Email content can't be empty")
        parser.add_argument("tos",type=str,required=True,help="Email recipient can't be empty")
        args = parser.parse_args()
        try:
            server = smtplib.SMTP(host=self.smtp_host,port=self.smtp_port,timeout=self.smtp_timeout)
            server.login(self.smtp_from,self.smtp_passwd)
            msg = MIMEText(args["content"],"plain","utf-8")
            msg["From"] = formataddr((Header("Open Fal-con","utf-8").encode(),self.smtp_from))
            msg["To"] = Header(args["tos"],"utf-8")
            msg["subject"] = Header(args["subject"],"utf-8")
            server.sendmail(self.smtp_from,args["tos"].split(","),msg.as_string())
        except Exception as e:
            logger.error(e)
            return {"code":1007,"message":"Failed to send email with exception {0}".format(str(e))}
        else:
            server.quit()
            return {"code":0,"message":"success"}

api.add_resource(Wechat,"/wechat")
api.add_resource(Email,"/email")

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=10086)