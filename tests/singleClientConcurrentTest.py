#encoding=utf8
import sys
sys.path.append("..")
import threading
import time

from fpnn import *

class MyConnectionCallback(ConnectionCallback):
        def connected(self, connection_id, endpoint):
            print("+", end="", flush=True)

        def closed(self, connection_id, endpoint, caused_by_error):
            if caused_by_error:
                print("#", end="", flush=True)
            else:
                print("~", end="", flush=True)

class MyCallback(QuestCallback):
    def callback(self, answer):
        if answer.is_error():
            if answer.error_code == FPNN_ERROR.FPNN_EC_CONNECTION_IS_CLOSE.value:
                print(";", end="", flush=True)
            else:
                print("@", end="", flush=True)
        else:
            print("$", end="", flush=True)

class Tester(object):
    def __init__(self, ip, port):
        self.client = TCPClient(ip, port)
        self.client.set_connection_callback(MyConnectionCallback())

    def ShowSignDesc(self):
        print("Sign:")
        print("    +: establish connection")
        print("    -: connect failed")
        print("    ~: close connection")
        print("    #: connection error")

        print("    *: send sync quest")
        print("    &: send async quest")

        print("    ^: sync answer Ok")
        print("    ?: sync answer exception")
        print("    |: sync answer exception by connection closed")
        #print("    (: sync operation fpnn exception")
        #print("    ): sync operation unknown exception")

        print("    $: async answer Ok")
        print("    @: async answer exception")
        print("    ;: async answer exception by connection closed")
        #print("    {: async operation fpnn exception")
        #print("    }: async operation unknown exception")

        print("    !: close operation")
        #print("    [: close operation fpnn exception")
        #print("    ]: close operation unknown exception")

    def GenQuest(self):
        quest = Quest("two way demo")
        quest.param("quest", "one")
        quest.param("int", 2)
        quest.param("double", 3.3)
        quest.param("boolean", True)
        quest.param("ARRAY", ["first_vec", 4])
        quest.param("MAP", {"map1":"first_map", "map2":True, "map3":5, "map4":5.7, "map5":"中文"});
        return quest

    def TestWorker(self):
        act = 0
        for i in range(self.questCount):
            index = (int(round(time.time() * 1000)) + i) % 64

            if i >= 10:
                if index < 6:
                    act = 2    #-- close operation
                elif index < 32:
                    act = 1    #-- async quest
                else:
                    act = 0    #-- sync quest
            else:
                act = int(index & 0x1)

            if act == 0:
                print("*", end="", flush=True)
                answer = self.client.send_quest(self.GenQuest())
                if answer.is_error():
                    if answer.error_code == FPNN_ERROR.FPNN_EC_CONNECTION_IS_CLOSE.value:
                        print("|", end="", flush=True)
                    else:
                        print("?", end="", flush=True)
                else:
                    print("^", end="", flush=True)
            elif act == 1:
                print("&", end="", flush=True)
                self.client.send_quest(self.GenQuest(), MyCallback())
            else:
                print("!", end="", flush=True)
                self.client.close()

    def Test(self, threadCount, perThreadQuestCount):
        self.questCount = perThreadQuestCount
        print("========[ Test: thread {0}, per thread quest: {1} ]==========".format(threadCount, perThreadQuestCount))

        threads = []
        for index in range(threadCount):
            thread = threading.Thread(target=Tester.TestWorker, args=(self,))
            thread.start()
            threads.append(thread)

        time.sleep(5)

        for thread in threads:
            thread.join()
        print("")

if  __name__=="__main__":
    if len(sys.argv) != 3:
        print("Usage: singleClientConcurrentTest.py <ip> <port>")
        exit(0)

    tester = Tester(sys.argv[1], int(sys.argv[2]))
    tester.ShowSignDesc()

    tester.Test(10, 30000)
    tester.Test(20, 30000)
    tester.Test(30, 30000)
    tester.Test(50, 30000)
    tester.Test(60, 30000)


