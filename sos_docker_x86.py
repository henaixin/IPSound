#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import os
import re
import time
import getopt

if sys.version > '3':
    PY3 = True
else:
    PY3 = False

dockerName = "sos-server"
dockerImage = "sos-server-x86:latest"

HTTP_PORT = 80
HTTPS_PORT = 443
SOS_AS_WS_PORT = 8046
FLV_PUSH_PORT = 1935
FLV_PULL_PORT = 8280
FLV_PULL_PORT_NUM = 6
FREESWITCH_SIP_PORT = 6560
FREESWITCH_WEBRTC_PORT = 7443
FREESWITCH_RTP_PORT = 16000
FREESWITCH_RTP_PORT_NUM = 400

# HTTP_PORT = 81
# HTTPS_PORT = 443
# SOS_AS_WS_PORT = 2132
# FLV_PUSH_PORT = 1234
# FLV_PULL_PORT = 4321
# FLV_PULL_PORT_NUM = 6
# FREESWITCH_SIP_PORT = 2543
# FREESWITCH_WEBRTC_PORT = 7444
# FREESWITCH_RTP_PORT = 20000
# FREESWITCH_RTP_PORT_NUM = 2

ipReg = re.compile('^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$')

pendingPorts = []


def system(command):
    return os.system("sudo " + command)

def popen(command):
    return os.popen("sudo " + command)

def exit():
    print("bye!")
    sys.exit(0)

def ipInput(tip = "", defaultValue = ""):
    try:
        if PY3:
            ret = input("%s[default:%s]: " % (tip, defaultValue))
        else:
            ret = raw_input("%s[default:%s]: " % (tip, defaultValue))
    except Exception as e:
        return (False, "")
    if ret:
        return (ipReg.match(ret), ret)
    else:
        return (True, defaultValue)

def yesNoInput(tip = ""):
    try:
        if PY3:
            ret = input("%s(y/n): " % tip)
        else:
            ret = raw_input("%s(y/n): " % tip)
    except Exception as e:
        return False
    if ret == "y" or ret == "yes":
        return True
    return False

def portInput(tip = "", defaultValue = 0, num = 0):
    try:
        port = defaultValue
        ret = ""
        if num:
            if PY3:
                ret = input("%s[default:%s-%s(total: %s)]: " % (tip, port, port + num - 1, num))
            else:
                ret = raw_input("%s[default:%s-%s(total: %s)]: " % (tip, port, port + num - 1, num))
        else:
            if PY3:
                ret = input("%s[default:%s]: " % (tip, port))
            else:
                ret = raw_input("%s[default:%s]: " % (tip, port))
        if ret != "":
            port = int(ret)
    except Exception as e:
        return (False, ret)
    
    if 0 < port < 65535:
        return (True, port)
    else:
        return (False, port)

def checkPortUsed(port, protocal = "tcp", col = 3):

    if protocal == "tcp" or protocal == "udp":
        for pp in pendingPorts:
            if pp.get("port") == port and pp.get("protocal") == protocal:
                return (True, pp.get("owner"))
    else:
        for pp in pendingPorts:
            if pp.get("port") == port:
                return (True, pp.get("owner"))
    
    cmdNetType = protocal == "tcp" and "t" or "udp" and "u" or ""
    portRet = popen("netstat -anp%s | grep :%s" % (cmdNetType, port))
    lines = portRet.readlines()
    for line in lines:
        items = line.split()
        if len(items) > col:
            if items[col].endswith(":%s" % port):
                return (True, len(items) >= 7 and items[6] or "")
    return (False, "")

def checkDocker():
    """检查本机docker是否安装"""
    print("check docker...")
    dockerVersion = popen("docker --version")
    line = dockerVersion.readline()
    if line:
        print("your docker version: %s" % line)
        versions = line.split()
        versionIndex = -1
        for (index, v) in enumerate(versions):
            if v == "version":
                versionIndex = index
                break
        
        if versionIndex != -1:
            version = versions[versionIndex + 1]
            versionSps = re.split(r"[^0-9]", version)
            if len(versionSps) >= 3:
                try:
                    first = int(versionSps[0])
                    sec = int(versionSps[1])
                    thrid = int(versionSps[2])
                    if first * 10000 + sec * 100 + thrid < 18 * 10000 + 9 * 100 + 7:
                        print("your docker version < 18.09.7, please update!")
                        return False
                    else:
                        return True
                except Exception as e:
                    pass
                    
        return yesNoInput("WARNING: please check docker version >= 20.10.9 manually")
    else:
        print("you have no docker, version >= 20.10.9!")
        return False

        # select = yesNoInput("本机没有安装docker，是否安装？")
        # if select:
        #     ret1 = 0
        #     ret1 |= system("yum install -y yum-utils device-mapper-persistent-data lvm2 --skip-broken")
        #     ret1 |= system("yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo")
        #     ret1 |= system("sed -i 's/download.docker.com/mirrors.aliyun.com\/docker-ce/g' /etc/yum.repos.d/docker-ce.repo")
        #     ret1 |= system("yum makecache fast")
        #     ret1 |= system("yum install -y docker-ce")
        #     return not ret1
        # else:
        #     print("本机没有安装docker")
        #     return False

    return True

