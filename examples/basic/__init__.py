from . import example_server, example_client


def run(client_or_serv="input"):
    if client_or_serv == "input":
        user_input = input("Are you connecting to or hosting a tictactoe match? (C/H) ")

        if user_input.lower() == "c":
            example_client.run()
        elif user_input.lower() == "h":
            example_server.run()
        else:
            print("No option selected, aborting...")
    elif client_or_serv.lower() == "client":
        example_client.run()
    elif client_or_serv.lower() == "server":
        example_server.run()
