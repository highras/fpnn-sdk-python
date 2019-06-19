# coding: utf-8
from __future__ import print_function
import sys
sys.path.append("../")
import time
import struct
import threading
from datetime import datetime
import Fpnn

class MyConnectedCallback(Fpnn.FpnnConnectedCallback):
    def callback(self):
        print("+", end='')

class MyConnectionWillCloseCallback(Fpnn.FpnnConnectionWillCloseCallback):
    def callback(self, causedByError):
        if causedByError:
            print("#", end='')
        else:
            print("~", end='')

class MyCallback(Fpnn.FpnnCallback):
    def callback(self, answer, exception):
	if exception == None:
	    print("$", end='')
	else:
	    print("@", end='')

class singleClientConcurrentTest:
    def __init__(self, ip, port):
	self.client = Fpnn.TCPClient(ip, port)
        self.client.setConnectionConnectedCallback(MyConnectedCallback())
        self.client.setConnectionWillCloseCallback(MyConnectionWillCloseCallback())
	
    def showSignDesc(self):
	print("Sign:")
	print("    +: establish connection")
	print("    ~: close connection")
	print("    #: connection error")

	print("    *: send sync quest")
	print("    &: send async quest")

	print("    ^: sync answer Ok")
	print("    ?: sync answer exception")
	print("    |: sync answer exception by connection closed")
	print("    (: sync operation fpnn exception")
	print("    ): sync operation unknown exception")

	print("    $: async answer Ok")
	print("    @: async answer exception")
	print("    ;: async answer exception by connection closed")
	print("    {: async operation fpnn exception")
	print("    }: async operation unknown exception")

	print("    !: close operation")
	print("    [: close operation fpnn exception")
	print("    ]: close operation unknown exception")
  
    def testThread(self, count):
	act = 0
	for i in range(count):
	    index = datetime.now().microsecond % 64
	    if i >= 10:
		if index < 6:
		    act = 2
		elif index < 32:
		    act = 1
		else:
		    act = 0
	    else:
		act = index & 0x1
	    try:
		if act == 0 or act == 1:
		    print("&", end='')
		    self.client.sendQuest('test', {'aaa': 'bbb'}, MyCallback(), 5)
		elif act == 2:
		    print("!", end='')
		    self.close()

	    except Exception, e:
                if act == 0:
		    print(')', end='')
		elif act == 1:
		    print('}', end='')
		elif act == 2:
		    print(']', end='') 
        print("finish")
 
    def test(self, threadCount, questCount):
	print("========[ Test: thread " + str(threadCount) + ", per thread quest: " + str(questCount) + " ]==========")
	_threads = []

	for i in range(threadCount):
	    t = threading.Thread(target=singleClientConcurrentTest.testThread, args=(self, questCount))
	    t.setDaemon(True)
            t.start()
            _threads.append(t)

	time.sleep(5)

	for t in _threads:
	    t.join()
        print("join all threads")
        self.client.close()
        print("closed")

    def launch(self):
        self.showSignDesc()
        self.test(3, 30000);
                    
if __name__ == '__main__':
    tester = singleClientConcurrentTest("localhost", 13697) 
    tester.launch()
