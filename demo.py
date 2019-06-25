# coding: utf-8

import time
import Fpnn

def main():
 
    class MyConnectedCallback(Fpnn.FpnnConnectedCallback):
        def callback(self):
            print("Connected")

    class MyConnectionWillCloseCallback(Fpnn.FpnnConnectionWillCloseCallback):
        def callback(self, causedByError):
            print("close: " + str(causedByError))

    class MyQuestCallback(Fpnn.FpnnCallback):
        def callback(self, answer, exception):
            if exception == None:
                print "answer: "
                print answer
            else:
                print "exception: " 
                print repr(exception)
   
    client = Fpnn.TCPClient('localhost', 13697)
    
    client.setConnectionConnectedCallback(MyConnectedCallback())
    client.setConnectionWillCloseCallback(MyConnectionWillCloseCallback())

    client.sendQuest('test', {'aaa': 'bbb'}, MyQuestCallback())
    client.sendQuest('test', {'aaa': 'bbb'}, MyQuestCallback())
    client.sendQuest('test', {'aaa': 'bbb'}, MyQuestCallback())

    try:
        answer = client.sendQuestSync('test', {'aaa': 'bbb', 'sync': 123})
        print 'sync answer:'
        print answer
    except Exception,e:
        print 'sync exception:'
        print e.message

    time.sleep(1)
    client.close()

if __name__ == '__main__':
    main()
