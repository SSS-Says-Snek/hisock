"""
Basic example of the structure of `hisock`. This is the client script.
Not an advanced example, but gets the main advantages of hisock across
"""

# Builtin module
import time

from hisock import connect, get_local_ip


def run():
    server_to_connect = input("Enter server IP to connect to (Press enter for default of your local IP): ")
    port = input("Enter Server port number (Press enter for default of 6969): ")

    if server_to_connect == '':
        server_to_connect = get_local_ip()

    if port == '':
        port = 6969
    else:
        port = int(port)

    name = input("Name? (Press enter for no name) ")
    group = input("Group? (Press enter for no group) ")

    print("======================================= ESTABLISHING CONNECTION =======================================")

    if name == '':
        name = None
    if group == '':
        group = None

    client = connect(
        (server_to_connect, port),
        name=name, group=group
    )
    join_time = time.time()

    @client.on("hello_message")
    def handle_hello(msg: str):
        print("Thanks, server, for sending a hello, just for me!")
        print(f"Looks like, the message was sent on timestamp {msg}, "
              f"which is just {round(float(msg) - join_time, 6) * 1000} milliseconds since the connection!")
        print("In response, I'm going to send the server a request to do some processing")

        client.send("processing1", b"randnum**2")
        result = client.recv("something", int)

        print(f"WHOAAA! The result is {result}! Thanks server!")

    client.start()


if __name__ == "__main__":
    run()
