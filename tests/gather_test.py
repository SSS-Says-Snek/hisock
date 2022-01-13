import hisock
import test_realtime

server = hisock.server.ThreadedHiSockServer(("localhost", 6969))
client = hisock.client.ThreadedHiSockClient(("localhost", 6969), None, None)

vals_to_test = {}


def finish():
    server.stop_server()
    client.stop_client()

    test_realtime.info = vals_to_test  # Monke patch


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
def recv(info: str):
    vals_to_test["serv_to_clt"] = info
    client.send("client2server", b"")

    finish()

server.start_server()
client.start_client()
