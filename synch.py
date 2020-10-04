"""


To print the output: https://github.com/astanin/python-tabulate
Amb la fancygrid?
(cal mirar si es pot anar escopint la taula progressivament o només es pot quan
ja tens tots els valors recopilats)
"""

from datetime import datetime

from settings import config
from buckets_manager import BucketManager
from splitwise_manager import SplitWiseManager


class SplitwiseToBucketsSynch:
    def __init__(self):
        self.sw = SplitWiseManager()
        self.bk = BucketManager()

        self.sw.authenticate()

        self.expenses = self.sw.get_expenses()
        self.current_user = self.sw.get_current_user()

    @staticmethod
    def sw_to_bk_amount(amount, negative=False):
        if amount is not float:
            amount = float(amount)
        if negative:
            amount = amount * -1
        return int(amount*100)

    def run(self):
        for expense in self.expenses:
            print('')

            # Expense object docs: https://splitwise.readthedocs.io/en/stable/api.html#splitwise.expense.Expense  #noqa
            date_sw = expense.getDate()
            date_py = datetime.strptime(date_sw, '%Y-%m-%dT%H:%M:%SZ')
            paid_by_me, my_expense_user_obj = self.sw.get_my_expense_user_obj(
                expense)
            if not my_expense_user_obj:
                print(
                    "Error: Found an expense without any UserExpense, looks "
                    "like Splitwise monkeys blew up something... skipping.")
                continue
            paid_share = float(my_expense_user_obj.getPaidShare())
            owed_share = float(my_expense_user_obj.getOwedShare())
            bucket_name = config['SplitwiseCategoriesToBucketNames'].get()[
                expense.getCategory().getId()
            ]
            bucket_id = self.bk.get_bucket_id(bucket_name)
            print(f"Expense {expense.getDescription()}:")
            print(f"{bucket_id=}")
            print(
                f"Paid share: {my_expense_user_obj.getPaidShare()}, "
                f"owed share: {owed_share}")
            if paid_by_me:
                """
                CASE A: Ticket that I paid
                Say I paid 50€ of which my share is 10€.
                We need to register 2 transactions in Buckets:
                T1: An expense transaction for my share of the expense, charged
                on bks.default_acc at the corresponding Bucket.
                T2: A TRANSFER transaction from bks.default_acc to 
                bks.splitwise_acc for the rest of the quantity that I paid.

                By now the expense Bucket is not set and needs to be set 
                manually after importing them.
                """
                print("Case A (ticket that I paid)")

                # Creating T1
                if self.bk.transaction_exist(expense.getId()):
                    print(f"Already exists in Buckets, skipping.")
                    continue

                account = 'payment'
                if self.sw.is_cash(expense):
                    account = 'cash'
                self.bk.create_expense(
                    date=date_py,
                    amount=self.sw_to_bk_amount(owed_share, True),
                    memo=expense.getDescription(),
                    fi_id=expense.getId(),
                    general_cat=None,
                    bucket_id=bucket_id,
                    account=account
                )

                # Creating T2
                owed_by_others = round(paid_share - owed_share, 2)
                self.bk.create_transfer(
                    date=date_py,
                    amount=self.sw_to_bk_amount(owed_by_others),
                    memo=expense.getDescription(),
                    fi_id=expense.getId(),
                    from_account=account,
                    to_account='splitwise'
                )

            elif owed_share > 0:
                """
                CASE B: Ticket that someone else paid, in which I'm included
                Say someone paid 30€ and my share is 5€.
                We need 1 transaction to be registered in Buckets:
                T1: An expense transaction charged at the bks.splitwise_acc 
                account by the amount of my share of the expense, at the 
                corresponding Bucket according to the Splitwise category of 
                the expense. 

                By now the expense Bucket is not set and needs to be set 
                manually after importing them.
                """
                print("Case B (paid by someone else)")

                if self.bk.transaction_exist(expense.getId()):
                    print(f"Already exists in Buckets, skipping.")
                    continue

                self.bk.create_expense(
                    date=date_py,
                    amount=self.sw_to_bk_amount(owed_share, True),
                    memo=expense.getDescription(),
                    fi_id=expense.getId(),
                    general_cat=None,
                    bucket_id=bucket_id,
                    account='splitwise'
                )
            else:
                print(
                    "Error: this expense is marked as paid by others but then "
                    "your owed share is 0, this should be an Splitwise's API "
                    "mistake, check it out.")
                print("Expense dump: " + my_expense_user_obj.__dict__)

            print("")


SplitwiseToBucketsSynch().run()
