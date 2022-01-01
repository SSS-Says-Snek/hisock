from hisock import connect
from hisock.utils import _input_port, iptup_to_str

client = connect(("127.0.0.1", _input_port("Port: ")), input("Name: "))


@client.on("client_connect")
def on_client_connect(client_data: dict):
    if client_data["name"] == client.name:
        return

    client_data["ip"] = iptup_to_str(client_data["ip"])

    # Get the client
    for client_identifier in (client_data["ip"], client_data["name"]):
        other_client = client.get_client(client_identifier)
        print(f"{client_identifier=} {other_client=}")


while True:
    client.update()
