import hisock
import _shared as shared
import random


class ServerData:
    def __init__(self):
        self.client_pairs: list[list] = []

    def add_client(self, clt_data):
        if not self.client_pairs:
            self.client_pairs.append([clt_data, shared.Board()])
            return

        # Last element in list is always the most recently updated
        last = self.client_pairs[-1]
        if len(last) == 2:
            # Only one client is connected in this pair
            last.insert(1, clt_data)

            # List now: [client_one, client_two, board]
            goes_first = random.choice((0, 1))
            goes_last = not goes_first
            server.send_client(
                last[goes_first],
                "start",
                {"turn": "first", "opp_name": last[goes_last].name},
            )
            server.send_client(
                last[goes_last],
                "start",
                {"turn": "last", "opp_name": last[goes_first].name},
            )
        else:
            # Both are connected; no open spots, create one
            self.client_pairs.append([clt_data, shared.Board()])

    def remove_client(self, clt_data):
        for client_pair in self.client_pairs[:]:
            if clt_data in client_pair:
                if len(client_pair) == 3:
                    other_client_idx = not client_pair.index(clt_data)

                    print(
                        f"[DEBUG] Left clt: {clt_data}, Other clt: {client_pair[other_client_idx]}\n"
                        f"List of paired clients: {self.client_pairs}\nTime: {__import__('time').time()}"
                    )

                    other_client = client_pair[other_client_idx]
                    self.client_pairs.remove(client_pair)

                    server.send_client(
                        client_pair[other_client_idx],
                        "disconn",
                        b"Opponent Disconnected",
                    )

                    server.disconnect_client(other_client, force=False)
                else:
                    self.client_pairs.remove(client_pair)
                print("[DEBUG] BYE BYE CLIENTS")
                break


addr, port = hisock.input_server_config()
server = hisock.HiSockServer((addr, port))

data = ServerData()


@server.on("join")
def on_join(clt_data):
    data.add_client(clt_data)
    print(data.client_pairs)


@server.on("leave")
def on_leave(clt_data):
    print(f"[DEBUG] in on_leave: {clt_data} LEFT, REMOVING CLIENT")
    data.remove_client(clt_data)
    print(data.client_pairs)


server.start()
