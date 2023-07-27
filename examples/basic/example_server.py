"""
Basic example of the structure of `hisock`. This is the server script.
Not an advanced example, but gets the main advantages of hisock across
"""

# Builtin modules
import sys
import time
import random

from hisock import ClientInfo, start_server, get_local_ip


def run():
    ADDR = get_local_ip()
    PORT = 6969

    if len(sys.argv) == 2:
        ADDR = sys.argv[1]
    if len(sys.argv) == 3:
        PORT = int(sys.argv[2])

    print(f"Serving at {ADDR}")
    server = start_server((ADDR, PORT))

    @server.on("join")
    def client_join(client: ClientInfo):
        print(f"Cool, {client.ipstr} joined!")
        if client.name is not None:
            print(f'    - With a sick name "{client.name}", very cool!')
        if client.group is not None:
            print(f'    - In a sick group "{client.group}", cool!')

        print("I'm gonna send them a quick hello message")

        server.send_client(
            client, "hello_message", str(time.time()).encode()
        )

    @server.on("processing1")
    def process(client: ClientInfo, process_request: str):
        print(
            f"\nAlright, looks like {client.ipstr} received the hello message, "
            "\nas now they're trying to compute something on the server, because they have "
            "potato computers"
        )
        print("Their processing request is:", process_request)

        for _ in range(process_request.count("randnum")):
            randnum = str(random.randint(1, 100000000))
            process_request = process_request.replace("randnum", randnum, 1)

        result = eval(process_request)  # Insecure, but I'm lazy, so...
        print(f"Cool! The result is {result}! I'mma send it to the client")

        server.send_client(client, "something", str(result))

    server.start()


if __name__ == "__main__":
    run()
