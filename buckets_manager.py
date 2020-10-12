import sqlite3

from settings import config

config = config['Buckets']


class MissingSpliwiseAccount(Exception):
    pass


class MissingTransferTransactions(Exception):
    pass


class MissingExpenseTransaction(Exception):
    pass


class TransferTransactionUpdateFailed(Exception):
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

    def transaction_exist(self, fi_id):
        results = self.get_transactions_by_fi_id(fi_id)
        if len(results) > 0:
            return True
        return False

    def get_transactions_by_fi_id(self, fi_id):
        cmd = f"SELECT * FROM account_transaction WHERE fi_id=?"
        values = (fi_id, )
        self.cursor.execute(cmd, values)
        return self.cursor.fetchall()

    def get_bucket_transaction_by_account_trans_id(self, account_trans_id):
        cmd = f"SELECT * FROM bucket_transaction WHERE id=?"
        values = (account_trans_id, )
        self.cursor.execute(cmd, values)
        return self.cursor.fetchall()

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

    def update_transfer(
            self, existing_transactions, date, amount, memo, from_account,
            to_account
    ):
        """
        Up to 3 transactions might come in existing_transactions, 2 of them
        should be the corresponding of a transfer, and the 3rd, if any, has
        general_cat=None because it's a normal expense.

        We need to identify the transfer transactions and which one is the
        outcoming and the incoming.
        """
        outcoming_t = None
        incoming_t = None
        for t in existing_transactions:
            # general_cat
            if t[7] != 'transfer':
                continue
            # amount
            if t[4] > 0:
                incoming_t = t
            else:
                outcoming_t = t

        if None in (outcoming_t, incoming_t):
            raise MissingTransferTransactions(
                f"The transfer couldn't be updated because "
                f"at least one of the 2 transactions is missing."
            )

        self.update_account_transaction(
            trans_id=outcoming_t[0],
            date=date,
            account_id=self.account_ids[from_account],
            amount=amount * -1,
            memo=memo,
            general_cat='transfer'
        )
        self.update_account_transaction(
            trans_id=incoming_t[0],
            date=date,
            account_id=self.account_ids[to_account],
            amount=amount,
            memo=memo,
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

    def update_expense(
        self, existing_transactions, date, amount, memo, general_cat,
            bucket_id, account
    ):
        """
        Up to 3 transactions might come in existing_transactions but only 1 of
        them can be an expense. The other 2 should belong to a transfer, if
        any.

        The expense will have general_cat == ''.
        """
        expense_t = None
        for t in existing_transactions:
            # general_cat
            if t[7] in ('', None):
                expense_t = t

        if expense_t is None:
            raise MissingExpenseTransaction(
                f"The expense couldn't be updated because "
                f"none of the existing transactions have an empty general_cat."
            )

        if account not in self.account_ids:
            raise ValueError(f"Specified {account=} is not valid.")

        self.update_account_transaction(
            trans_id=expense_t[0],
            date=date,
            account_id=self.account_ids[account],
            amount=amount,
            memo=memo,
            general_cat=general_cat
        )
        self.categorize_transaction(
            bucket_id, date, amount, memo, expense_t[0]
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

    def update_account_transaction(
            self, trans_id, date, account_id, amount, memo, general_cat,
    ):
        cmd = f"""
        UPDATE account_transaction
        SET 
            posted = ?,
            account_id = ?, 
            amount = ?,
            memo = ?,
            general_cat = ?
        WHERE
            id = ?
        """
        values = (
            date,
            account_id,
            amount,
            memo,
            general_cat,
            trans_id
        )
        self.cursor.execute(cmd, values)
        self.connection.commit()
        if self.cursor.rowcount < 0:
            raise TransferTransactionUpdateFailed(
                f"Failed to update the transaction {id=}"
            )

    def get_bucket_id(self, bucket_name):
        cmd = f"SELECT * FROM bucket WHERE name='{bucket_name}' LIMIT 1"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()
        if len(results) == 0:
            return None
        return results[0][0]

    def categorize_transaction(self, bucket_id, date, amount, memo, trans_id):
        existing = self.get_bucket_transaction_by_account_trans_id(trans_id)
        if len(existing) == 0:
            # Creating a bucket_transaction without bucket_id is possible but
            # it litters the database with unused data. Just skip it and when
            # the user manually clicks on "Categorize" this is going to be
            # created.
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
            values = (date, bucket_id, amount, memo, trans_id)
        else:
            if bucket_id is None:
                # User might've changed the bucket manually, leaving bucket_id
                # alone.
                cmd = """
                UPDATE bucket_transaction
                SET
                    posted = ?,
                    amount = ?,
                    memo = ?
                WHERE
                    account_trans_id = ?
                """
                values = (date, amount, memo, trans_id)
            else:
                # We cannot know if the user changed the bucket manually or
                # not. So, if a valid bucket can be resolved from
                # SplitwiseCategoriesToBucketNames, this one prevails.
                cmd = """
                UPDATE bucket_transaction
                SET
                    posted = ?,
                    bucket_id = ?,
                    amount = ?,
                    memo = ?
                WHERE
                    account_trans_id = ?
                """
                values = (date, bucket_id, amount, memo, trans_id)
        self.cursor.execute(cmd, values)
        self.connection.commit()

    def test(self):
        cmd = "SELECT * FROM account_transaction"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()

        print(results)
