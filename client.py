import socket
import json
import errno
import sys
import traceback

from utils import make_header, removeprefix


class HiSockClient:
    def __init__(self, addr, name, group, blocking=True, header_len=16):
        self.funcs = {}

        self.addr = addr
        self.name = name
        self.group = group
        self.header_len = header_len

        self._closed = False

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

                    for matching_cmd, func in self.funcs.items():
                        if content.startswith(matching_cmd.encode()):
                            parse_content = content[len(matching_cmd) + 1:]
                            func(parse_content)
            except IOError as e:
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK and not self._closed:
                    print(f"Reading Error: {str(e)}", file=sys.stderr)
                    b = traceback.print_exception(type(e), e, e.__traceback__)

    class _on:
        """Decorator used to handle something when receiving command"""
        def __init__(self, outer, something):
            self.outer = outer
            self.something = something

        def __call__(self, func):
            def inner_func(*args, **kwargs):
                ret = func(*args, **kwargs)
                return ret

            self.outer.funcs[self.something] = func
            return inner_func

    def on(self, something):
        return HiSockClient._on(self, something)

    def send(self, command: str, content: bytes):
        content_header = make_header(command.encode() + b" " + content, self.header_len)
        self.sock.send(
            content_header + command.encode() + b" " + content
        )

    def close(self):
        self._closed = True
        self.sock.close()


def connect(addr, name=None, group=None):
    return HiSockClient(addr, name, group)


if __name__ == "__main__":
    s = connect(('192.168.1.131', 33333), name="Sussus", group="Amogus")

    @s.on("Joe")
    def hehe(msg):
        print("Wowie", msg)
        s.send("Sussus", b"Some random msg I guess")

    @s.on("pog")
    def eee(msg):
        print("Pog juice:", msg)
        s.close()

    while True:
        s.update()
