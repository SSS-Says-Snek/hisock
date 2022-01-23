import hisock
import _shared

addr, port = hisock.input_server_config()

server = hisock.HiSockServer((addr, port))

server.start()

print("SUSSSS")