def loadDockerImage():
    """加载docker镜像"""
    print("loading docker image...")
    system("docker stop %s" % dockerName)
    system("docker rm %s" % dockerName)
    system("docker rmi %s" % dockerImage)
    ret = system("gunzip -c sos-image-x86.tar.gz | docker load")
    print("completed!")
    return (not ret)

def unloadDockerImage():
    """删除docker镜像"""
    print("unloading docker image...")
    system("docker stop %s" % dockerName)
    system("docker rm %s" % dockerName)
    system("docker rmi %s" % dockerImage)
    print("completed!")
    return True

def startDocker(dockerName):
    """启动docker实例"""
    print("start docker...")
    ret = system("docker start %s" % dockerName)
    print("completed!")
    return (not ret)

def stopDocker(dockerName):
    """停止docker实例"""
    print("stop docker...")
    ret = system("docker stop %s" % dockerName)
    print("completed!")
    return (not ret)

def configIp():
    """配置IP地址"""
    errorType = "server ip(advertised ip)"
    
    def ethFilter(x):
        x = x[-1] == '\n' and x[0:-1] or x
        x = x[-1] == ':' and x[0:-1] or x
        return x

    ethsRet = popen("ifconfig | awk -F '[ ]+' '{print $1}'")
    eths = [ethFilter(x) for x in ethsRet.readlines() if x and x != '\n' and x != 'lo\n' and x != 'lo:\n' and not x.startswith("docker")]
    configs = []
    for eth in eths:
        ethRet = popen("ifconfig %s | awk 'NR==2{print $2}'" % (eth))
        ip = ethRet.readline()
        if ipReg.match(ip[0:-1]):
            configs.append({
                "eth": eth,
                "ip": ip[0:-1],
            })
        elif ipReg.match(ip[5:-1]):
            configs.append({
                "eth": eth,
                "ip": ip[5:-1],
            })
    if configs:
        errorType = "your eth ip: \n" + "\n".join(["%s: %s" % (c.get("eth"), c.get("ip")) for c in configs]) + "\n\n" + errorType
 
    while 1:
        ret, ip = ipInput(errorType, len(configs) >= 1 and configs[0].get("ip") or "")
        if not ret:
            errorType = "ip:%s is illegal, please input again" % (ip)
            continue
        else:
            return ip

def configHttpsPort():
    """配置nginx https的端口"""
    errorType = "server https port"
    while 1:
        # ret, port = portInput(errorType, HTTPS_PORT)
        ret , port = True,11000
        if not ret:
            errorType = "port:%s is illegal, please input again" % (port)
            continue
        else:
            used, pid = checkPortUsed(port, "tcp")
            if used:
                errorType = "port:%s has be used by '%s', please choice another one" % (port, pid)
                continue
            else:
                pendingPorts.append({"port": port, "protocal": "tcp", "owner": "server https port"})
                return port

def configAsWebsocketPort():
    """配置业务服务器websocket端口"""
    errorType = "server websocket port"
    while 1:
        # ret, port = portInput(errorType, SOS_AS_WS_PORT)
        ret, port = True,11001
        if not ret:
            errorType = "port:%s is illegal, please input again" % (port)
            continue
        else:
            used, pid = checkPortUsed(port, "tcp")
            if used:
                errorType = "port:%s has be used by '%s', please choice another one" % (port, pid)
                continue
            else:
                pendingPorts.append({"port": port, "protocal": "tcp", "owner": "server websocket port"})
                return port

