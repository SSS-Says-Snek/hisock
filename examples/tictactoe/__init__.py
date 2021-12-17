from . import tictactoe_client, tictactoe_server


def run(client_or_serv="input"):
    if client_or_serv == "input":
        user_input = input("Are you connecting to or hosting a tictactoe match? (C/H) ")

        if user_input.lower() == "c":
            tictactoe_client.run()
        elif user_input.lower() == "h":
            tictactoe_server.run()
        else:
            print("No option selected, aborting...")
    elif client_or_serv.lower() == "client":
        tictactoe_client.run()
    elif client_or_serv.lower() == "server":
        tictactoe_server.run()
