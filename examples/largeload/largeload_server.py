from __future__ import annotations
import time

import hisock

print(hisock.__file__)

server = hisock.HiSockServer(("192.168.1.126", 8888))


@server.on("join")
def on_join(_):
    pass


@server.on("large_load")
def on_large_load(client: hisock.ClientInfo, data: list):
    print(len(data[1]), f"recv from {client.ip} at t={time.time()}")
    for server_client in server.get_all_clients():
        if client.ip != server_client.ip:
            server.send_client(client, "large_load", data)


server.start()
