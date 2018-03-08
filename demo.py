# coding: utf-8

import time

import Fpnn

class MyCallback(Fpnn.FpnnCallback):
    def __init__(self, client):
        self.client = client

    def callback(self, answer, exception):
        if exception == None:
            print "answer: "
            print answer
        else:
            print "exception: " 
            print repr(exception)

class MyConnectedCallback(Fpnn.FpnnConnectedCallback):
    def callback(self):
        print("Connected")

class MyConnectionWillCloseCallback(Fpnn.FpnnConnectionWillCloseCallback):
    def callback(self, causedByError):
        print("close: " + str(causedByError))

def main():
    client = Fpnn.TCPClient('localhost', 13199)

    # f = open('server-public.pem')
    # peerPubData = f.read()
    # f.close()
    
    # client.enableEncryptor(peerPubData)


    client.setConnectionConnectedCallback(MyConnectedCallback())
    client.setConnectionWillCloseCallback(MyConnectionWillCloseCallback())

    client.sendQuest('two way demo', {'aaa': 'bbb'}, MyCallback(client))

    try:
        answer = client.sendQuestSync('two way demo', {'aaa': 'bbb'})
        print 'sync answer:'
        print answer
    except Exception,e:
        print 'sync exception:'
        print e.message

    time.sleep(1)
    client.close()

if __name__ == '__main__':
    main()
