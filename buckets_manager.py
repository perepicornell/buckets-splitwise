import sqlite3

from settings import config

config = config['Buckets']


class MissingSpliwiseAccount(Exception):
    pass


class BucketManager:
    """
    According to https://docs.budgetwithbuckets.com/fileformat/
    Transactions are stored at the 'account_transaction' table.

    account_transaction's scheme:
        id INTEGER PRIMARY KEY
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        posted TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            Note: It actually needs a datetime string, not a timestamp number.
        account_id INTEGER
        amount INTEGER
        memo TEXT
        fi_id TEXT
        general_cat TEXT DEFAULT ''
        notes TEXT DEFAULT ''
        cleared TINYINT DEFAULT 0
        FOREIGN KEY(account_id) REFERENCES account(id)

    From the documentation:
    - The fi_id column represents an account-unique ID (typically assigned by
    the bank) for a transaction.
    - general_cat should be one of the strings "", "income", or "transfer"

    The empty string in general_cat means it's an expense.

    As iffy pointed out here https://github.com/buckets/application/issues/507
    We also need to access the 'account' table in order to get the Splitwise
    account ID.

    To create transactions that are Transfers:
    - Create am expense transaction with 'general_cat' set to: 'transfer' for
        the outcoming account.
    - Create an income transaction with the same values but to the incoming
        account.

    account's scheme:
        id INTEGER PRIMARY KEY
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        name TEXT DEFAULT
        balance INTEGER DEFAULT 0
        currency TEXT
        import_balance INTEGER DEFAULT NULL
        closed TINYINT DEFAULT 0
        notes TEXT DEFAULT ''
        offbudget TINYINT DEFAULT 0
        kind TEXT DEFAULT ''

    """

    def __init__(self):
        self.connection = sqlite3.connect(config['BudgetFilePath'].get())
        self.cursor = self.connection.cursor()
        self.account_ids = {}
        for keyword, account_name in config['AccountsKeywords'].get().items():
            self.account_ids.update({
                keyword: self.get_account_id(account_name)
            })

    def get_account_id(self, acc_name):
        cmd = f"SELECT * FROM account WHERE name='{acc_name}'"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()
        if len(results) < 1:
            raise MissingSpliwiseAccount(
                "In your BUCKETS_PAYMENTS_ACCOUNT settings you specified"
                f" '{acc_name}', but no account with this name was found in "
                "your buckets file."
            )
        return results[0][0]

    def transaction_exist(self, sw_id):
        cmd = f"SELECT * FROM account_transaction WHERE fi_id='{sw_id}'"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()
        if len(results) > 0:
            return True
        return False

    def create_transfer(
            self, date, amount, memo, fi_id, from_account, to_account
    ):
        self.create_account_transaction(
            date=date,
            account_id=self.account_ids[from_account],
            amount=amount * -1,
            memo=memo,
            fi_id=fi_id,
            general_cat='transfer'
        )
        self.create_account_transaction(
            date=date,
            account_id=self.account_ids[to_account],
            amount=amount,
            memo=memo,
            fi_id=fi_id,
            general_cat='transfer'
        )

    def create_expense(
        self, date, amount, memo, fi_id, general_cat, bucket_id, account
    ):
        if account not in self.account_ids:
            raise ValueError(f"Specified {account=} is not valid.")

        transaction_id = self.create_account_transaction(
            date, self.account_ids[account], amount, memo, fi_id, general_cat
        )
        self.categorize_transaction(
            bucket_id, date, amount, memo, transaction_id
        )

    def create_account_transaction(
            self, date, account_id, amount, memo, fi_id, general_cat,
    ):
        if amount == 0:
            """ It doesn't make sense to make 0 value expenses, incomes or 
            transfers, which could happen in some situations, i.e. if I paid 
            something that's entirely owed by other people.
            """
            return
        cmd = f"""
        INSERT INTO account_transaction (
            posted, account_id, amount, memo, fi_id, general_cat
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """
        values = (
            date,
            account_id,
            amount,
            memo,
            fi_id,
            general_cat
        )
        self.cursor.execute(cmd, values)
        self.connection.commit()
        created_id = self.cursor.lastrowid
        return created_id

    def get_bucket_id(self, bucket_name):
        cmd = f"SELECT * FROM bucket WHERE name='{bucket_name}' LIMIT 1"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()
        if len(results) == 0:
            return None
        return results[0][0]

    def categorize_transaction(self, bucket_id, date, amount, memo, trans_id):
        if not bucket_id:
            return
        cmd = f"""
        INSERT INTO bucket_transaction (
            posted, bucket_id, amount, memo, account_trans_id
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """
        values = (
            date,
            bucket_id,
            amount,
            memo,
            trans_id
        )
        self.cursor.execute(cmd, values)
        self.connection.commit()
        return self.cursor.lastrowid

    def test(self):
        cmd = "SELECT * FROM account_transaction"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()

        print(results)