def configFlvPushPort():
    """配置视频推流的端口"""
    errorType = "video stream(push) start port"
    while 1:
        # ret, port = portInput(errorType, FLV_PUSH_PORT)
        ret, port = True,11002
        if not ret:
            errorType = "port:%s is illegal, please input again" % (port)
            continue
        else:
            used, pid = checkPortUsed(port, "tcp")
            if used:
                errorType = "port:%s has be used by '%s', please choice another one" % (port, pid)
                continue
            else:
                pendingPorts.append({"port": port, "protocal": "tcp", "owner": "video stream(push) start port"})
                return port

def configFlvPullPort():
    """配置视频拉流起始端口"""
    errorType = "video stream(pull) start port"
    while 1:
        # ret, port = portInput(errorType, FLV_PULL_PORT, FLV_PULL_PORT_NUM)
        ret, port = True,11003
        if not ret:
            errorType = "port:%s is illegal, please input again" % (port)
            continue
        else:
            ports = [x for x in range(port, port + FLV_PULL_PORT_NUM)]
            for checkPort in ports:
                used, pid = checkPortUsed(checkPort, "tcp")
                if used:
                    errorType = "port:%s has be used by '%s', please choice another one" % (checkPort, pid)
                    break
            else:
                for p in ports:
                    pendingPorts.append({"port": p, "protocal": "tcp", "owner": "video stream(pull) start port"})
                return ports

def configFreeswitchWebrtcPort():
    """配置音频webrtc端口"""
    errorType = "audio webrtc port"
    while 1:
        # ret, port = portInput(errorType, FREESWITCH_WEBRTC_PORT)
        ret, port = True,11011
        if not ret:
            errorType = "port:%s is illegal, please input again" % (port)
            continue
        else:
            used, pid = checkPortUsed(port, "tcp")
            if used:
                errorType = "port:%s has be used by '%s', please choice another one" % (port, pid)
                continue
            else:
                pendingPorts.append({"port": port, "protocal": "tcp", "owner": "audio webrtc port"})
                return port

def configFreeswitchSipPort():
    """配置音频sip端口"""
    errorType = "audio sip port"
    while 1:
        # ret, port = portInput(errorType, FREESWITCH_SIP_PORT)
        ret, port = True,11010
        if not ret:
            errorType = "port:%s is illegal, please input again" % (port)
            continue
        else:
            used, pid = checkPortUsed(port, "tcp")
            if used:
                errorType = "port:%s has be used by '%s', please choice another one" % (port, pid)
                continue
            else:
                pendingPorts.append({"port": port, "protocal": "tcp", "owner": "audio sip port"})
                return port

def configFreeswitchRtpPorts():
    """配置音频rtp端口"""
    errorType = "audio rtp start port"
    while 1:
        # ret, port = portInput(errorType, FREESWITCH_RTP_PORT, FREESWITCH_RTP_PORT_NUM)
        ret, port = True,11100
        if not ret:
            errorType = "port:%s is illegal, please input again" % (port)
            continue
        else:

            ports = [x for x in range(port, port + FREESWITCH_RTP_PORT_NUM)]
            for checkPort in ports:
                used, pid = checkPortUsed(checkPort, "udp")
                if used:
                    errorType = "port:%s has be used by '%s', please choice another one" % (checkPort, pid)
                    break
            else:
                for p in ports:
                    pendingPorts.append({"port": p, "protocal": "udp", "owner": "audio rtp port"})
                return ports

def runDocker(httpsPort, asWebsocketPort, flvPushPort, flvPullPorts, freeswitchWebrtcPort, freeswitchSipPort, freeswitchRtpPorts):
    runStatusRet = popen("docker ps -f name=%s --format \"{{.Names}}\n{{.Status}}\"" % (dockerName))
    runStatuses = runStatusRet.readlines()
    if len(runStatuses) >= 2:
        if runStatuses[0].startswith(dockerName):
            if runStatuses[1].startswith("Up"):
                if not yesNoInput("%s has started, now stop it?" % dockerName):
                    return False
                print("stopping %s..." % dockerName)
                system("docker stop %s" % (dockerName))

            if not yesNoInput("%s has existed, delete(ATTENTION: all data will be lost)?" % dockerName):
                return False
            print("deleting %s..." % dockerName)
            system("docker rm %s" % (dockerName))

    # 从image中run docker
    cmd = "docker run -itd --name=%s" % dockerName
    cmd += " -p %s-%s:%s-%s/udp" % (freeswitchRtpPorts[0], freeswitchRtpPorts[-1], freeswitchRtpPorts[0], freeswitchRtpPorts[-1])
    cmd += " -p %s-%s:%s-%s/tcp" % (flvPullPorts[0], flvPullPorts[-1], FLV_PULL_PORT, FLV_PULL_PORT + FLV_PULL_PORT_NUM - 1)
    cmd += " -p %s:%s/tcp" % (httpsPort, HTTPS_PORT)
    cmd += " -p %s:%s/tcp" % (asWebsocketPort, SOS_AS_WS_PORT)
    cmd += " -p %s:%s/tcp" % (flvPushPort, flvPushPort)
    cmd += " -p %s:%s/tcp" % (freeswitchWebrtcPort, FREESWITCH_WEBRTC_PORT)
    cmd += " -p %s:%s/tcp" % (freeswitchSipPort, FREESWITCH_SIP_PORT)
    cmd += " --restart=always --privileged %s /sbin/init" % dockerImage
    print("create sos docker: %s" % cmd)
    ret = system(cmd)
    print("result: %s" % (not ret))
    return bool(not ret)

