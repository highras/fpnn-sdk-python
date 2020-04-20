## FPNN PYTHON SDK Simple Demo


### 1. Send Quest

```
import sys
sys.path.append("path/to/fpnn")
from fpnn import *

# create TCPClient
client = TCPClient("52.83.245.22", 13697, True)

# set quest timeout, default is 0 (unlimited)
client.set_quest_timeout(5000)

# create Quest
quest = Quest("method_name")
quest.param("k1", 123)
quest.param("k2", "abc")
quest.param("k3", 0.32)

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

### 2. Set Connection Callback 

```
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

### 3. Set Duplex Server Push Processor

```
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

### 4. Enable Connection Encryptor

```
client.enable_encryptor_by_pem_file('./test-public.pem')
```
