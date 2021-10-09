"""
Basic example of the structure of `hisock`. This is the client script.
Not an advanced example, but gets the main advantages of hisock across
"""

# Builtin module
import time

from hisock import connect, get_local_ip


def run():
    # Parse `input` results
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

    join_time = time.time()

    # Establishes connection to the server
    s = connect(
        (server_to_connect, port),
        name=name, group=group
    )

    @s.on("hello_message")
    def handle_hello(msg):
        print("Thanks, server, for sending a hello, just for me!")
        print(f"Looks like, the message was sent on timestamp {msg.decode()}, "
              f"which is just {round(float(msg.decode()) - join_time, 6) * 1000} milliseconds since the connection!")
        print("In response, I'm going to send the server a request to do some processing")

        s.send("processing1", b"randnum**2")
        result = int(s.recv_raw())

        print(f"WHOAAA! The result is {result}! Thanks server!")

    while True:
        s.update()


if __name__ == "__main__":
    run()
