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
    
## Usage

If you already had your own system for entering the Splitwise expenses into Buckets,
you need to set the date of the last expense you entered (or today's date, if you're up to date)
in order to prevent duplicating entries.

- Locate the last expense in Splitwise that you entered in Buckets and make sure that
all the transactions from this day are inserted in Buckets.
- Then write down that date in the .env config in this format:


    SPLITWISE_EXPENSES_DATED_AFTER=2020-08-26
    
Remember that if you or someone enters an expense older than this date, the script is not
going to synchronize it.

- In Buckets, create an Account for Splitwise (as if it's another bank account), and set its 
initial balance to your global balance in Splitwise.

With this approach, remember that Buckets is going to think that you have this money at your disposition,
but obviously, you'll need to ask everyone to settle up the debt with you to actually have it ;)



### How do I register it when someone pays me their debt with me?

Add a Transfer transaction from Splitwise to the account you actually received the money for this amount.

### And if it's me returning a debt to someone?

Add an expense transaction to the Splitwise Account for this amount.
 