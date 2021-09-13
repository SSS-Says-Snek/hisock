![CircleCI Badge](https://img.shields.io/circleci/build/github/SSS-Says-Snek/hisock)

# highsock
A higher-level extension of the socket module, with simpler and more efficient usages

## Documentation
Documentation's currently unavailable, though a crude form of it is available 
by examining the docstrings of desired functions. There will also soon be 
functioning examples, to show the main features of hisock

## Examples
hisock utilizes decorators as the core of receiving messages. 
Examples are located in the `examples` directory. Here is what a basic 
server script would look like using hisock:

#### Server
```python
import sys
import time
import random

from hisock import start_server, get_local_ip, iptup_to_str

ADDR = get_local_ip()
PORT = 6969

if len(sys.argv) == 2:
    ADDR = sys.argv[1]
if len(sys.argv) == 3:
    PORT = int(sys.argv[2])

print(f"Serving at {ADDR}")
server = start_server((ADDR, PORT))

@server.on("join")
def client_join(client_data):
    print(f"Cool, {':'.join(map(str, client_data['ip']))} joined!")
    if client_data['name'] is not None:
        print(f"    - With a sick name \"{client_data['name']}\", very cool!")
    if client_data['group'] is not None:
        print(f"    - In a sick group \"{client_data['group']}\", cool!")

    print("I'm gonna send them a quick hello message")

    server.send_client(client_data['ip'], "hello_message", str(time.time()).encode())

@server.on("processing1")
def process(client, process_request: str):
    print(f"\nAlright, looks like {iptup_to_str(client['ip'])} received the hello message, "
          "\nas now they're trying to compute something on the server, because they have "
          "potato computers")
    print("Their processing request is:", process_request)

    for _ in range(process_request.count("randnum")):
        randnum = str(random.randint(1, 100000000))
        process_request = process_request.replace("randnum", randnum, 1)

    result = eval(process_request)  # Insecure, but I'm lazy, so...
    print(f"Cool! The result is {result}! I'mma send it to the client")

    server.send_client_raw(client['ip'], str(result).encode())


while True:
    server.run()
```

#### Client
```python
import time

from hisock import connect, get_local_ip

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

```
###### Readme to be added of course lel
