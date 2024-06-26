#coding=utf-8
import re
import os
import sys
import flask
import signal
import requests
import json
import time
import subprocess
import argparse, textwrap
import retrying 
import threading

from gevent.pywsgi import WSGIServer
from gevent import monkey

import warnings
warnings.filterwarnings("ignore")
#monkey.patch_all()

#from loguru import logger
#logger.add(sink='{time}_log.log', encoding='utf-8', rotation= "1 GB")

from loguru import logger

# "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}
# </cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

# 配置日志文件，按日期和时间命名和轮转
log_format = "[{process} {level} {time}] at {file}:{line} {function} {message}"

# logger.add(
#     "logs/{time:YYYYMMDD}.log",
#     rotation="00:00",  # 按照每天的日期和时间轮转 "7 days" 7天轮转
#     compression="zip",  # "zip",  # 压缩旧的日志文件
#     format=log_format,
#     level="INFO",  # 最低日志级别
# )

logger.add(
    sys.stdout,
    format=log_format,
    level="INFO"  # 最低日志级别
)
server= flask.Flask(__name__)

global args
args = None

global IPS
IPS = None

global CONF
CONF = None

global dev2task
dev2task = {}

global runFlag
runFlag = True

def exit_while(signum, frame):
    global runFlag
    runFlag = False
    logger.error("Exit...")
    IPS.close()
    time.sleep(2)
    exit(0)
    
signal.signal(signal.SIGINT, exit_while)
signal.signal(signal.SIGTERM, exit_while)


# 输入bool参数的处理
def str2bool(v):
    if isinstance(v,bool):
        return v
    if v == 'True':
        return True
    if v == 'False':
        return False

# 输入参数处理
def argsProcess():
    # 使用样例
    usage = """python3 IPSound.py   [-h] 
                                    [--appId APPID] 
                                    [--appCode APPCODE]
                                    [--deviceMapInfoFile DEVICEMAPINFOFILE]
                                    [--algMapInfoFile ALGMAPINFOFILE]
    """
    # 使用注意
    epilog="""
    注意：
    """
    # 参数配置 usage=usage,
    parser = argparse.ArgumentParser(description='这是个IP音柱的接口使用的脚本. ',  epilog=epilog, formatter_class=argparse.RawTextHelpFormatter) 
    
    # 参数设置
    parser.add_argument('--port', type=int, default=20000, help='')
    parser.add_argument('--appId', type=str, default='ac148c28ca424b0ebc8047ad7b3c387e', help='')
    parser.add_argument('--appCode', type=str, default='46694a1148b947668b5903522cdde2a2', help='')    
    parser.add_argument('--deviceMapInfoFile', type=str, default='./configs/deviceMapInfo.json', help='')
    parser.add_argument('--algMapInfoFile', type=str, default='./configs/algMapInfo.json', help='')
    parser.add_argument('--audios', type=str, default='./audios/', help='')
    # 参数转换
    args = parser.parse_args()

    return args
    
# 配置文件信息 配置摄像头地址对应的设备id 以及 算法任务对应的音频id
class Configure:
    # 初始化参数
    def __init__(self, deviceMapInfoFile, algMapInfoFile):
        self.deviceMapInfoFile = deviceMapInfoFile
        self.algMapInfoFile = algMapInfoFile
        self.deviceMapInfo = None
        self.algMapInfo = None
        
        self.getDeviceMapInfo()
        self.getAlgMapInfo()
        
    # 加载摄像头映射喇叭id  
    def getDeviceMapInfo(self):
        try:
            with open(self.deviceMapInfoFile, 'r+', encoding='utf8') as fp:
                self.deviceMapInfo = json.load(fp)
        except Exception as e:
            logger.error("读取摄像头映射喇叭id文件信息失败！！！", e)
          
    # 加载算法映射音频名称文件   
    def getAlgMapInfo(self):
        try:
            with open(self.algMapInfoFile, 'r+', encoding='utf8') as fp:
                self.algMapInfo = json.load(fp)
        except Exception as e:
            logger.error("读取算法映射音频文件信息失败！！！", e)
      
    def getDeviceIDByCamInfo(self, CamInfo):
        if CamInfo in self.deviceMapInfo.keys():
            return self.deviceMapInfo[CamInfo]
        else:
            logger.error("不存在", CamInfo, "对应的IP音响ID！！！")
            return None

    def getAutoNameByAlgID(self, AlgID):
        if AlgID in self.algMapInfo.keys():
            return self.algMapInfo[AlgID]
        else:
            logger.error("不存在", AlgID, "对应的音频！！！")
            return None
        
