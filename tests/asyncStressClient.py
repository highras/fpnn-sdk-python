#encoding=utf8
import sys
sys.path.append("..")
import threading
import time

from fpnn import *

class MyCallback(QuestCallback):
    def __init__(self, tester, send_time):
        self.tester = tester
        self.send_time = send_time

    def callback(self, answer):
        if answer.is_error():
            with self.tester.countLock:
                self.tester.recvErrorCount += 1
            if answer.error_code == FPNN_ERROR.FPNN_EC_QUEST_TIMEOUT.value:
                with self.tester.countLock:
                    print("Timeouted occurred when recving.")
            else:
                print("Error occurred when recving..")
        else:
            with self.tester.countLock:
                self.tester.recvCount += 1
            recv_time = int(round(time.time() * 1000 * 1000))
            diff = recv_time - self.send_time
            with self.tester.countLock:
                self.tester.timeCost += diff


class Tester(object):
    def __init__(self, ip, port, threadCount, qps):
        self.ip = ip
        self.port = port
        self.threadCount = threadCount
        self.qps = qps
        self.running = True
        self.countLock = threading.Lock()
        self.sendCount = 0
        self.recvCount = 0
        self.recvErrorCount = 0
        self.timeCost = 0
        self.threads = []

    def __del__(self):
        self.Close()

    def Close(self):
        self.Stop()

    def Stop(self):
        self.running = False
        for thread in self.threads:
            thread.join()

    def Launch(self):
        pqps = self.qps / self.threadCount
        if pqps == 0:
            pqps = 1

        remain = self.qps - pqps * self.threadCount

        for i in range(self.threadCount):
            thread = threading.Thread(target=Tester.TestWorker, args=(self, pqps))
            thread.start()
            self.threads.append(thread)

        if remain > 0:
            thread = threading.Thread(target=Tester.TestWorker, args=(self, remain))
            thread.start()
            self.threads.append(thread)

    def GenQuest(self):
        quest = Quest("two way demo")
        quest.param("quest", "one")
        quest.param("int", 2)
        quest.param("double", 3.3)
        quest.param("boolean", True)
        quest.param("ARRAY", ["first_vec", 4])
        quest.param("MAP", {"map1":"first_map", "map2":True, "map3":5, "map4":5.7, "map5":"中文"});
        return quest

    def ShowStatistics(self):
        sleepSeconds = 3
        send = 0
        recv = 0
        recvError = 0
        timecost = 0

        while self.running:
            start = int(round(time.time() * 1000 * 1000))
            time.sleep(sleepSeconds)

            s = 0
            with self.countLock:
                s = self.sendCount
            r = 0
            with self.countLock:
                r = self.recvCount
            re = 0
            with self.countLock:
                re = self.recvErrorCount
            tc = 0
            with self.countLock:
                tc = self.timeCost

            ent = int(round(time.time() * 1000 * 1000))

            ds = s - send
            dr = r - recv
            dre = re - recvError
            dtc = tc - timecost

            send = s
            recv = r
            recvError = re
            timecost = tc

            real_time = ent - start

            if dr > 0:
                dtc = dtc / dr

            ds = ds * 1000 * 1000 / real_time
            dr = dr * 1000 * 1000 / real_time

            print("time interval: " + str(real_time / 1000.0) + " ms, recv error: " + str(dre))
            print("[QPS] send: " + str(ds) + ", recv: " + str(dr) + ", per quest time cost: " + str(dtc) + " usec")

    def TestWorker(self, obj):
        qps = obj
        msec = 1000 / qps
        with self.countLock:
            print("-- qps: " + str(qps) + ", sleep milliseconds interval: " + str(msec))
        client = TCPClient(self.ip, self.port)

        if not client.connect():
            with self.countLock:
                print("Client sync connect remote server " + self.ip + ":" + str(self.port) + " failed.")
        
        while self.running:
            quest = self.GenQuest()
            send_time = int(round(time.time() * 1000 * 1000))
            client.send_quest(quest, MyCallback(self, send_time))

            with self.countLock:
                self.sendCount += 1

            sent_time = int(round(time.time() * 1000 * 1000))
            real_usec = msec * 1000 - (sent_time - send_time)
            if real_usec > 1000:
                time.sleep(real_usec / 1000.0 / 1000.0)
            elif real_usec > 500:
                time.sleep(0.001)
        client.close()


if  __name__=="__main__":
    if len(sys.argv) != 5:
        print("Usage: asyncStressClient.py <ip> <port> <connections> <totalQPS>")
        exit(0)

    tester = Tester(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    tester.Launch()
    tester.ShowStatistics()