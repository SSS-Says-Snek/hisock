"""HiSock TicTacToe client and server shared code"""


### Setup ###
import hisock
import traceback
from typing import Union

### Functions ###
def get_username() -> str:
    """Asks the user for a username and returns it"""

    while True:
        username: str = input("Enter a username: ")

        if username == "":
            print("The username cannot be blank")
            continue

        if len(username) > 16:
            print("The username must be 16 characters or less")
            continue

        if not username.strip("_").isalnum():
            print(
                "The username must be made up of only alpha numeric characters and underscores"
            )
            continue

        break

    return username


def get_ip_addr_port() -> tuple[str, int]:
    """Asks the user for an IP address and port and returns it (ip, port)"""

    # IP address
    while True:
        ip_addr: str = input("Enter an IP address: ")

        if ip_addr == "":
            print("The IP address cannot be blank")
            continue
        if not ip_addr.count(".") == 3:
            print("The IP address must be in the form of a dotted quad")
            continue

        break

    # Port
    while True:
        port: str = input("Enter a port: ")

        if not port.isnumeric():
            print("The port must be a number")
            continue

        # The port is numerical, convert it now
        port = int(port)

        if port < 1 or port > 65535:
            print("The port must be between 1 and 65535")
            continue

        break

    return ip_addr, port


def log_error(error: Exception):
    """Logs an error to the console"""

    print(
        "AN ERROR HAS OCCURRED!!!\n"
        f"Error message: {error!s}\n"
        f"Traceback:\n{traceback.format_exc()}\n"
        "-Sheepy's Amazing Error Message Services"
    )


def connect_to_server(
    ip_address: Union[str, None] = None,
    name: Union[str, None] = None,
    threaded: bool = False,
) -> Union[hisock.client.HiSockClient, hisock.client.ThreadedHiSockClient]:
    if ip_address is None:
        ip_address = get_ip_addr_port()

    if name is None:
        name = get_username()

    try:
        return (
            hisock.client.connect(ip_address, name=name)
            if not threaded
            else hisock.client.threaded_connect(ip_address, name=name)
        )
    except Exception as error:
        log_error(error)
        raise error
