# coding: utf-8
import sys
sys.path.append("../")
import threading
import time
import random
import Fpnn

lock = threading.Lock()
seq = 0

client = Fpnn.Client('35.167.185.139', 13099)
f = open('../server-public.pem')
peerPubData = f.read()
f.close()

client.enableEncryptor(peerPubData)


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

def syncTest():
    global client
    while (True):
        seqNum = getSeq()
        try:
            answer = client.sendQuestSync('test', {'seqNum': seqNum})
            readSeqNum = int(answer['seqNum'])
            if readSeqNum != seqNum:
                print "exception: seqnum wrong\n"
        except Exception, e:
            print "exception: " + e.message + "\n"
        time.sleep(random.random())

def main():
    threads = []
    for i in range(0, 20):
        t = threading.Thread(target=asyncTest, args=())
        t.setDaemon(True)
        t.start()
        threads.append(t)

    for i in range(0, 20):
        t = threading.Thread(target=syncTest, args=())
        t.setDaemon(True)
        t.start()
        threads.append(t)
    
    while (True):
        time.sleep(1)

if __name__ == '__main__':
    main()
