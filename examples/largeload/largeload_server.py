import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join("..", "..")))
import hisock

print(hisock.__file__)

server = hisock.HiSockServer(("192.168.1.126", 8888))

@server.on("join")
def on_join(_): pass

@server.on("large_load")
def on_large_load(client_data, data: list):
    print(len(data), f"recv from {client_data.ip} at t={time.time()}")
    for client in server.get_all_clients():
        if client["ip"] != client_data.ip:
            server.send_client(client["ip"], "large_load", data)


server.start()