# Buckets-Splitwise synchronization

## Installation

### 1. Clone or download the files

In the [app's repository](https://github.com/perepicornell/buckets-splitwise), get the
files by downloading them as .zip or just clone the repo in some folder.

### 2. Environment
You need the proper version of Python and some third party packages installed in order to
be able to run the script.
There's an app call Poetry that handles that for you, and it creates a "virtual environment",
which is like an "enclosed space" in which Python and the packages are installed inside, instead of installing
everything in your system and making a mess.

Check their [website](https://python-poetry.org/) website for installation instructions.

To create a virtual environment and install the dependencies specified in pyproject.toml file,
inside the app's folder run:

    poetry install

Then get inside the virtual environment's shell by doing:

    poetry shell

At this point, when you run python programs you'll be running them inside the virtual environment.
Whenever you want to run the script again you'll have to get inside that shell again (by
using the same `poetry shell` command), otherwise if you just go to the folder and try to
run it you'll see some errors and will not work.

### 3. Create Splitwise app for API access

To allow connections to its API (which is the interface that Splitwise provides for apps
to access their data) Splitwise needs to create a Splitwise App.
Then when you or any user wants to use a script that access the API, Splitwise is going to
ask the user to authorize the app to access their data.

In apps that are a web service, they have their own app created and the users only need to
accept the authorization when they want to use it.

As this is a local script there is not such app, so in order to obtain the necessary credentials
for the script to run you need to create your own Splitwise app.

Open this URL and then "Register your application":
 
https://secure.splitwise.com/oauth_clients
 
Put any data you want in it, but put that in the callback url you put:
http://localhost:1337/generate_token/

Otherwise is not going to work. 

### 4. Settings

You need to duplicate the `config.template.yaml` file and call it `config.yaml`:

    cp config.template.yaml config.yaml
    
And edit it with a plain text editor, like vim for instance: 
    
    vim config.yaml

And fill it with your information. By now leave the LastValidToken values empty.
Read the config.yaml comments carefully, there are crucial instructions there!

### 5. Generate Spliwise token

To generate the token run:

    python authenticate.py
    
And follow the instructions.

You should only need to generate it once, unless Splitwise revokes tokens for
some reason, if at some point it stops working just generate it again.

### 6. Launch synchronization

Before your first run, I strongly recommend you to make a backup of your budget
file!
You may need to adjust many things in the settings (like the SplitwiseCategoriesToBucketNames)
before it runs as smooth as you want, so, do all this testing in a dummy copy.

Having now a valid token in your config.yaml file, run...

    python synch.py
    
## Usage

If you already had your own system for entering the Splitwise expenses into Buckets,
you need to set the date of the last expense you entered (or today's date, if you're up to date)
in order to prevent duplicating entries.

- Locate the last expense in Splitwise that you entered in Buckets and make sure that
all the transactions from this day are inserted in Buckets.
- Then write down that date in the config file in this format:


    ExpensesDatedAfter: "2020-08-26"
    
Remember that if you or someone enters an expense older than this date, the script is not
going to synchronize it.

- In Buckets, create an Account for Splitwise (as if it's another bank account), and set its 
initial balance to your global balance in Splitwise.

With this approach, you'll have your Splitwise balance reflected in your accounts, 
therefore, Buckets is going to think that you have this money at your disposition.
Obviously that's not actual money that you have access to but money that other
 people owes you.


### How do I register it when someone pays me their debt with me?

This is going to automatically be imported in your budget, as these payments are 
included in the expenses retrieved from Splitwise.

### And if it's me returning a debt to someone?

I still have to implement this, by now, manually create a transaction in Buckets.

### What if an expense is modified in Splitwise?

Still to be developed, but what's going to happen is:

The script is going to update all the transactions in your Buckets according
to the latest data obtained from Splitwise, therefore, the changes will be reflected.
But that only works if the modified expense is newer than the last expense retrieved,
according to ExpensesDaysAgo and ExpensesLimit settings.

If an expense that is older than that or that will not be retrieved because of 
the limit is modified, the you need to locate it in Buckets and modify it manually.

# Potential problems or doubts

### The synchronization is importing an expense under a certain category (bucket), then I change it, but next time I run the script it changes back

If the expense's category in Splitwise is one of the SplitwiseCategoriesToBucketNames setting,
this correlation is going to prevail when synching.
If you manually change an expense that is categorized in SplitwiseCategoriesToBucketNames and you don't want
the script to modify it back again, you have to edit your expense in Splitwise and uncategorize it 
(or set it to a category that you didn't relate to a bucket in SplitwiseCategoriesToBucketNames).