def editAsConf(hostIp, httpsPort, asWebsocketPort, flvPushPort, flvPullPorts, freeswitchWebrtcPort, freeswitchSipPort):
    # 按照ip和port要求修改配置文件
    # as app.conf

    print("write sos api server configuration...")

    system("docker cp %s:/work/sos/api/conf/app.conf ./" % dockerName)
    system("docker cp ./app.conf %s:/work/sos/api/conf/app.conf.%s" % (dockerName, time.strftime("%Y%m%d%H%M%S",time.localtime())))

    file = open("./app.conf",'r')
    startLine = 0
    endLine = 0
    newLines = []
    try:
        lines = file.readlines()
        for (index, line) in enumerate(lines):
            if line.startswith("[docker"):
                startLine = index + 1
                newLines.append(line)
            elif startLine and line[0] == "[":
                endLine = index
                newLines.append(line)
            elif startLine and not endLine:
                if line.startswith("ip"):
                    newLines.append("ip = \"%s\"\n" % hostIp)
                elif line.startswith("apiPort"):
                    newLines.append("apiPort = %s\n" % httpsPort)
                elif line.startswith("wsPort"):
                    newLines.append("wsPort = %s\n" % asWebsocketPort)
                elif line.startswith("fsPort"):
                    newLines.append("fsPort = %s\n" % freeswitchSipPort)
                elif line.startswith("fsWsPort"):
                    newLines.append("fsWsPort = %s\n" % freeswitchWebrtcPort)
                elif line.startswith("rtmpPort"):
                    newLines.append("rtmpPort = %s\n" % flvPushPort)
                elif line.startswith("flvPorts"):
                    newLines.append("flvPorts = \"%s\"\n" % ",".join([str(x) for x in flvPullPorts]))
                else:
                    newLines.append(line)
            else:
                newLines.append(line)
    finally:
        file.close()
        with open("./app.conf",'w') as f:
            f.writelines(newLines)
        system("docker cp ./app.conf %s:/work/sos/api/conf/app.conf" % (dockerName))
        system("rm -rf ./app.conf")

    print("completed!")

    return True


def editFreeswitchConf(hostIp, freeswitchRtpPorts):

    print("write audio server configuration...")

    # 改ip
    system("docker cp %s:/usr/local/freeswitch/conf/online_vars.xml ./" % dockerName)
    system('sed -i "/online_proxy_ip/c\\  <X-PRE-PROCESS cmd=\\"set\\" data=\\"online_proxy_ip=%s\\"/>" ./online_vars.xml' % (hostIp))
    system("docker cp ./online_vars.xml %s:/usr/local/freeswitch/conf/online_vars.xml" % (dockerName))
    system("rm -rf ./online_vars.xml")

    # 改端口
    system("docker cp %s:/usr/local/freeswitch/conf/autoload_configs/switch.conf.xml ./" % dockerName)
    system("docker cp ./switch.conf.xml %s:/usr/local/freeswitch/conf/autoload_configs/switch.conf.xml.%s" % (dockerName, time.strftime("%Y%m%d%H%M%S",time.localtime())))
    system('sed -i "/rtp-start-port/c\\    <param name=\\"rtp-start-port\\" value=\\"%s\\"/>" ./switch.conf.xml' % (freeswitchRtpPorts[0]))
    system('sed -i "/rtp-end-port/c\\    <param name=\\"rtp-end-port\\" value=\\"%s\\"/>" ./switch.conf.xml' % (freeswitchRtpPorts[-1]))
    system("docker cp ./switch.conf.xml %s:/usr/local/freeswitch/conf/autoload_configs/switch.conf.xml" % (dockerName))
    system("rm -rf ./switch.conf.xml")

    print("completed!")
    return True

