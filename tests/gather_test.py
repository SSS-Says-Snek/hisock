import hisock

server = hisock.server.ThreadedHiSockServer(("localhost", 6969))
client = hisock.client.ThreadedHiSockClient(("localhost", 6969), None, None)

info = {}


def finish():
    server.stop_server()
    client.stop_client()


########################
#        SERVER        #
########################


@server.on("join")
def join(clt_data: dict):
    server.send_client(clt_data["ip"], "sus", b"AMOGUS")


########################
#        CLIENT        #
########################


@client.on("sus")
def recv(data: str):
    info["serv_to_clt"] = data
    client.send("client2server", b"")

    finish()

server.start_server()
client.start_client()

server.join()
client.join()

def test_serv_to_clt():
    assert info["serv_to_clt"] == "AMOGUS"
