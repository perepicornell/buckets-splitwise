# Buckets-Splitwise synchronization

## Installation

### 1. Environment
Create a virtual environment and install the dependencies specified in pyproject.toml file.
I use poetry for that

    poetry install

Then get inside the virtual environment's shell

    poetry shell
    
### 2. Create splitwise app

As this is a local script (instead of a script running in a web server) I cannot
share the Splitwise secret API key, so you need to make your own.

Open this URL and then "Register your application":
 
https://secure.splitwise.com/oauth_clients
 
Put any data you want in it, but make that in the callback url you put:
http://localhost:1337/generate_token/

Otherwise is not going to work. 

### 3. Settings

    cp .env.example .env
    vim .env
    
And fill it with your information. So far leave the SPLITWISE_LAST_VALID_TOKEN empty.

### 4. Generate Spliwise token

To generate the token:

    python authenticate.py
    
And follow the instructions.

You should only need to generate it once, unless Splitwise revokes tokens for
some reason, if at some point it stops working just generate it again.

### 5. Launch synchronization

Having now a valid token in your .env file...

    python synch.py
    
