import re
import socket
import json
import errno
import sys
import traceback

from functools import wraps
from utils import make_header, removeprefix


class HiSockClient:
    def __init__(self, addr, name, group, blocking=True, header_len=16):
        """
        The client class for HiSock.
        HiSockClient offers a higher-level version of sockets. No need to worry about headers now, yay!
        """
        self.funcs = {}

        self.addr = addr
        self.name = name
        self.group = group
        self.header_len = header_len

        self._closed = False

        self.reserved_functions = ['client_connect']

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(self.addr)
        self.sock.setblocking(blocking)

        hello_dict = {"name": self.name, "group": self.group}
        conn_header = make_header(f"$CLTHELLO$ {hello_dict}", self.header_len)

        self.sock.send(
            conn_header + f"$CLTHELLO$ {json.dumps(hello_dict)}".encode()
        )

    def update(self):
        if not self._closed:
            try:
                while True:
                    content_header = self.sock.recv(self.header_len)

                    if not content_header:
                        print("[SERVER] Connection forcibly closed by server, exiting...")
                        raise SystemExit
                    content = self.sock.recv(int(content_header.decode()))

                    if content.startswith(b"$CLTCONN$") and 'client_connect' in self.funcs:
                        clt_content = json.loads(
                            removeprefix(content, b"$CLTCONN$ ")
                        )
                        self.funcs['client_connect'](clt_content)

                    for matching_cmd, func in self.funcs.items():
                        if content.startswith(matching_cmd.encode()) and \
                                matching_cmd not in self.reserved_functions:
                            parse_content = content[len(matching_cmd) + 1:]
                            func(parse_content)
            except IOError as e:
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK and not self._closed:
                    # Fatal Error, abort client (print exception, print log, exit python)
                    traceback.print_exception(
                        type(e), e, e.__traceback__, file=sys.stderr
                    )
                    print("\nServer Error encountered, aborting client...", file=sys.stderr)
                    self.close()

                    raise SystemExit

    class _on:
        """Decorator used to handle something when receiving command"""
        def __init__(self, outer, command):
            self.outer = outer
            self.command = command

        def __call__(self, func):
            def inner_func(*args, **kwargs):
                """Adds a function that gets called when the client receives a matching command"""
                ret = func(*args, **kwargs)
                return ret

            if re.search(r"\$.+\$", self.command):
                raise ValueError(
                    "The format \"$command$\" is used for reserved functions - "
                    "Consider using a different format"
                )
            self.outer.funcs[self.command] = func
            return inner_func

    def on(self, something):
        """Adds a function that gets called when the client receives a matching command"""
        return HiSockClient._on(self, something)

    def send(self, command: str, content: bytes):
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        self.sock.send(
            content_header + command.encode() + b" " + content
        )

    def raw_send(self, content: bytes):
        """
        Sends a message to the server: NO COMMAND REQUIRED.
        This is preferable in some situations, where clients need to send
        multiple data over the server, without overcomplicating it with commands

        Args:
          content:
            A bytes-like object, with the content/message
            to send

        Returns:
          Nothing
        """
        header = make_header(content, self.header_len)
        self.sock.send(
            header + content
        )

    def wait_recv(self):
        """
        Waits (blocks) until a message is sent, and returns that message

        Returns:
          A bytes-like object, containing the content/message
          the client first receives
        """
        msg_len = int(self.sock.recv(self.header_len).decode())
        message = self.sock.recv(msg_len)
        return message

    def close(self):
        """Closes the client; running `client.update()` won't do anything now"""
        self._closed = True
        self.sock.close()


def connect(addr, name=None, group=None):
    return HiSockClient(addr, name, group)


if __name__ == "__main__":
    s = connect(('192.168.1.131', 33333), name="Sussus", group="Amogus")

    @s.on("Joe")
    def hehe(msg):
        print("Wowie", msg)
        yes = s.wait_recv()
        print(yes)
        s.send("Sussus", b"Some random msg I guess")

    @s.on("pog")
    def eee(msg):
        print("Pog juice:", msg)
        # s.close()

    @s.on("client_connect")
    def please(data):
        print("YESSSSSSSSSSS")
        print(data)

    @s.on("$CLTCONN$")
    def hehehe(msg):
        print("This will not be able to")

    while True:
        s.update()