def editFlvConf(flvPushPort, flvPullPorts):

    print("write video server configuration...")

    system("docker cp %s:/usr/local/flv/flv.conf ./" % dockerName)
    system('sed -i "/listen 1935/c\\        listen %s so_keepalive=5s:1:1;" ./flv.conf' % (flvPushPort))
    system("docker cp ./flv.conf %s:/usr/local/flv/flv.conf" % (dockerName))
    system("rm -rf ./flv.conf")

    print("completed!")
    return True

def extra():
    return True

def systemctlCheckStatus(dockerName, appName):
    cmd = "docker exec -it %s systemctl show %s --no-page | grep ActiveState" % (dockerName, appName)
    ret = popen(cmd)
    return "ActiveState=active" in ret.readline()
    
def psCheckStatus(dockerName, appName):
    cmd = "docker exec -it %s ps -ef | grep %s | grep -v grep | awk '{print $2}'" % (dockerName, appName)
    ret = popen(cmd)
    return ret.readline() != ''

def systemctlStop(dockerName, appName):
    ret = system("docker exec -it %s systemctl stop %s" % (dockerName, appName))
    return (not ret)

def systemctlStart(dockerName, appName):
    ret = system("docker exec -it %s systemctl start %s" % (dockerName, appName))
    return (not ret)

def psStop(dockerName, appName):
    pidRet = popen("docker exec -it %s ps -ef | grep %s | grep -v grep | awk '{print $2}'" % (dockerName, appName))
    line = pidRet.readline()
    cols = line.split()
    pid = len(cols) >= 1 and cols[0] or 0
    if not pid:
        return False

    system("docker exec -it %s kill -9 %s" % (dockerName, pid))
    return True

def psStart(dockerName, cmd):
    ret = system("docker exec -it %s %s" % (dockerName, cmd))
    return (not ret)

