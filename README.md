## FPNN PYTHON SDK



## Requirements

* Python 3+
* selectors
* msgpack
* cryptography



## Use

```python
import sys
sys.path.append("/path/to/fpnn")
from fpnn import *
```



## Usage

### Create FPNN TCP Client

```python
client = TCPClient(host, port, auto_reconnect = True)
```

* **auto_reconnect** means establishing the connection in implicit or explicit. NOT keep the connection.



### Connect and Close and Reconnect

```python
client.connect()
client.close()
client.reconnect()
```



### Safe destruction TcpClient

```python
client.destory()
```



### Configure (Optional)

#### set_quest_timeout

```python
client.set_quest_timeout(microseconds)
```

* timeout in **microseconds**, this api can set the global quest timeout, you can also set a timeout for each request individually



#### set_connection_callback

```python
client.set_connection_callback(callback)
```

* the callback is a sub-class of ConnectionCallback, you can use it like this:

```python
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
```



#### enable_encryptor_by_pem_file

```python
client.enable_encryptor_by_pem_file(pem_pub_file, curve_name, strength)
```

* RTM Server-End Python SDK using **ECC**/**ECDH** to exchange the secret key, and using **AES-128** or **AES-256** in **CFB** mode to encrypt the whole session in **stream** way.



#### set_quest_processor

```python
client.set_quest_processor(processor)
```

* set the server quest processor to get the Duplex Push from the FPNN-Server, you can see the detailed usage below



### Send Quest simple demo

```python
# create Quest
quest = Quest("method_name")
quest.param("p1", 12345)
quest.param("p2", "abc")
quest.param("p3", 0.25)
quest.param("p4", True)

# send quest in async:
# define async quest callback:
class MyQuestCallback(QuestCallback):
    def callback(self, answer):
        if answer.is_error():
            print(answer.error_code)
            print(answer.error_message)
        else:
            try:
                k1 = answer.want("k1)
            except:
                pass
            k2 = answer.get("k2", None)

# send async quest:
client.send_quest(quest, MyQuestCallback())

# send quest in sync:
answer = client.send_quest(quest)
if answer.is_error():
    print(answer.error_code)
    print(answer.error_message)
else:
    try:
        k1 = answer.want("k1)
    except:
        pass
    k2 = answer.get("k2", None)
```



### send_quest

```python
def send_quest(self, quest, callback = None, timeout = 0)
```

#### params:

* quest: **(Required | instance of Quest )**  the quest
* callback: **(Optional | a sub-class of QuestCallback )**  used in async implementation
* timeout: **(Optional | int )** timeout in **microseconds**, if not set, a global timeout will be used



### Quest

```python
def __init__(self, method, oneway = False, params = None)
  
# you can init Quest and set param like this:
quest = Quest('method_name')
quest.param('key', 'value')

# or init param when init:
quest = Quest('method_name', params = {'key':'value'})
```



### Answer

```python
def __init__(self, params = None)

# you can init Answer and set param like this:
answer = Answer()
answer.param('key', 'value')

# or init param when init:
answer = Answer(params = {'key':'value'})

# you can get the param from an answer return by a send_quest:
try:
    k1 = answer.want("k1)
except:
    pass
k2 = answer.get("k2", None)
```



#### answer.want()

```python
def want(self, key)
```

#### params:

* key: **(Required | Str )**  answer key

#### return:

* the value 

#### exception:

* Exception('get param error')



#### answer.get()

```python
def get(self, key, default)
```

#### params:

* key: **(Required | Str )**  answer key
* default: **(Required )**  default value if not exist the key

#### return:

* the value 



#### answer.is_error()

```python
if answer.is_error():
    print(answer.error_code)
    print(answer.error_message)
```



### Set Duplex Server Push Processor

```python
class MyQuestProcessor(QuestProcessor):
    def method_name(self, connection, quest):
        try:
            k1 = quest.want("k1")
        except:
            pass

        k2 = quest.get("k2", None)
        return Answer()

client.set_quest_processor(MyQuestProcessor())
```

#### Advance or Async Answer

```python
class MyQuestProcessor(QuestProcessor):
    def method_name(self, connection, quest):
        connection.send_answer(Answer())
        # ...
        return None
```

