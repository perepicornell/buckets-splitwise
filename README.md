# Buckets-Splitwise synchronization

## Installation

You need to set up 3 things for it to work:

1. Buckets.
2. Your Splitwise account.
3. This script itself.

### 1. Setting up Buckets

This script synchronizes the transactions from your Splitwise account into
[Bucket's](https://www.budgetwithbuckets.com/) budget.

To have Buckets prepared to work with this script is fairly simple.

You just need:

A) A configuration of accounts like this:

- An Account for your Splitwise balance. Name it however you want.
- An Account for "bank payments". By default, this script assumes that everything that every
Splitwise expense that you paid, you paid it from the same bank account. 
If you are already a Buckets user, you might have this"main account" already. Any name is valid.
- An Account for "cash payments", again any name is valid. More about it further in the docs.

B) The right initial balance in your Splitwise account in Buckets:

The simplest way is to set the balance to the current balance you have in 
Splitwise, and further on when you set up the script, remember to set the
`ExpensesDatedAfter` setting to today, so it will start synching your new
Splitwise transactions starting from tomorrow.

Beware that if anyone modifies, creates or delete a transaction in Splitwise 
before that date, your Splitwise balance will change and will not match anymore
the balance in Buckets.

To avoid that you can let the script to the default synching time span, which
is 90 days, and then adjust the Splitwise's account balance in Buckets to the
current one.

By doing that, if any change is done in Splitwise (for transactions not older
than 90 days) it will be reflected correctly in Buckets the next time you run 
the script.

But, of course, you will have to clean up a lot your Buckets transactions 
within these 3 months, as you will end up with your old system of tracking 
Splitwise overlapped with that new one.

In any case, just do some experimenting, but firstly **make sure to
duplicate your budget file to have a fresh backup**, until you figured out
the best way for you to set the initial balance. 

### 2. Create Splitwise app for API access

To allow connections to its API (which is the interface that Splitwise provides for apps
to access their data) we cannot just tell the script your Splitwise's login and
password, instead we need an *authorization token* that Splitwise will
generate and give it to you. Think of it as if it's a password but for accessing
their API instead of their normal interface.

Another requirement in order to obtain a token is to create your own *Splitwise 
application*.

Open this URL and then "Register your application":
 
https://secure.splitwise.com/oauth_clients

Put any data you want in it, but put that in the callback url field:
http://localhost:1337/generate_token/

Otherwise is not going to work.

That's all for now, later we'll use the script to generate the token.

### 3. "Install" the script

Currently this is not an application that you can just download and run, but
the source code in Python.

This means that you need to download the source code to your computer and 
set up an environment (by installing a couple of things) so you can run the
script.

I'll take a look on how to distribute python scripts compiled or in some way 
that saves you from these next steps, but for now that's what I have!

For the installation and also for running the script you need to use the
command line, by opening the corresponding terminal window of your OS.

If you don't know how to change the current folder and run commands in a 
terminal, look for "command line tutorial" at some search engine before 
continuing.

#### 1. Clone or download the files

In the [app's repository](https://github.com/perepicornell/buckets-splitwise), 
get the files by downloading them as .zip or just clone the repo in some 
folder.

#### 2. Environment
You need the proper version of Python and some third party packages installed 
in order to be able to run the script.
There's an app call Poetry that handles that for you, and it creates a "virtual
environment", which is like an "enclosed space" in which Python and the 
packages are installed inside, instead of installing
everything directly in your system and making a mess.

Check their [website](https://python-poetry.org/) website and follow
the installation instructions.

To create the virtual environment and install the dependencies go to the 
app's folder and run:

    poetry install

Then get inside the virtual environment's shell by doing:

    poetry shell

At this point, when you run python programs you'll be running them inside the virtual environment.

**Remember:** In the future, to run the script again you'll have to get inside
 that *virtual environment's shell* first (by using the same `poetry shell` 
 command), otherwise if you just go to the folder and try to
run it you'll see some errors and will not work.

#### 4. Settings

You need to duplicate the `config.template.yaml` file and call it 
`config.yaml`.
    
Then edit it with a plain text editor, like vim for instance: 
    
    vim config.yaml

In Windows, Notepad is also a plain text editor.

The settings file itself is full with tips about how to fill the values.

Nonetheless, some clarifications:

`CallbackUrl`: If for some reason you want to change that, then you have to
change it also in your Splitwise's application settings or it will not work.

`ConsumerKey` and `ConsumerSecret`:  These keys belong to your newly created
Splitwise application. To obtain them, access again the 
[URL that you used before](https://secure.splitwise.com/oauth_clients) for
creating the app and go to the app's settings.

`LastValidToken`: leave it empty for now.

#### 5. Generate Spliwise token

Having the `ConsumerKey` and `ConsumerSecret` settings saved, we can now
generate the token. 
Run:

    python authenticate.py
    
And follow the instructions.

You should only need to generate it once, unless Splitwise revokes tokens for
some reason, if at some point it stops working just generate it again.

When you end up with the newly generated token copied to `LastValidToken` 
settings, you're finally done with the installation and configuration, 
congratulations!

## Usage

**Before your first run, I strongly recommend you to make a backup of your 
budget file!**

To run the synchronization, go inside the shell of your virtual environment
(if you're not already there) by following the same steps than during the
set-up:

Go to the folder where you cloned the script and run

`poetry shell`

Then you can run:

`python synch.py`

Whenever there's any change in the Splitwise transactions (created, updated or
deleted), run the script again and the changes will be reflected.

That's true as long as it's a change dated after the `ExpensesDatedAfter`date 
and within the `ExpensesDaysAgo` limit. For older changes, you will have to
reproduce them manually in Buckets. 

You cannot set an immense number of days in `ExpensesDaysAgo` and expect to 
work because Splitwise have a limit of expenses they can send to you for each
petition. I don't know the number, they just say something like *a big enough
limit*.

## Some potential doubts and specific cases

### How do I register it when someone pays me their Splitwise debt to me?

This is going to automatically be imported in your budget, as these payments are 
included in the expenses retrieved from Splitwise.

### And if it's me returning a debt to someone?

I still have to implement this, by now, manually create a transaction in Buckets.

### What if an expense is modified in Splitwise?

The script updates all the transactions in your Buckets according
to the latest data obtained from Splitwise, therefore, the changes will be reflected.

If an expense that is older than that or that will not be retrieved because of 
the limit is modified, the you need to locate it in Buckets and modify it manually.

### The synchronization is importing an expense under a certain category (bucket), then I change it, but next time I run the script it changes back

If the expense's category in Splitwise is one of the SplitwiseCategoriesToBucketNames setting,
this correlation is going to prevail when synching.
If you manually change an expense that is categorized in SplitwiseCategoriesToBucketNames and you don't want
the script to modify it back again, you have to edit your expense in Splitwise and uncategorize it 
(or set it to a category that you didn't relate to a bucket in SplitwiseCategoriesToBucketNames).
