"""
Basic example of the structure of `hisock`. This is the server script.
Not an advanced example, but gets the main advantages of hisock across
"""

# Builtin modules
import sys
import time
import random

from hisock import start_server, get_local_ip, iptup_to_str


def run():
    ADDR = get_local_ip()
    PORT = 6969

    if len(sys.argv) == 2:
        ADDR = sys.argv[1]
    if len(sys.argv) == 3:
        PORT = int(sys.argv[2])

    print(f"Serving at {ADDR}")
    server = start_server((ADDR, PORT))  # Starts the server

    # `join` is a reserved function - It will activate
    # whenever a new client joins
    @server.on("join")
    def client_join(client_data):
        # The `join` reserved function returns one argument;
        # The client data, with IP, name, and group
        # (Names and Groups are just an easy way to identify clients without IP)
        print(f"Cool, {':'.join(map(str, client_data['ip']))} joined!")
        if client_data['name'] is not None:
            print(f"    - With a sick name \"{client_data['name']}\", very cool!")
        if client_data['group'] is not None:
            print(f"    - In a sick group \"{client_data['group']}\", cool!")

        print("I'm gonna send them a quick hello message")

        # The current way to send; it takes in a tuple of IP,
        # The command to send (essentially what to label the message as),
        # And the content (Content must be in bytes for now, str support may be added)
        server.send_client(client_data['ip'], "hello_message", str(time.time()).encode())

    # Client SHOULD send a command `processing1`, soon after the server message
    # This will activate whenever a client sends a `processing1` command
    @server.on("processing1")
    def process(client, process_request: str):
        # Nonreserved functions take two arguments; the client data,
        # And the actual content
        # In HiSock, you are able to type cast the initially `bytes` content
        # Into another supported type, like str, int, or float

        # `iptup_to_str` converts a tuple IP into a string IP ('1.1.1.1', 4) -> 1.1.1.1:4
        print(f"\nAlright, looks like {iptup_to_str(client['ip'])} received the hello message, "
              "\nas now they're trying to compute something on the server, because they have "
              "potato computers")
        print("Their processing request is:", process_request)

        for _ in range(process_request.count("randnum")):
            randnum = str(random.randint(1, 100000000))
            process_request = process_request.replace("randnum", randnum, 1)

        result = eval(process_request)  # Insecure, but I'm lazy, so...
        print(f"Cool! The result is {result}! I'mma send it to the client")

        # Whenever you want to send multiple content rounds without
        # creating 500 commands, use `send_client_raw`. Along with
        # `recv_raw`, it can be used to send multiple content rounds.
        # Here, we are sending the result back to the client
        server.send_client_raw(client['ip'], str(result).encode())

    while True:
        server.run()


if __name__ == "__main__":
    run()