servers = [
    {
        "name": "https server",
        "processName": "nginx",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
    {
        "name": "mysql",
        "processName": "mysql",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
    {
        "name": "redis",
        "processName": "redis",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
    {
        "name": "video server",
        "processName": "flv",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
    {
        "name": "audio server",
        "processName": "freeswitch",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
    {
        "name": "conference manager server",
        "processName": "cm",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
    {
        "name": "sos api server",
        "processName": "sosapi",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
    {
        "name": "sos websocket server",
        "processName": "sosws",
        "description": "",
        "checkFun": systemctlCheckStatus,
        "stopFun": systemctlStop,
        "startFun": systemctlStart,
    },
]

def init(args):
    print("run init")
    ret = popen("arch")
    if ret:
        if not ret.readline().startswith("x86_64"):
            print("the installer only available on x86 systems")
            exit()
    else:
        if not yesNoInput("get your arch error, the installer only available on x86_64 systems"):
            exit()

    # 检查docker安装状态
    ret = checkDocker()
    if not ret:
        exit()

    # 加载镜像
    ret = loadDockerImage()
    if not ret:
        exit()

    # 获取输入的自定义端口配置
    hostIp = configIp()
    if not hostIp:
        exit()

    # httpPort = configHttpPort()
    # if not httpPort:
    #     exit()

    httpsPort = configHttpsPort()
    if not httpsPort:
        exit()

    asWebsocketPort = configAsWebsocketPort()
    if not asWebsocketPort:
        exit()

    flvPushPort = configFlvPushPort()
    if not flvPushPort:
        exit()

    flvPullPorts = configFlvPullPort()
    if not flvPullPorts:
        exit()

    freeswitchSipPort = configFreeswitchSipPort()
    if not freeswitchSipPort:
        exit()

    freeswitchWebrtcPort = configFreeswitchWebrtcPort()
    if not freeswitchWebrtcPort:
        exit()

    freeswitchRtpPorts = configFreeswitchRtpPorts()
    if not freeswitchRtpPorts:
        exit()

    # 输出统计信息，最终确认
    print("\n======================== Result =========================\n")
    print("server ip(advertised ip): %s" % hostIp)
    print("server https port(tcp): %s" % httpsPort)
    print("server websocket port(tcp): %s" % asWebsocketPort)
    print("video push stream port(tcp): %s" % flvPushPort)
    print("video pull stream port(tcp): %s - %s(total: %s)" % (flvPullPorts[0], flvPullPorts[-1], len(flvPullPorts)))
    print("audio webrtc port(tcp): %s" % freeswitchWebrtcPort)
    print("audio sip port(tcp): %s" % freeswitchSipPort)
    print("audio rtp port(udp): %s - %s(total: %s)" % (freeswitchRtpPorts[0], freeswitchRtpPorts[-1], len(freeswitchRtpPorts)))
    print("\n=======================================================\n")

    client = "\n***************** Client Config ***********************\n"
    client += "*\n"
    client += "* server ip on PC \t-> %s:%s \n" % (hostIp, httpsPort)
    client += "* server ip on device \t-> %s:%s \n" % (hostIp, httpsPort)
    client += "*\n"
    client += "*******************************************************\n\n\n"
    print(client)

    firewall = "\n****************** Firewall(Allow) *********************\n" 
    firewall += "*\n"
    firewall += "* %s tcp \n" % (httpsPort)
    firewall += "* %s tcp \n" % (asWebsocketPort)
    firewall += "* %s tcp \n" % (flvPushPort)
    firewall += "* %s - %s tcp (total: %s)\n" % (flvPullPorts[0], flvPullPorts[-1], len(flvPullPorts))
    firewall += "* %s tcp \n" % (freeswitchWebrtcPort)
    firewall += "* %s tcp \n" % (freeswitchSipPort)
    firewall += "* %s - %s udp (total: %s)\n" % (freeswitchRtpPorts[0], freeswitchRtpPorts[-1], len(freeswitchRtpPorts))
    firewall += "*\n"
    firewall += "********************************************************\n\n\n"
    print(firewall)

    with open("./result.txt", "w") as f:
        f.write(client)
        f.write(firewall)

    if not yesNoInput("please confirm the above information."):
        exit()
    else:
        print("the above information has saved in result.txt")

    if not runDocker(httpsPort, asWebsocketPort, flvPushPort, flvPullPorts, freeswitchWebrtcPort, freeswitchSipPort, freeswitchRtpPorts):
        exit()

    if not editAsConf(hostIp, httpsPort, asWebsocketPort, flvPushPort, flvPullPorts, freeswitchWebrtcPort, freeswitchSipPort):
        exit()

    if not editFreeswitchConf(hostIp, freeswitchRtpPorts):
        exit()

    if not editFlvConf(flvPushPort, flvPullPorts):
        exit()

    if not extra():
        exit()

    # 重启docker
    print("rebooting %s..." % dockerName)
    system("docker restart %s" % dockerName)
    print("install completed!")
    return True

def uninit(args):
    print("run uninit")
    unloadDockerImage()
    return True

def status(args):
    print("run status")
    print("========================== server status ==========================\n")
    print("  %2s\t%-15s\t%-25s\t%s\n" % ("id", "process", "description", "result"))
    for (index, server) in enumerate(servers):
        ret = server["checkFun"](dockerName, server["processName"])
        print("  %2s\t%-15s\t%-25s\t%s" % (index + 1, server["processName"], server["name"], ret and "OK" or "ERROR"))
    print("\n===================================================================")
    return True

def restart(args):
    print("run restart")
    subcmds = [
        {"param": "docker", "description": "restart the docker"},
    ]
    subcmds.extend([{"param": x["processName"], "description": "restart %s in docker" % x["processName"]} for x in servers])
    if len(args) == 0 or args[0] == "help":
        exeName = os.path.split(sys.argv[0])[-1]
        print("\nUsage of python %s restart:" % exeName)
        print("\n\tpython %s restart [process]\tprocess: %s\n" % (exeName, ", ".join([x["processName"] for x in servers])))
        for subcmd in subcmds:
            print("\tpython %s restart %-10s \t # %s" % (exeName, subcmd["param"], subcmd["description"]))
        print("")
    elif args[0] == "docker":
        print("docker restarting...")
        system("docker restart %s" % dockerName)
        print("completed!")
    else:
        server = None
        for x in servers:
            if x["processName"] == args[0]:
                server = x
                break
        if not server:
            print("there have no server '%s', available server as follows:" % args[0])
            print("\t%s\n" % ", ".join([x["processName"] for x in servers]))
        else:
            print("%s(%s) restarting..." % (server["processName"], server["name"]))
            server["stopFun"](dockerName, server["processName"])
            server["startFun"](dockerName, server["processName"])
            print("completed!")
    return True

def getLog(args):
    print("run get-log")
    dirName = "sos-logs-%s" % time.strftime("%Y%m%d%H%M%S",time.localtime())
    system("mkdir -p %s/nginx/log" % dirName)
    system("docker cp %s:/var/log/nginx %s/nginx/log" % (dockerName, dirName))
    system("mkdir -p %s/nginx/conf" % dirName)
    system("docker cp %s:/etc/nginx/nginx.conf %s/nginx/conf" % (dockerName, dirName))

    system("mkdir -p %s/flv/log" % dirName)
    system("docker cp %s:/var/log/flv %s/flv/log" % (dockerName, dirName))
    system("mkdir -p %s/flv/conf" % dirName)
    system("docker cp %s:/usr/local/flv/flv.conf %s/flv/conf" % (dockerName, dirName))

    system("mkdir -p %s/freeswitch/log" % dirName)
    system("docker cp %s:/var/log/ldq/freeswitch %s/freeswitch/log" % (dockerName, dirName))
    system("mkdir -p %s/freeswitch/conf" % dirName)
    system("docker cp %s:/usr/local/freeswitch/conf %s/freeswitch" % (dockerName, dirName))

    system("mkdir -p %s/cm/log" % dirName)
    system("docker cp %s:/var/log/ldq/cm %s/cm/log" % (dockerName, dirName))
    system("mkdir -p %s/cm/conf" % dirName)
    system("docker cp %s:/usr/local/ldq/cm/conf %s/cm" % (dockerName, dirName))

    system("mkdir -p %s/sosapi/log" % dirName)
    system("docker cp %s:/work/sos/api/logs %s/sosapi/log" % (dockerName, dirName))
    system("mkdir -p %s/sosapi/conf" % dirName)
    system("docker cp %s:/work/sos/api/conf %s/sosapi" % (dockerName, dirName))

    system("mkdir -p %s/sosws/log" % dirName)
    system("docker cp %s:/work/sos/ws/logs %s/sosws/log" % (dockerName, dirName))
    system("mkdir -p %s/sosws/conf" % dirName)
    system("docker cp %s:/work/sos/ws/conf %s/sosws" % (dockerName, dirName))
    
    system("tar zcf {dirName}.tar.gz {dirName}".format(dirName=dirName))
    system("rm -rf %s" % dirName)

    print("the logs are all packaged in {dirName}.tar.gz".format(dirName=dirName))
    return True

def changeIp(args):
    # 按照ip要求修改配置文件
    # as app.conf
    print("run change-ip")

    if len(args) == 0 or args[0] == "help":
        exeName = os.path.split(sys.argv[0])[-1]
        print("\nUsage of python %s change-ip:" % exeName)
        print("\n\tpython %s change-ip [ip]" % exeName)
        print("")
        return False
    else:
        ip = args[0]
        if not re.match(r'(([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])\.){3}([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])', ip):
            print("'%s' is not ip address" % ip)
            return False

    print("write sos api server configuration...")

    system("docker cp %s:/work/sos/api/conf/app.conf ./" % dockerName)
    system("docker cp ./app.conf %s:/work/sos/api/conf/app.conf.%s" % (dockerName, time.strftime("%Y%m%d%H%M%S",time.localtime())))

    file = open("./app.conf",'r')
    startLine = 0
    endLine = 0
    newLines = []
    try:
        lines = file.readlines()
        for (index, line) in enumerate(lines):
            if line.startswith("[docker"):
                startLine = index + 1
                newLines.append(line)
            elif startLine and line[0] == "[":
                endLine = index
                newLines.append(line)
            elif startLine and not endLine:
                if line.startswith("ip"):
                    newLines.append("ip = \"%s\"\n" % ip)
                else:
                    newLines.append(line)
            else:
                newLines.append(line)
    finally:
        file.close()
        with open("./app.conf",'w') as f:
            f.writelines(newLines)
        system("docker cp ./app.conf %s:/work/sos/api/conf/app.conf" % (dockerName))
        system("rm -rf ./app.conf")

    print("write audio server configuration...")

    # 改ip
    system("docker cp %s:/usr/local/freeswitch/conf/online_vars.xml ./" % dockerName)
    system('sed -i "/online_proxy_ip/c\\  <X-PRE-PROCESS cmd=\\"set\\" data=\\"online_proxy_ip=%s\\"/>" ./online_vars.xml' % (ip))
    system("docker cp ./online_vars.xml %s:/usr/local/freeswitch/conf/online_vars.xml" % dockerName)
    system("rm -rf ./online_vars.xml")

    system("docker exec -it %s systemctl restart sosapi" % dockerName)
    system("docker exec -it %s systemctl restart freeswitch" % dockerName)

    print("completed!")
    return True

def changePort(args):
    print("run change-port")
    return True

def changeHttpsCerts(args):
    print("run change-https-certs")

    if len(args) < 2 or args[0] == "help":
        exeName = os.path.split(sys.argv[0])[-1]
        print("\nUsage of python %s change-https-certs:" % exeName)
        print("\n\tpython %s change-https-certs [ssl_certificate] [ssl_certificate_key]\n" % exeName)
        print("\tssl_certificate : a file with the certificate in the PEM format - a public key like nginx.pem or nginx.crt ")
        print("\tssl_certificate_key : a file with the secret key in the PEM format - a private key like nginx.key\n")
        return False
    else:
        pemPath = args[0]
        keyPath = args[1]

        # check file exists
        if not os.path.exists(pemPath):
            print("ssl_certificate path: '%s' dose not exist" % pemPath)
            return False

        if not os.path.exists(keyPath):
            print("ssl_certificate_key path: '%s' dose not exist" % keyPath)
            return False

        # backup
        timestamp = time.strftime("%Y%m%d%H%M%S",time.localtime())
        system("docker exec -it %s mv /etc/certs/nginx.pem /etc/certs/nginx.pem.%s" % (dockerName, timestamp))
        system("docker exec -it %s mv /etc/certs/nginx.key /etc/certs/nginx.key.%s" % (dockerName, timestamp))

        system("cp -rf %s ./nginx.pem" % pemPath)
        system("cp -rf %s ./nginx.key" % keyPath)

        # new file to docker
        system("docker cp ./nginx.pem %s:/etc/certs/nginx.pem" % dockerName)
        system("docker cp ./nginx.key %s:/etc/certs/nginx.key" % dockerName)
        system("docker exec -it %s cat /etc/certs/nginx.pem /etc/certs/nginx.key > /etc/certs/websocket.pem" % dockerName)

        system("rm -rf ./nginx.pem")
        system("rm -rf ./nginx.key")

        # reload nginx flv, restart freeswitch
        system("docker exec -it %s /usr/local/flv/sbin/flv -s reload" % dockerName)
        system("docker exec -it %s nginx -s reload" % dockerName)
        for x in servers:
            if x["processName"] == "freeswitch":
                x["stopFun"](dockerName, x["processName"])
                x["startFun"](dockerName, x["processName"])
                break
    print("completed!")
    return True

cmds = [
    {
        "cmd": "init",
        "function": init,
        "description": "install sos docker"
    },
    {
        "cmd": "uninit",
        "function": uninit,
        "description": "uninstall sos docker"
    },
    {
        "cmd": "status",
        "function": status,
        "description": "sos docker status"
    },
    {
        "cmd": "restart",
        "function": restart,
        "description": "restart sos docker",
    },
    {
        "cmd": "get-log",
        "function": getLog,
        "description": "get sos docker log"
    },
    {
        "cmd": "change-ip",
        "function": changeIp,
        "description": "change the advertised ip"
    },
    # {
    #     "cmd": "change-port",
    #     "function": changePort,
    #     "description": "change the port"
    # },
    {
        "cmd": "change-https-certs",
        "function": changeHttpsCerts,
        "description": "change https certs"
    },
]

def help():
    exeName = os.path.split(sys.argv[0])[-1]
    print("\nUsage of %s:" % exeName)
    print("\n\tpython %s [cmd]\tcmd: %s\n" % (exeName, ", ".join([c["cmd"] for c in cmds])))
    for c in cmds:
        print("\tpython %s %-20s \t# %s" % (exeName, c["cmd"], c["description"]))
    print("\tpython %s %s\n" % (exeName, "help"))


if __name__ == "__main__":
    print("python %s" % sys.version)

    # get input args
    opts,args = getopt.getopt(sys.argv[1:],"h",["help"])
    cmd = len(args) >= 1 and args[0] or "help"
    
    # find cmd 
    cmdObj = None
    for c in cmds:
        if c["cmd"] == cmd:
            cmdObj = c
            break
    
    # run function if cmd found
    if cmdObj:
        fun = cmdObj["function"]
        if fun:
            fun(sys.argv[2:])
        else:
            help()
    else:
        help()


