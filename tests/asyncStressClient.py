# coding: utf-8
import sys
sys.path.append("../")
import time
import struct
import threading
from datetime import datetime
import Fpnn

class MyCallback(Fpnn.FpnnCallback):

	def __init__(self, instance, send_time):
	    self._instance = instance
	    self._send_time = send_time

	def callback(self, answer, exception):
	    if exception == None:
		self._instance.incRecv()
	
		recv_time = datetime.utcnow()
		diff = recv_time - self._send_time
		self._instance.addTimeCost(int((diff.total_seconds())/86400 ))	
	    else:
		self._instance.incRecvError()

class asyncStressClient:
    def __init__(self, ip, port, thread_num, qps):
        self._ip = ip
        self._port = port
        self._thread_num = thread_num
        self._qps = qps
       	self._send = 0
	self._recv = 0
	self._sendError = 0
	self._recvError = 0
	self._timecost = 0 
	self.locker = threading.Lock()
	self._threads = []

    def __del__(self):
	self.stop()

    def stop(self):
	pass

    def incSend(self): 
	with self.locker:
	    self._send += 1

    def incRecv(self):
	with self.locker:
	    self._recv += 1

    def incSendError(self):
	with self.locker:
	    self._sendError += 1

    def incRecvError(self):
	with self.locker:
	    self._recvError += 1

    def addTimeCost(self, cost):
	with self.locker:
	    self._timecost += cost

    def stop(self):
	for t in self._threads:
	    t.join()

    def launch(self):
	pqps = self._qps / self._thread_num
	if (pqps == 0):
	    pqps = 1
	remain = self._qps - pqps * self._thread_num

	for i in range(0, self._thread_num):
	    t = threading.Thread(target=asyncStressClient.test_worker, args=(self,pqps))
	    t.setDaemon(True)
	    t.start()
	    self._threads.append(t)

	if remain > 0:
	    t = threading.Thread(target=asyncStressClient.test_worker, args=(self,remain))
	    t.setDaemon(True)
	    t.start()
	    self._threads.append(t)
			
    def showStatistics(self):
	sleepSeconds = 3
	send = self._send
	recv = self._recv
	sendError = self._sendError
	recvError = self._recvError
	timecost = self._timecost

	while True:
	    start = datetime.utcnow()
	    time.sleep(sleepSeconds)

	    s = self._send
	    r = self._recv
	    se = self._sendError
	    re = self._recvError
	    tc = self._timecost

	    ent = datetime.utcnow()

	    ds = s - send
	    dr = r - recv
	    dse = se - sendError
	    dre = re - recvError
	    dtc = tc - timecost

	    send = s
	    recv = r
	    sendError = se
	    recvError = re
	    timecost = tc

	    real_time = (ent - start).microseconds

	    ds = ds * 1000  / real_time
	    dr = dr * 1000 / real_time
		
            if dr > 0:
	        dtc = dtc / dr

	    print("time interval: " + str(real_time / 10000.0) + " ms, send error: " + str(dse) + ", recv error: " + str(dre))
	    print("[QPS] send: " + str(ds) + ", recv: " + str(dr) + ", per quest time cost: " + str(dtc) + " usec")

    def test_worker(self, qps):
	usec = 1000 * 1000 / qps

        print("-- qps: " + str(qps) + ", usec: " + str(usec))

	client = Fpnn.TCPClient(self._ip, self._port)
	client.connect()

	while True:
	    send_time = datetime.utcnow()
	
	    try:
                client.sendQuest('test', {"quest": "one"}, MyCallback(self, send_time))
		self.incSend()	
	    except Exception,e: 
		self.incSendError()

            sent_time = datetime.utcnow()
            real_usec = float(float(usec - (sent_time - send_time).microseconds) / 1000000)

            if real_usec > 0:
                time.sleep(1)
	client.close()


if __name__ == '__main__':
    tester = asyncStressClient("localhost", 13697, 5, 5)
    tester.launch()	
    tester.showStatistics()
