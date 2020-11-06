import sqlite3

from settings import config

debug = config['debug'].get()
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
        if debug:
            self.connection.set_trace_callback(print)
        self.cursor = self.connection.cursor()
        self.account_ids = {}
        for keyword, account_name in config['AccountsKeywords'].get().items():
            self.account_ids.update({
                keyword: self.get_account_id(account_name)
            })
        cmd = f"SELECT * FROM bucket WHERE id > 0"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()
        self.bucket_ids = {}
        if len(results) > 0:
            for bucket in results:
                self.bucket_ids.update({bucket[2]: bucket[0]})

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

    def get_transfer_transactions_by_fi_id(self, fi_id):
        cmd = (f"SELECT * FROM account_transaction "
               f"WHERE fi_id=? AND general_cat=?")
        values = (fi_id, 'transfer')
        self.cursor.execute(cmd, values)
        return self.cursor.fetchall()

    def get_expense_transactions_by_fi_id(self, fi_id, account):
        if account in ('cash', 'payment'):
            acc_q = "AND account_id IN (?, ?)"
            acc_v = (self.account_ids['cash'], self.account_ids['payment'])
        elif account == 'splitwise':
            acc_q = "AND account_id = ?"
            acc_v = (self.account_ids['splitwise'], )
        else:
            raise ValueError(
                "Calling get_expense_transactions_by_fi_id with an account "
                "that's not cash, payment or splitwise."
            )
        cmd = (f"SELECT * FROM account_transaction "
               f"WHERE "
               f"   fi_id=? "
               f"   AND (general_cat IS NULL OR general_cat = '')"
               f"   {acc_q}")
        values = [fi_id, ]
        values.extend(acc_v)
        self.cursor.execute(cmd, values)
        return self.cursor.fetchall()

    def get_bucket_transaction_by_account_trans_id(self, account_trans_id):
        cmd = f"SELECT * FROM bucket_transaction WHERE id=?"
        values = (account_trans_id, )
        self.cursor.execute(cmd, values)
        return self.cursor.fetchall()

    """
    Managing transfers
    """
    def create_or_update_transfer(self, **kwargs):
        """
        :param kwargs: 'date', 'amount', 'memo', 'fi_id', 'from_account',
            'to_account'
        """
        if kwargs['from_account'] not in self.account_ids:
            raise ValueError(
                f"Specified {kwargs['from_account']=} is not valid."
            )
        if kwargs['to_account'] not in self.account_ids:
            raise ValueError(
                f"Specified {kwargs['to_account']=} is not valid."
            )

        existing_transactions = self.get_transfer_transactions_by_fi_id(
            kwargs['fi_id']
        )
        if len(existing_transactions) > 0:
            del kwargs['fi_id']
            self.update_transfer(existing_transactions, **kwargs)
        elif kwargs['amount'] != 0:
            self.create_transfer(**kwargs)

    def create_transfer(
            self, **kwargs
    ):
        """
        :param kwargs: 'date', 'amount', 'memo', 'from_account',
            'to_account'
        """
        kwargs['general_cat'] = 'transfer'
        self.create_account_transaction(**kwargs)
        kwargs['amount'] *= -1
        self.create_account_transaction(**kwargs)

    def update_transfer(
            self, existing_transfer_transactions, date, amount, memo,
            from_account, to_account
    ):
        outcoming_t = None
        incoming_t = None
        for t in existing_transfer_transactions:
            # [4] is amount
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
            account_id=from_account,
            amount=amount * -1,
            memo=memo,
            general_cat='transfer'
        )
        self.update_account_transaction(
            trans_id=incoming_t[0],
            date=date,
            account_id=to_account,
            amount=amount,
            memo=memo,
            general_cat='transfer'
        )

    """
    Manage expenses
    """
    def create_or_update_expense(self, **kwargs):
        if kwargs['account'] not in self.account_ids:
            raise ValueError(f"Specified {kwargs['account']=} is not valid.")

        existing_transactions = self.get_expense_transactions_by_fi_id(
            kwargs['fi_id'], kwargs['account']
        )
        print(f"existing transactions: {existing_transactions}")
        if len(existing_transactions) > 0:
            del kwargs['fi_id']
            self.update_expense(existing_transactions, **kwargs)
        elif kwargs['amount'] != 0:
            self.create_expense(**kwargs)

    def create_expense(
        self, date, amount, memo, fi_id, general_cat, bucket_id, account
    ):
        if account not in self.account_ids:
            raise ValueError(f"Specified {account=} is not valid.")

        transaction_id = self.create_account_transaction(
            date, account, amount, memo, fi_id, general_cat
        )
        # self.categorize_transaction(
        #     bucket_id, date, amount, memo, transaction_id
        # )

    def update_expense(
        self, existing_expense_transactions, date, amount, memo, general_cat,
            bucket_id, account
    ):
        """
        The other two can be a payment_expense and a splitwise_expense.
        We need to update the expense belonging to the same account, as this
        method is going to be called another time for the other transaction if
        existing.

        But for payment expenses the account could've changed, not in
        splitwise ones.
        """
        expense_t = None

        for t in existing_expense_transactions:
            # [3] is account.
            if t[3] == self.account_ids['splitwise']:
                expense_t = t
            elif t[3] in (
                    self.account_ids['payment'], self.account_ids['cash']):
                # Only if it's not the splitwise one we check if it's one of
                # the other 2.
                expense_t = t

        if expense_t is None:
            raise MissingExpenseTransaction(
                f"The expense couldn't be updated because "
                f"none of the existing transactions have an empty general_cat "
                f"and matches the same account '{account}'"
            )

        self.update_account_transaction(
            trans_id=expense_t[0],
            date=date,
            account_id=account,
            amount=amount,
            memo=memo,
            general_cat=general_cat
        )

        # TO DO: categorization on update, ONLY IF there's one of the valid
        # buckets in config, to the Splitwise data will prevail but not
        # erase the manually categorized buckets.
        # self.categorize_transaction(
        #     bucket_id, date, amount, memo, expense_t[0]
        # )

    """
    Managing transactions
    Each Expense creates or updates 1 transaction.
    Each Transfer creates or updates 2 transactions.
    """
    def create_account_transaction(
            self, date, account_id, amount, memo, fi_id, general_cat,
    ):
        if amount == 0:
            # A 0€ transaction should've been sent to Update and never here.
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
            self.account_ids[account_id],
            self.decimal_to_bk_amount(amount),
            memo,
            fi_id,
            general_cat
        )
        print(f"creating, {values=}")
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
            self.account_ids[account_id],
            self.decimal_to_bk_amount(amount),
            memo,
            general_cat,
            trans_id
        )
        print(f"updating, {values=}")
        self.cursor.execute(cmd, values)
        self.connection.commit()
        if self.cursor.rowcount < 0:
            raise TransferTransactionUpdateFailed(
                f"Failed to update the transaction {id=}"
            )

    def get_bucket_id(self, bucket_name):
        if bucket_name in self.bucket_ids:
            return self.bucket_ids[bucket_name]
        else:
            return None

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
            values = (date, bucket_id, self.decimal_to_bk_amount(amount),
                      memo, trans_id)
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
                values = (date, self.decimal_to_bk_amount(amount), memo,
                          trans_id)
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
                values = (date, bucket_id, self.decimal_to_bk_amount(amount),
                          memo, trans_id)
        self.cursor.execute(cmd, values)
        self.connection.commit()

    @staticmethod
    def decimal_to_bk_amount(amount):
        if amount is not float:
            amount = float(amount)
        return int(round(amount * 100))

    def test(self):
        cmd = "SELECT * FROM account_transaction"
        self.cursor.execute(cmd)
        results = self.cursor.fetchall()

        print(results)
