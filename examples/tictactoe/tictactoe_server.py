import pathlib
import random
import statistics
import sys

sys.path.append(str(pathlib.Path('.').parent.parent))  # Not needed usually; used to run examples

try:
    from hisock import (
        start_server,
        utils
    )
except ImportError:
    print("Because I'm dumb, run the example at the root of the package. Thank you!")
    sys.exit()


class Data:
    def __init__(self):
        self.board = [' ' for _ in range(9)]


ip_input = input("Enter IP of where the server should be hosted "
                 "(Leave blank for current IP): ")

if ip_input == '':
    ip_input = utils.get_local_ip()

port_input = input("Enter port of server: ")

while port_input == '':
    port_input = input("Enter port of server: ")

port_input = int(port_input)
print(f"Starting server at {ip_input}:{port_input}...", end=" ")
s = start_server((ip_input, port_input))
print("SUCCESS!")

paired_clients = []
paired_clients_ip = []
x_or_o = []

data = Data()


@s.on("join")
def client_conn(client_info):
    print(f"Client \"{client_info['name']}\" connected")

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
            s.send_client_raw(client_info['ip'], b"First")
            s.send_client_raw(last_ip_pair[0], b"Last")
            x_or_o.append(["O", "X"])
        else:
            s.send_client_raw(last_ip_pair[0], b"First")
            s.send_client_raw(client_info['ip'], b"Last")
            x_or_o.append(["X", "O"])
    elif len(last_pair) == 2:  # Available client
        print("    - Currently available (no clients to pair)")
        paired_clients.append([client_info['name']])
        paired_clients_ip.append([client_info['ip']])


@s.on("player_turn")
def player_turn(clt_data, move: int):
    opponent_ip = None  # Suppressing Pycharm warnings
    opponent_letter = None
    idx = None
    for x, ip_pair in enumerate(paired_clients_ip):
        for y, ip in enumerate(ip_pair):
            if ip == clt_data['ip']:
                opponent_ip = paired_clients_ip[x][abs(y-1)]
                opponent_letter = x_or_o[x][abs(y-1)]
                idx = [x, abs(y-1)]

    data.board[move] = x_or_o[idx[0]][idx[1]]
    row1, row2, row3 = [data.board[i:i+3] for i in range(0, 9, 3)]
    col1, col2, col3 = [data.board[i:7+i:3] for i in range(3)]
    diag1, diag2 = [
        [data.board[0], data.board[4], data.board[8]],
        [data.board[2], data.board[4], data.board[6]]
    ]
    no_winner = True
    for check in (row1, row2, row3, col1, col2, col3, diag1, diag2):
        if (check[0] == check[1] == check[2]) and statistics.mode(check) != ' ':  # WINNER!
            no_winner = False
            winner = statistics.mode(check)
            winner = "X" if winner == "O" else "O"

            if winner == opponent_letter:
                s.send_client(opponent_ip, "win", str(move).encode())
                s.send_client(clt_data['ip'], 'lose', str(move).encode())
            else:
                s.send_client(clt_data['ip'], "win", str(move).encode())
                s.send_client(opponent_ip, 'lose', str(move).encode())

    spaces = [i == " " for i in data.board]

    if not any(spaces):
        no_winner = False  # Even though it's technically true
        s.send_client(opponent_ip, "tie", str(move).encode())
        s.send_client(clt_data['ip'], 'tie', str(move).encode())

    if no_winner:
        s.send_client(opponent_ip, "player_turn", str(move).encode())


while True:
    try:
        s.run()
    except utils.NoMessageException:
        pass
