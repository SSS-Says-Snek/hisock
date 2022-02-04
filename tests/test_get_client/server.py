# Dummy server

from hisock import start_server
from hisock.utils import _input_port

server = start_server(("127.0.0.1", _input_port("Port: ")))

while True:
    server.run()
