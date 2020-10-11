import sys
from datetime import datetime
from dataclasses import dataclass

from tabulate import tabulate
from yaspin import yaspin
from yaspin.spinners import Spinners

from settings import config
from buckets_manager import BucketManager
from splitwise_manager import SplitWiseManager
from splitwise.exception import SplitwiseUnauthorizedException


@dataclass
class ReportLine:
    name: str = ''
    date: str = ''
    total_amount: float = 0.0
    i_paid: float = 0.0
    i_owe: float = 0.0
    case: str = ''
    bucket_name: str = ''

    def __list__(self):
        r = []
        for key, value in self.__dict__.items():
            r.append(value)
        return r

    def __setattr__(self, key, value):
        if isinstance(value, str) and len(value) > 30:
            value = value[:30] + '...'
        super().__setattr__(key, value)


class SplitwiseToBucketsSynch:
    report = []
    report_line = None

    def __init__(self):
        self.sw = SplitWiseManager()
        self.bk = BucketManager()
        with yaspin(
                Spinners.moon,
                text="Authenticating into Splitwise API",
                color="blue"
        ) as spinner:
            try:
                self.sw.authenticate()
            except SplitwiseUnauthorizedException as e:
                spinner.fail(
                    "Authentication failed 😿 your token is not valid. Please "
                    "run 'python authenticate.py' to start the token "
                    "generation process and follow the instructions. Remember "
                    "that you first need to create 'an app' in Splitwise, as "
                    "it's explained in README.md."
                )
                sys.exit()
            except Exception as e:
                spinner.fail(f"😿 Authentication failed with the error: {e}")
                sys.exit()
            spinner.ok("Done! 😻")

        with yaspin(
                Spinners.moon,
                text="Retrieving Splitwise expenses",
                color="blue"
        ) as spinner:
            self.sw.authenticate()
            self.expenses = self.sw.get_expenses()
            if not self.expenses or len(self.expenses) == 0:
                spinner.fail("Couldn't retrieve the expenses 😿")
                sys.exit()
            spinner.ok("Done! 😻")

    def add_report_line(self):
        self.report.append(self.report_line.__list__())

    def print_report(self):
        columns = []
        for field, field_type in ReportLine.__annotations__.items():
            columns.append(field)
        print(tabulate(self.report, columns, tablefmt="fancy_grid"))

    @staticmethod
    def sw_to_bk_amount(amount, negative=False):
        if amount is not float:
            amount = float(amount)
        if negative:
            amount = amount * -1
        return int(amount*100)

    def process_sw_expenses(self):
        for expense in self.expenses:
            self.report_line = ReportLine()
            self.handle_expense(expense)
            self.add_report_line()

    def handle_expense(self, expense):
        # Expense object docs: https://splitwise.readthedocs.io/en/stable/api.html#splitwise.expense.Expense  #noqa
        self.report_line.total_amount = expense.getCost()
        date_sw = expense.getDate()
        date_py = datetime.strptime(date_sw, '%Y-%m-%dT%H:%M:%SZ')
        self.report_line.date = date_py

        paid_by_me, my_expense_user_obj = self.sw.get_my_expense_user_obj(
            expense
        )
        if not my_expense_user_obj:
            raise ValueError(
                "Error: Found an expense without any UserExpense, looks "
                "like Splitwise monkeys blew up something... skipping."
            )

        paid_share = float(my_expense_user_obj.getPaidShare())
        self.report_line.i_paid = float(paid_share)
        owed_share = float(my_expense_user_obj.getOwedShare())
        self.report_line.i_owe = owed_share
        bucket_name = config['SplitwiseCategoriesToBucketNames'].get()[
            expense.getCategory().getId()
        ]
        self.report_line.bucket_name = bucket_name
        bucket_id = self.bk.get_bucket_id(bucket_name)
        self.report_line.name = expense.getDescription()

        if self.bk.transaction_exist(expense.getId()):
            self.report_line.case = "Already exists in Buckets, skipping."
            return

        if expense.getPayment():
            """
            Not an expense but a payment received from another person (or
            that you paid to someone)
            """
            self.report_line.case = "Payment received"
            cost = self.sw_to_bk_amount(expense.getCost())
            # TO DO: how to know if it's positive or negative?
            self.bk.create_expense(
                date=date_py,
                amount=cost,
                memo=expense.getDescription(),
                fi_id=expense.getId(),
                general_cat='income',
                bucket_id=None,
                account='splitwise'
            )
        elif paid_by_me:
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
            self.report_line.case = "Case A (ticket I paid)"

            # Creating T1
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
            self.report_line.case = "Case B (paid by someone else)"

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
            self.report_line.case = (
                "Error: this expense is marked as paid by others but then "
                "your owed share is 0, this should be an Splitwise's API "
                "mistake, check it out.")

    def run(self):
        self.process_sw_expenses()
        self.print_report()


SplitwiseToBucketsSynch().run()
