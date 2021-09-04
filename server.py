import socket
import select  # Yes, we're using select for multiple clients
import json  # To send multiple data without 10 billion commands
import re

from utils import (
    receive_message, removeprefix, make_header,
    dict_tupkey_lookup, dict_tupkey_lookup_key
)


class HiSockServer:
    class _on:
        """Decorator used to handle something when receiving command"""
        def __init__(self, outer, cmd_activation):
            self.outer = outer
            self.cmd_activation = cmd_activation

        def __call__(self, func):
            def inner_func(*args, **kwargs):
                ret = func(*args, **kwargs)
                return ret

            self.outer.funcs[self.cmd_activation] = func
            return inner_func

    def __init__(self, addr, max_connections=0, header_len=16):
        self.addr = addr
        self.header_len = header_len

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(True)
        self.sock.bind(addr)
        self.sock.listen(max_connections)

        self.funcs = {}

        self._sockets_list = [self.sock]
        self.clients = {}
        self.clients_rev = {}

    def on(self, something):
        return HiSockServer._on(self, something)

    def send_all_clients(self, command: str, content: bytes):
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        for client in self.clients:
            client.send(
                content_header + command.encode() + b" " + content
            )

    def send_client(self, client, command: str, content: bytes):
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        # r"((\b(0*(?:[1-9]([0-9]?){2}|255))\b\.){3}\b(0*(?:[1-9][0-9]?[0-9]?|255))\b):(\b(0*(?:[1-9]([0-9]?){4}|65355))\b)"

        if re.search(r"(((\d?){3}\.){3}(\d?){3}):(\d?){5}", client):
            # I don't care that the regex doesn't quite work, now shh
            # Try IP Address, should be unique
            split_client = client.split(':')
            try:
                split_client[0] = map(int, split_client[0].split('.'))
            except ValueError:
                raise ValueError("IP is not numerical (only IPv4 currently supported)")
            try:
                split_client[1] = int(split_client[1])
            except ValueError:
                raise ValueError("Port is not numerical (only IPv4 currently supported)")

            for subip in split_client[0]:
                if not 0 <= subip < 255:
                    raise ValueError(f"{client} is not a valid IP address")
            if not 0 < split_client[1] < 65535:
                raise ValueError(f"{split_client[1]} is not a valid port (1-65535)")

            client = dict_tupkey_lookup((client.split(':')[0], split_client[1]), self.clients_rev)

            client.send(
                content_header + command.encode() + b" " + content
            )
        else:
            # Try name
            pass

    def run(self):
        read_sock, write_sock, exception_sock = select.select(self._sockets_list, [], self._sockets_list)

        for notified_sock in read_sock:
            if notified_sock == self.sock:  # Got new connection
                connection, address = self.sock.accept()
                client = receive_message(connection, self.header_len)

                client_hello = removeprefix(client['data'].decode(), "$CLTHELLO$ ")
                client_hello = json.loads(client_hello)

                self._sockets_list.append(connection)
                self.clients[connection] = {
                    "ip": address,
                    "name": client_hello['name'],
                    "group": client_hello['group']
                }
                self.clients_rev[(
                    address,
                    client_hello['name'],
                    client_hello['group']
                )] = connection

                if 'join' in self.funcs:
                    # Reserved function - Join
                    self.funcs['join'](
                        {
                            "ip": address,
                            "name": client_hello['name'],
                            "group": client_hello['group']
                        }
                    )
            else:
                # "header" - The header of the msg, mostly not needed
                # "data" - The actual data/content of the msg
                message = receive_message(notified_sock, self.header_len)

                if not message:
                    # Most likely client disconnect
                    client_disconnect = self.clients[notified_sock]['ip']
                    more_client_info = self.clients[notified_sock]

                    self._sockets_list.remove(notified_sock)
                    del self.clients[notified_sock]
                    del self.clients_rev[
                        next(
                            dict_tupkey_lookup_key(client_disconnect, self.clients_rev)
                        )
                    ]

                    if 'leave' in self.funcs:
                        # Reserved function - Leave
                        self.funcs['leave'](
                            {
                                "ip": client_disconnect,
                                "name": more_client_info['name'],
                                "group": more_client_info['group']
                            }
                        )
                else:
                    for matching_cmd, func in self.funcs.items():
                        if message['data'].startswith(matching_cmd.encode()):
                            parse_content = message['data'][len(matching_cmd) + 1:]
                            func(parse_content)

                    if 'message' in self.funcs:
                        self.funcs['message'](message['data'])


def start_server(addr, max_connections=0, header_len=16):
    return HiSockServer(addr, max_connections, header_len)


if __name__ == "__main__":
    print("Starting server...")
    s = HiSockServer(('192.168.1.131', 33333))

    @s.on("join")
    def test_sussus(yum_data):
        print("Whomst join, ahh it is", yum_data['name'])
        print(yum_data)
        s.send_all_clients("Joe", b"Bidome")
        s.send_client(f"{yum_data['ip'][0]}:{yum_data['ip'][1]}", "Bruh", b"E")

    @s.on("leave")
    def bruh(yum_data):
        print("Hmmm whomst leaved, ah it is", yum_data['name'])

    @s.on("Sussus")
    def a(msg):
        s.send_all_clients("pog", msg)

    while True:
        s.run()
