import hisock
import _shared as shared

addr, name, _ = hisock.input_client_config(group_prompt=None)

client = hisock.HiSockClient(addr, name)

@client.on("start")
def on_start(data):
    print(data)

@client.on("disconn")
def on_disconn(reason: str):
    print(reason)

client.start()