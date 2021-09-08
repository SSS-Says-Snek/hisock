from __future__ import annotations

import socket  # Socket module, duh
import select  # Yes, we're using select for multiple clients
import json  # To send multiple data without 10 billion commands
import re  # Regex, to make sure arguments are passed correctly
import warnings
from typing import Callable

from utils import (
    receive_message, removeprefix, make_header,
    dict_tupkey_lookup, dict_tupkey_lookup_key
)
from functools import wraps


class HiSockServer:
    """
    The server class for HiSock
    HiSockServer offers a neater way to send and receive data than
    sockets. You don't need to worry about headers now, yay!

    Args:
      addr: tuple
        A two-element tuple, containing the IP address and the
        port number of where the server should be hosted.
        Due to the nature of reserved ports, it is recommended to host the
        server with a port number that's higher than 1023.
        Only IPv4 currently supported
      blocking: bool
        A boolean, set to whether the server should block the loop
        while waiting for message or not.
        Default passed in by `start_server` is True
      max_connections: int
        The number of maximum connections `HiSockServer` should accept, before
        refusing clients' connections. Pass in 0 for unlimited connections.
        Default passed in  by `start_server` is 0
      header_len: int
        An integer, defining the header length of every message.
        A smaller header length would mean a smaller maximum message
        length (about 10**header_len).
        Any client connecting MUST have the same header length as the server,
        or else it will crash.
        Default passed in by `start_server` is 16 (maximum length: 10 quadrillion bytes)
    """

    def __init__(
            self,
            addr: tuple[str, int],
            blocking: bool = True,
            max_connections: int = 0,
            header_len: int = 16
    ):
        # Binds address and header length to class attributes
        self.addr = addr
        self.header_len = header_len

        # Socket initialization
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(blocking)
        self.sock.bind(addr)
        self.sock.listen(max_connections)

        self.funcs = {}

        # Dictionaries and Lists for client lookup
        self._sockets_list = [self.sock]
        self.clients = {}
        self.clients_rev = {}

    def __str__(self):
        return f"<HiSockServer serving at {':'.join(map(str, self.addr))}>"

    class _on:
        """Decorator used to handle something when receiving command"""

        def __init__(self, outer, cmd_activation):
            self.outer = outer
            self.cmd_activation = cmd_activation

        def __call__(self, func: Callable):
            """Adds a function that gets called when the server receives a matching command"""

            # Inner function that's returned
            @wraps(func)
            def inner_func(*args, **kwargs):
                ret = func(*args, **kwargs)
                return ret

            self.outer.funcs[self.cmd_activation] = func
            return inner_func

    def on(self, command: str):
        """
        A decorator that adds a function that gets called when the server
        receives a matching command

        Args:
          command: str
            A string, representing the command the function should activate
            when receiving it

        Returns:
          The same function
          (The decorator just appended the function to a stack)
        """
        return self._on(self, command)

    def send_all_clients(self, command: str, content: bytes):
        """
        Sends the commmand and content to *ALL* clients connected
        
        Args:
          command: str
            A string, representing the command to send to every client
          content: bytes
            A bytes-like object, containing the message/content to send
            to each client
        """
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        for client in self.clients:
            client.send(
                content_header + command.encode() + b" " + content
            )

    def send_group(self, group: str, command: str, content: bytes):
        """
        Sends data to a specific group.
        Groups are recommended for more complicated servers or multipurpose
        servers, as it allows clients to be divided, which allows clients to
        be sent different data for different purposes.

        Args:
          group: str
            A string, representing the group to send data to
          command: str
            A string, containing the command to send
          content: bytes
            A bytes-like object, with the content/message
            to send

        Raises:
          TypeError, if the group does not exist
        """
        group_clients = dict_tupkey_lookup(
            group, self.clients_rev,
            idx_to_match=2
        )
        group_clients = list(group_clients)

        if len(group_clients) == 0:
            raise TypeError(f"Group {group} does not exist")
        else:
            content_header = make_header(command.encode() + b" " + content, self.header_len)
            for clt_to_send in group_clients:
                clt_to_send.send(
                    content_header + command.encode() + b" " + content
                )

    def send_client(self, client, command: str, content: bytes):
        """
        Sends data to a specific client.
        Different formats of the client is supported. It can be:
          - An IP + Port format, written as "ip:port"
          - A client name, if it exists

        Args:
          client: str, tuple
            The client to send data to. The format could be either by IP+Port,
            or a client name
          command: str
            A string, containing the command to send
          content: bytes
            A bytes-like object, with the content/message
            to send

        Raises:
          ValueError, if the client format is wrong
          TypeError, if client does not exist
          Warning, if using client name and more than one client with
            the same name is detected
        """
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        # r"((\b(0*(?:[1-9]([0-9]?){2}|255))\b\.){3}\b(0*(?:[1-9][0-9]?[0-9]?|255))\b):(\b(0*(?:[1-9]([0-9]?){4}|65355))\b)"

        if isinstance(client, tuple):
            if len(client) == 2 and isinstance(client[0], str):
                if re.search(r"(((\d?){3}\.){3}(\d?){3})", client[0]) and isinstance(client[1], int):
                    client = f"{client[0]}:{client[1]}"
                else:
                    raise ValueError(
                        f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                        f"{client}"
                    )
            else:
                raise ValueError(
                    f"Client tuple format should be ('ip.ip.ip.ip', port), not "
                    f"{client}"
                )

        if re.search(r"(((\d?){3}\.){3}(\d?){3}):(\d?){5}", client):
            # Matching: 523.152.135.231:92344   Invalid IP handled by Python
            # Try IP Address, should be unique
            split_client = client.split(':')
            reconstructed_client = []
            try:
                # split_client[0] = map(int, split_client[0].split('.'))
                reconstructed_client.append(map(int, split_client[0].split('.')))
            except ValueError:
                raise ValueError("IP is not numerical (only IPv4 currently supported)")
            try:
                # split_client[1] = int(split_client[1])
                reconstructed_client.append(int(split_client[1]))
            except ValueError:
                raise ValueError("Port is not numerical (only IPv4 currently supported)")

            for subip in reconstructed_client[0]:
                if not 0 <= subip < 255:
                    raise ValueError(f"{client} is not a valid IP address")
            if not 0 < reconstructed_client[1] < 65535:
                raise ValueError(f"{split_client[1]} is not a valid port (1-65535)")

            try:
                client_sock = next(
                    dict_tupkey_lookup(
                        (client.split(':')[0], reconstructed_client[1]), self.clients_rev,
                        idx_to_match=0
                    )
                )
            except StopIteration:
                raise TypeError(f"Client with IP {client} is not connected")

            client_sock.send(
                content_header + command.encode() + b" " + content
            )
        else:
            # Try name or group
            try:
                mod_clients_rev = {}
                for key, value in self.clients_rev.items():
                    mod_key = (key[0], key[1])  # Groups shouldn't count
                    mod_clients_rev[mod_key] = value

                client_sock = list(dict_tupkey_lookup(client, mod_clients_rev, idx_to_match=1))
            except StopIteration:
                raise TypeError(f"Client with name \"{client}\"does not exist")

            content_header = make_header(command.encode() + b" " + content, self.header_len)

            if len(client_sock) > 1:
                warnings.warn(
                    f"{len(client_sock)} clients with name \"{client}\" detected; sending data to "
                    f"Client with IP {':'.join(map(str, client_sock[0].getpeername()))}"
                )

            client_sock[0].send(
                content_header + command.encode() + b" " + content
            )

    def run(self):
        """
        Runs the server. This method handles the sending and receiving of data,
        so it should be run once every iteration of a while loop, as to not
        lose valuable information
        """
        read_sock, write_sock, exception_sock = select.select(self._sockets_list, [], self._sockets_list)

        for notified_sock in read_sock:
            if notified_sock == self.sock:  # Got new connection
                connection, address = self.sock.accept()
                client = receive_message(connection, self.header_len)

                client_hello = removeprefix(client['data'].decode(), "$CLTHELLO$ ")
                client_hello = json.loads(client_hello)

                self._sockets_list.append(connection)

                clt_info = {
                    "ip": address,
                    "name": client_hello['name'],
                    "group": client_hello['group']
                }

                self.clients[connection] = clt_info
                self.clients_rev[(
                    address,
                    client_hello['name'],
                    client_hello['group']
                )] = connection

                if 'join' in self.funcs:
                    # Reserved function - Join
                    self.funcs['join'](
                        clt_info
                    )
                clt_cnt_header = make_header(f"$CLTCONN$ {json.dumps(clt_info)}", self.header_len)
                clt_to_send = [clt for clt in self.clients if clt != connection]

                for sock_client in clt_to_send:
                    sock_client.send(
                        clt_cnt_header + f"$CLTCONN$ {json.dumps(clt_info)}".encode()
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

                    clt_dcnt_header = make_header(f"$CLTDISCONN$ {json.dumps(more_client_info)}", self.header_len)

                    for clt_to_send in self.clients:
                        clt_to_send.send(
                            clt_dcnt_header + f"$CLTDISCONN$ {json.dumps(more_client_info)}".encode()
                        )
                else:
                    for matching_cmd, func in self.funcs.items():
                        if message['data'].startswith(matching_cmd.encode()):
                            parse_content = message['data'][len(matching_cmd) + 1:]
                            func(parse_content)

                    if 'message' in self.funcs:
                        self.funcs['message'](self.clients[notified_sock], message['data'])

    def get_group(self, group: str):
        """
        Gets all clients from a specific group

        Args:
          group: str
            A string, representing the group to look up

        Returns:
          A list of dictionaries of clients in that group, containing
          the address, name, group, and socket

        Raises:
          TypeError, if the group does not exist
        """
        group_clients = list(dict_tupkey_lookup_key(
            group, self.clients_rev,
            idx_to_match=2
        ))
        mod_group_clients = []

        if len(group_clients) == 0:
            raise ValueError(f"Group {group} does not exist")

        for clt in group_clients:
            clt_conn = self.clients_rev[clt]
            mod_dict = {
                "ip": clt[0],
                "name": clt[1],
                "group": clt[2],
                "socket": clt_conn
            }
            mod_group_clients.append(mod_dict)

        return mod_group_clients

    def get_addr(self):
        return self.addr


def start_server(addr, blocking=True, max_connections=0, header_len=16):
    """
    Creates a `HiSockServer` instance. See `HiSockServer` for more details

    Returns:
      A `HiSockServer` instance
    """
    return HiSockServer(addr, blocking, max_connections, header_len)


if __name__ == "__main__":
    print("Starting server...")
    s = HiSockServer(('192.168.1.131', 33333))


    @s.on("join")
    def test_sussus(yum_data):
        print("Whomst join, ahh it is", yum_data['name'])
        s.send_all_clients("Joe", b"Bidome")
        s.send_client(f"{yum_data['ip'][0]}:{yum_data['ip'][1]}", "Bruh", b"E")
        s.send_client(yum_data['ip'], "e", b"E")

        s.send_group("Amogus", "Test", b'TTT')


    @s.on("leave")
    def bruh(yum_data):
        print("Hmmm whomst leaved, ah it is", yum_data['name'])


    @s.on("message")
    def why(client_data, message):
        print("Message reserved function aaa")
        print("Client data:", client_data)
        print("Message:", message)


    @s.on("Sussus")
    def a(msg):
        s.send_all_clients("pog", msg)


    while True:
        s.run()
