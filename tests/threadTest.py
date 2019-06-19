# coding: utf-8
import sys
sys.path.append("../")
import threading
import time
import random
import Fpnn

lock = threading.Lock()
seq = 0

client = Fpnn.TCPClient('localhost', 13697)

def getSeq():
    global lock, seq
    with lock:
        seq += 1
        return seq

class MyCallback(Fpnn.FpnnCallback):
    def __init__(self, seqNum):
        self.seqNum = seqNum

    def callback(self, answer, exception):
        if exception == None:
            readSeqNum = int(answer['seqNum'])
            if readSeqNum != self.seqNum:
                print "exception: seqnum wrong\n"
        else:
            print "exception: " + exception.message + "\n"

def asyncTest():
    global client
    while (True):
        seqNum = getSeq()
        client.sendQuest('test', {'seqNum': seqNum}, MyCallback(seqNum))
        time.sleep(random.random())

def main():
    threads = []
    for i in range(0, 20):
        t = threading.Thread(target=asyncTest, args=())
        t.setDaemon(True)
        t.start()
        threads.append(t)

    while (True):
        time.sleep(1)

if __name__ == '__main__':
    main()
