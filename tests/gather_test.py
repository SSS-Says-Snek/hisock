from __future__ import annotations

from hisock import ClientInfo, ThreadedHiSockClient, ThreadedHiSockServer

server = ThreadedHiSockServer(("localhost", 6969))
client = ThreadedHiSockClient(("localhost", 6969))

info = {}


def finish():
    server.close()
    client.close()


########################
#        SERVER        #
########################


@server.on("join")
def join(client: ClientInfo):
    server.send_client(client, "sus", b"AMOGUS")


########################
#        CLIENT        #
########################


@client.on("sus")
def recv(data: bytes):
    info["serv_to_clt"] = data
    # client.send("client2server", b"")

    finish()


server.start()
client.start()


def test_serv_to_clt():
    assert info["serv_to_clt"] == b"AMOGUS"
