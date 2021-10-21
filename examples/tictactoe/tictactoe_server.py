# Imports

import pathlib
import random
import statistics
import sys

# Import stuff, as this situation's a bit wonky
# This is not needed in usual hisock code. However, in this odd case,
# imports need to be configured first like this

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))  # Not needed usually; used to run examples

from hisock import start_server, utils


# Data class, as to prevent using those dirty globals
class Data:
    def __init__(self):
        self.boards = []


# IP and Port establishment

def run():
    if len(sys.argv) - 1 != 1:
        ip_input = input("Enter IP of where the server should be hosted "
                         "(Leave blank for current IP): ")
        if ip_input == '':
            ip_input = utils.get_local_ip()

        port_input = input("Enter port of server: ")
        while port_input == '':
            port_input = input("Enter port of server: ")

        port_input = int(port_input)
    else:
        ip_input = utils.get_local_ip()
        port_input = 6969

    print(f"Starting server at {ip_input}:{port_input}...", end=" ")
    s = start_server((ip_input, port_input))
    print("SUCCESS!")

    # Tic Tac Toe variable initialization
    paired_clients = []
    paired_clients_ip = []
    x_or_o = []

    data = Data()

    # Hisock message receive decorators
    @s.on("join")
    def client_conn(client_info):
        print(f"Client \"{client_info['name']}\" connected")

        # Gathers last pair/user from the list
        try:
            last_pair = paired_clients[-1]
            last_ip_pair = paired_clients_ip[-1]
        except IndexError:
            last_pair = ("Place", "Holder")  # To conform to the 2-1 last pair searchup
            last_ip_pair = ("Place", "Holder")

        if len(last_ip_pair) == 1:  # Pair client to currently available one
            print(f"    - Paired with \"{last_pair[0]}\"")
            paired_clients[-1].append(client_info['name'])
            paired_clients_ip[-1].append(client_info['ip'])

            goes_first = random.random()

            s.send_client(client_info['ip'], "game_start", last_pair[0].encode())
            s.send_client(last_ip_pair[0], "game_start", client_info['name'].encode())

            if goes_first < 0.5:
                # Connected client goes first
                s.send_client_raw(client_info['ip'], b"First")
                s.send_client_raw(last_ip_pair[0], b"Last")
                x_or_o.append(["O", "X"])
            else:
                # Unpaired client goes first
                s.send_client_raw(last_ip_pair[0], b"First")
                s.send_client_raw(client_info['ip'], b"Last")
                x_or_o.append(["X", "O"])

        elif len(last_pair) == 2:  # Available client
            # Appended to variables - no other action taken
            print("    - Currently available (no clients to pair)")
            paired_clients.append([client_info['name']])
            paired_clients_ip.append([client_info['ip']])

    @s.on("leave")
    def player_leave(clt_info):
        print(paired_clients_ip)
        print(f"Client \"{clt_info['name']}\" disconnected")
        for ip_pair in paired_clients_ip[:]:
            for ip in ip_pair:
                if ip == clt_info['ip']:
                    if len(ip_pair) == 1:
                        paired_clients_ip.remove(ip_pair)
                    else:
                        # Uhh I don't know what to do RN
                        cp_ip_pair = ip_pair[:]
                        cp_ip_pair.remove(ip)
                        other_ip = cp_ip_pair[0]
                        s.send_client(other_ip, "opp_disc", clt_info['name'].encode())
                        paired_clients_ip.remove(ip_pair)
        print(paired_clients_ip)

    @s.on("player_turn")
    def player_turn(clt_data, move: int):
        opponent_ip = None  # Suppressing Pycharm warnings
        opponent_letter = None
        idx = None

        # Locates index of player pair
        for x, ip_pair in enumerate(paired_clients_ip):
            for y, ip in enumerate(ip_pair):
                if ip == clt_data['ip']:
                    opponent_ip = paired_clients_ip[x][abs(y - 1)]
                    opponent_letter = x_or_o[x][abs(y - 1)]
                    idx = [x, abs(y - 1)]

        if len(data.boards) == idx[0]:
            data.boards.append([" " for _ in range(9)])
        data.boards[idx[0]][move] = x_or_o[idx[0]][idx[1]]

        # Winning combos
        row1, row2, row3 = [data.boards[idx[0]][i:i + 3] for i in range(0, 9, 3)]
        col1, col2, col3 = [data.boards[idx[0]][i:7 + i:3] for i in range(3)]
        diag1, diag2 = [
            [data.boards[idx[0]][0], data.boards[idx[0]][4], data.boards[idx[0]][8]],
            [data.boards[idx[0]][2], data.boards[idx[0]][4], data.boards[idx[0]][6]]
        ]
        no_winner = True

        for check in (row1, row2, row3, col1, col2, col3, diag1, diag2):
            if (check[0] == check[1] == check[2]) and statistics.mode(check) != ' ':  # WINNER!
                no_winner = False
                winner = statistics.mode(check)  # Checks the most occurances
                winner = "X" if winner == "O" else "O"

                if winner == opponent_letter:
                    s.send_client(opponent_ip, "win", str(move).encode())
                    s.send_client(clt_data['ip'], 'lose', str(move).encode())
                else:
                    s.send_client(clt_data['ip'], "win", str(move).encode())
                    s.send_client(opponent_ip, 'lose', str(move).encode())

        spaces = [
            i == " " for i in data.boards[idx[0]]
        ]

        if not any(spaces):
            # No spaces and no winner - Tied
            no_winner = False  # Even though it's technically true
            s.send_client(opponent_ip, "tie", str(move).encode())
            s.send_client(clt_data['ip'], 'tie', str(move).encode())

        if no_winner:
            s.send_client(opponent_ip, "player_turn", str(move).encode())

    while True:
        try:
            # Runs server
            s.run()
        except utils.NoMessageException:
            pass


if __name__ == "__main__":
    run()