# IPSound 类
class IPSound:
    # 初始化参数
    def __init__(self, appId, appCode):
        self.appId = appId
        self.appCode = appCode
        self.token = None
        self.refreshoken = None
        self.tokenTimeOut = 60
        self.taskOutDateInterval = 10
        self.taskCodes = []
        self.uploadAudios = {}
        self.urls = {
            "token":f"https://norsos.lionking110.com/sos/v1/mntn/account/appId/token",
            "tokenRefresh":f"https://norsos.lionking110.com/sos/v1/mntn/account/refresh/token",
            "getSoundsInfo":f"https://norsos.lionking110.com/sos/v1/mntn/business/audioFile/list",
            "uploadSound":f"https://norsos.lionking110.com/sos/v1/mntn/business/audioFile/upload",
            "createTaskAndStartPlay":f"https://norsos.lionking110.com/sos/v1/mntn/business/play/task/start",
            "stopTask":f"https://norsos.lionking110.com/sos/v1/mntn/business/play/task/stop",
            "delTask":f"https://norsos.lionking110.com/sos/v1/mntn/business/play/task/del",
            "taskState":f"https://norsos.lionking110.com/sos/v1/mntn/business/play/task/detail",
            "delAudio":f"https://norsos.lionking110.com/sos/v1/mntn/business/audioFile/del",
        }
        
        self.getToken()
        
        # 定时器Token刷新任务
        self.tokenTimer = threading.Timer(self.tokenTimeOut, self.refreshTokenRun)
        self.tokenTimer.start()
        
        # 定时器删除过期任务
        self.delTaskTimer = threading.Timer(self.taskOutDateInterval, self.delOutDateTaskRun)
        self.delTaskTimer.start()

    # 定时Token刷新任务
    def refreshTokenRun(self):
        try:
            self.getRefreshToken()
        except Exception as e:
            self.getToken()
            logger.warning("重新获取token")
        self.tokenTimer = threading.Timer(self.tokenTimeOut, self.refreshTokenRun)
        self.tokenTimer.start()
        
    # 定时1s删除过期的任务
    def delOutDateTaskRun(self):
        for taskCode in self.taskCodes:
            if self.getTaskState(taskCode) == "finished":
                #logger.error("taskCodes Len:", len(self.taskCodes))
                self.stopTask(taskCode)
                self.delTask(taskCode)
                self.taskCodes.remove(taskCode)
                
        self.delTaskTimer = threading.Timer(self.taskOutDateInterval, self.delOutDateTaskRun)
        self.delTaskTimer.start()

    # 鉴权 (装饰器 retry 异常情况等1秒钟后尝试1次总共操作不超过10次)
    @retrying.retry(stop_max_attempt_number=10, wait_fixed=1000)
    def getToken(self):
        headers = {"Content-type": "application/json"}
        data = {
            "AppId": self.appId,
            "AppCode": self.appCode
        }
        try:
            resp = requests.post(self.urls["token"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            
            if not respJsonData["Status"]:
                self.token = respJsonData["Token"]
                self.refreshoken = respJsonData["RefreshToken"]
            else:
                logger.error(resp.text)
        except Exception as e:
            logger.error("请求token失败！！！", e)
            retrying.RetryError("Retry failed.")

	
    # 重新鉴权
    @retrying.retry(stop_max_attempt_number=10, wait_fixed=1000)
    def getRefreshToken(self):
        headers = {"Content-type": "application/json"}
        data = {"RefreshToken": self.refreshoken}
        try:
            resp = requests.post(self.urls["tokenRefresh"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if not respJsonData["Status"]:
                self.token = respJsonData["Token"]
                self.refreshoken = respJsonData["RefreshToken"]
            else:
                logger.error(resp.text)
        except Exception as e:
            logger.error("请求刷新token失败！！！", e)
            retrying.RetryError("Retry failed.")


    # 获取指定的音频信息
    def getAudioIdByName(self, audioName):
        headers = {"Content-type": "application/json", "Token": self.token}
        data = {
            "PageSize": 1000,
            "PageNum": 1,
            "Filters": [[
                {
                    "Key": "DisplayName",
                    "Type": "str",
                    "Value": audioName,
                    "Op": "="
                }
            ]]
        }
        try:
            resp = requests.post(self.urls["getSoundsInfo"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if not respJsonData["Status"]:
                if respJsonData["RecordList"]:
                    return respJsonData["RecordList"][0]["Id"]
                else:
                    logger.error(resp.text)
                    # logger.error("获取音频信息")
                    return None
            else:
                logger.error(resp.text)
                return None
        except Exception as e:
            logger.error("请求", audioName, "的音频信息失败！！！", e)
            return None

    # 上传音频数据
    def uploadAudioFile(self, file, description="测试音频"):
        try:
            headers = {"Token": self.token}
            fileName = os.path.basename(file)
            fileNameWithoutExt = os.path.splitext(fileName)[0]
            
            data = {
                'DisplayName': fileNameWithoutExt,
                'Description': description,
                'Remark': description
            }
            
            files = [('UploadFile',(fileName,open(file,'rb'),'audio/mpeg'))]
            resp = requests.post(self.urls["uploadSound"], data=data, files=files, headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if not respJsonData["Status"]:
                self.uploadAudios[fileNameWithoutExt] = respJsonData["Record"]["Id"]
                return respJsonData["Record"]["Id"]
            else:
                logger.error(resp.text)
                return None
        except Exception as e:
            logger.error("上传音频数据失败！！！", e)
            return None
    
    # 删除音频
    def delAudioInfo(self, audioId):
        try:
            headers = {"Token": self.token}
            data = {
                'Id': audioId,
            }

            resp = requests.post(self.urls["delAudio"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if not respJsonData["Status"]:
                return True
            else:
                logger.error(resp.text)
                return False
        except Exception as e:
            logger.error("上传音频数据失败！！！", e)
            return False

    # 创建播放任务并播放
    def createTaskAndStartPlay(self, deviceIds, audioId, taskName="测试任务"):
        headers = {"Content-type": "application/json", "Token": self.token}
        data = {
            "TaskName": taskName,
            "PlayTimes": 1,
            "DeviceIds": deviceIds,
            "FileInfos": [
                {
                    "FileId": audioId,
                    "Seq": 0
                }
            ]
        }
        
        try:
            resp = requests.post(self.urls["createTaskAndStartPlay"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if not respJsonData["Status"]:
                self.taskCodes.append(respJsonData["TaskCode"])
                return respJsonData["TaskCode"]
            else:
                logger.error(resp.text)
                return None
        except Exception as e:
            logger.error("创建播放任务失败！！！", e)
            return None
    
    # 停止任务
    def stopTask(self, taskCode):
        headers = {"Content-type": "application/json", "Token": self.token}
        data = {"TaskCode": taskCode}
        try:
            resp = requests.post(self.urls["stopTask"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if respJsonData["Status"]:
                logger.error(resp.text)
        except Exception as e:
            logger.error("停止播放任务失败！！！", e)
        
    # 删除任务
    def delTask(self, taskCode): 
        headers = {"Content-type": "application/json", "Token": self.token}
        data = {"TaskCode": taskCode}
        try:
            resp = requests.post(self.urls["delTask"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if respJsonData["Status"]:
                logger.error(resp.text)
        except Exception as e:
            logger.error("删除播放任务失败！！！", e)
    
            
    # 查看任务状态
    def getTaskState(self, TaskCode):
        headers = {"Content-type": "application/json", "Token": self.token}
        data = {"TaskCode": TaskCode}
        try:
            resp = requests.post(self.urls["taskState"], data=json.dumps(data), headers=headers, timeout=3,verify=False)
            respJsonData = json.loads(resp.text)
            if not respJsonData["Status"]:
                return respJsonData["TaskInfo"]["State"]
            else:
                logger.error(resp.text)
                return None
        except Exception as e:
            logger.error("查看任务状态失败！！！", e, TaskCode)
            return None
    
    def close(self):
        for taskCode in self.taskCodes:
            self.stopTask(taskCode)
            self.delTask(taskCode)
        for audioName in self.uploadAudios.keys():
            self.delAudioInfo(self.uploadAudios[audioName])
        self.taskCodes = []
        self.uploadAudios = {}
        self.tokenTimer.cancel()
        self.delTaskTimer.cancel()
    
def alarmCheck(jsonData):
    # uuid timestamp alarm cameraName cameraID 算法名称
    if not "cameraId" in jsonData.keys():
        logger.error("摄像头ID字段不存在！")
        return False
    if not "cameraName" in jsonData.keys():
        logger.error("摄像头名称字段不存在！")
        return False
    if not "cameraUrl" in jsonData.keys():
        logger.error("摄像头地址字段不存在！")
        return False
    if not "taskId" in jsonData.keys():
        logger.error("算法ID字段不存在！")
        return False
    if not "algorithmName" in jsonData.keys():
        logger.error("算法名称字段不存在！")
        return False
    if not "alarmUrl" in jsonData.keys():
        logger.error("报警图片字段不存在！")
        return False
    if not "timestamp" in jsonData.keys():
        logger.error("时间戳不存在！")
        return False
    if not "resultData" in jsonData.keys():
        logger.error("数据不存在！")
        return False
    if not "objectList" in jsonData["resultData"].keys():
        logger.error("结果数据不存在！")
        return False
    return True

def alarm2pushData(jsonData, args):
    pushData = {}
    return jsonData

        
@server.route('/callback',methods=['post'])
def callback():
    path = flask.request.path
    host = flask.request.host
    jsonData = flask.request.json
    status = alarmCheck(jsonData)
    
    if not status:
        return "失败，相关字段不存在", 500
        
    data = alarm2pushData(jsonData, args)
    
    # 获取配置信息
    deviceId = CONF.getDeviceIDByCamInfo(jsonData["cameraName"])
    audioName = CONF.getAutoNameByAlgID(str(jsonData["algorithmId"]))
    logger.info(f"0->{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}->received a new alarm deviceId:{deviceId},audioName:{audioName},algorithmId:{jsonData['algorithmId']}")
    # 看前一个喇叭任务状态若完成，则停止这个喇叭的播放任务，否则跳过
    if dev2task and deviceId in dev2task.keys():
        taskCode = dev2task[deviceId]
        status = IPS.getTaskState(taskCode)
        logger.info("taskCode:", taskCode)
        if taskCode and status and status == "finished":
            IPS.stopTask(taskCode)
            logger.info(f"the previous alarm has ended deviceId{deviceId},audioName{audioName},algorithmId{jsonData['algorithmId']}")

        elif not status:
            logger.info("taskCode:", taskCode, "status:", status)
            logger.info(f"start a new alarm deviceId{deviceId},audioName{audioName},algorithmId{jsonData['algorithmId']}")

        elif status == "tostart":
            logger.error("taskCode:", taskCode, "status:", status)
            time.sleep(7)
            IPS.stopTask(taskCode)
            logger.info(f"end the tostart task in 7 seconds deviceId{deviceId},audioName{audioName},algorithmId{jsonData['algorithmId']}")

        else:
            #此次播放跳过
            logger.info("taskCode:", taskCode, "status:", status)
            logger.info(f"skip this alarm deviceId{deviceId},audioName{audioName},algorithmId{jsonData['algorithmId']}")
            return "Successful",200
            
    # 判断是否存在线上的音频去播放 没有就上传本音频去播放
    if deviceId and audioName:
        audioId = IPS.getAudioIdByName(audioName)
        if audioId:
            dev2task[deviceId] = IPS.createTaskAndStartPlay([deviceId], audioId)
        else:
            logger.error("线上", audioId, audioName, "音频未查到！！！")
            # 添加音频
            file = args.audios + audioName + ".wav"
            audioId = IPS.uploadAudioFile(file)
            dev2task[deviceId] = IPS.createTaskAndStartPlay([deviceId], audioId)
            
    else:
        logger.error("未查到摄像头和算法映射的喇叭id和音频名称！！！")

    return "Successful",200
        
if __name__ == '__main__':
    args = argsProcess()
    logger.info(f"http://127.0.0.1:{args.port}/callback")
    IPS = IPSound(args.appId, args.appCode)
    CONF = Configure(args.deviceMapInfoFile, args.algMapInfoFile)

    #server.run(port=20000,debug=True,host='0.0.0.0')
    WSGIServer(("0.0.0.0", args.port), server).serve_forever()
   
