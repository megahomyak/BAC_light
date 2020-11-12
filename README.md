# What is this

This is a little bot for my school company, it helps us serve our customers.

Simplified, it works as follows:
* Client makes an order
* Employees get a notification that client made an order
* One employee takes an order
* He DMs the client, and they have an intelligent conversation about details
* Employee serves the client
* Client sends the money
* Employee marks the order as paid


# What to make before launch

Create a file `vk_secrets.ini` in the `vk` directory with the following contents
(you need to fill the {forms}):

    [SECRETS]
    token = {VK group token (allow group control and messages access)}
    group_id = {ID of your VK group}


    [EMPLOYEES]
    employees_chat_peer_id = {ID of chat with employees (actually peer_id; will look like 2000000001, you can get it by printing incoming messages)}


# How to launch it

Just run main_logic.py file from the project's root directory.
