#encoding=utf8
import sys
sys.path.append("..")

import time
import threading
from fpnn import *

class MyProcessor(QuestProcessor):
    def pushmsg(self, connection, quest):
        print(connection)
        print(quest)
        return Answer()

if  __name__=="__main__":
    
    #client = TCPClient("52.82.27.68", 13321, True)
    client = TCPClient("52.83.245.22", 13697, True)

    #client.enable_encryptor_by_pem_file('test-public.pem')

    class MyConnectionCallback(ConnectionCallback):
        def connected(self, connection_id, endpoint):
            print("connected")
            print(connection_id)
            print(endpoint)

        def closed(self, connection_id, endpoint, caused_by_error):
            print("closed")
            print(connection_id)
            print(endpoint)
            print(caused_by_error)

    client.set_connection_callback(MyConnectionCallback())
    client.set_quest_timeout(5000)
    
    client.set_quest_processor(MyProcessor())

    quest = Quest("two")
    quest.param("pid", 11000001)
    quest.param("uid", 123456)
    quest.param("token", "4215BAC19C00D74C4652F21EC0064C97")

    class MyCallback(QuestCallback):
        def callback(self, answer):
            print("async:")
            print(answer)

    client.send_quest(quest, MyCallback())

    #answer = client.send_quest(quest)
    #print("sync:")
    #print(answer)

    time.sleep(10)

    client.destory()




