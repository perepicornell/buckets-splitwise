import sys
import textwrap
from datetime import datetime, timezone
from dataclasses import dataclass, astuple

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
    debug: str = ''

    def __setattr__(self, key, value):
        value = str(value)
        value_lines = textwrap.wrap(value, 30)
        value = "\n".join(value_lines)
        super().__setattr__(key, value)


@dataclass
class Expense:
    id: int
    name: str
    date: str
    total_amount: float
    i_paid: float
    i_owe: float
    case: str
    bucket_name: str
    bucket_id: int
    already_exists: bool
    existing_transactions: list
    owed_by_others: float
    is_cash: bool


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
        self.report.append(astuple(self.report_line))

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
        return int(round(amount * 100))

    def process_sw_expenses(self):
        for expense in self.expenses:
            exp_obj = self.get_expense_obj(expense)
            self.report_line = ReportLine()
            self.report_line.total_amount = exp_obj.total_amount
            self.report_line.date = exp_obj.date
            self.report_line.i_paid = exp_obj.i_paid
            self.report_line.i_owe = exp_obj.i_owe
            self.report_line.bucket_name = exp_obj.bucket_name
            self.report_line.name = exp_obj.name

            try:
                self.handle_expense(exp_obj)
            except Exception as e:
                self.report_line.debug = e
            self.add_report_line()

    def get_expense_obj(self, expense):
        # expense is this object: https://splitwise.readthedocs.io/en/stable/api.html#splitwise.expense.Expense  #noqa
        obj = {}

        date_sw = expense.getDate()
        date_py_utc = datetime.strptime(date_sw, '%Y-%m-%dT%H:%M:%SZ')
        # SW sends the dates in UTC. Converting to local time.
        obj['date'] = date_py_utc.replace(
            tzinfo=timezone.utc
        ).astimezone(tz=None)

        my_expense_user_obj = self.sw.get_my_expense_user_obj(
            expense
        )
        if not my_expense_user_obj:
            raise ValueError(
                "Error: Found an expense without any UserExpense, looks "
                "like Splitwise monkeys blew up something... skipping."
            )

        obj['id'] = expense.getId()
        obj['name'] = expense.getDescription()
        obj['total_amount'] = self.sw_to_bk_amount(expense.getCost())
        obj['i_paid'] = float(my_expense_user_obj.getPaidShare())
        obj['i_owe'] = float(my_expense_user_obj.getOwedShare())
        obj['owed_by_others'] = self.sw.get_owed_by_others(expense)
        obj['is_cash'] = self.sw.is_cash(expense)
        obj['bucket_name'] = config['SplitwiseCategoriesToBucketNames'].get()[
            expense.getCategory().getId()
        ]
        obj['bucket_id'] = self.bk.get_bucket_id(obj['bucket_name'])
        obj['existing_transactions'] = self.bk.get_transactions_by_fi_id(
            expense.getId()
        )
        obj['already_exists'] = False
        if len(obj['existing_transactions']) > 0:
            obj['already_exists'] = True

        if expense.getPayment():
            obj['case'] = 'payment_received'
        elif obj['i_paid']:
            obj['case'] = 'i_paid_something'
        elif obj['i_owe']:
            obj['case'] = 'i_owe_something'

        return Expense(**obj)

    def handle_expense(self, exp_obj):

        if exp_obj.case == 'payment_received':
            """
            Not an expense but a payment received from another person (or
            that you paid to someone).
            """
            self.report_line.case = "Payment"
            # TO DO: how to know if it's positive or negative?
            if exp_obj.already_exists:
                try:
                    self.bk.update_transfer(
                        existing_transactions=exp_obj.existing_transactions,
                        date=exp_obj.date,
                        amount=exp_obj.total_amount,
                        memo=exp_obj.name,
                        from_account='splitwise',
                        to_account='payment'
                    )
                except Exception as e:
                    self.report_line.debug = e
            else:
                self.bk.create_transfer(
                    date=exp_obj.date,
                    amount=exp_obj.total_amount,
                    memo=exp_obj.name,
                    fi_id=exp_obj.id,
                    from_account='splitwise',
                    to_account='payment'
                )
        elif exp_obj.case == 'i_paid_something':
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
            self.report_line.case = "I paid"
            account = 'payment'
            if exp_obj.is_cash:
                account = 'cash'

            if exp_obj.already_exists:
                try:
                    # Updating 1st transaction (normal expense)
                    self.bk.update_expense(
                        existing_transactions=exp_obj.existing_transactions,
                        date=exp_obj.date,
                        amount=self.sw_to_bk_amount(exp_obj.i_owe, True),
                        memo=exp_obj.name,
                        general_cat=None,
                        bucket_id=exp_obj.bucket_id,
                        account=account
                    )

                    # Updating 2nd transaction (a transfer)
                    self.bk.update_transfer(
                        existing_transactions=exp_obj.existing_transactions,
                        date=exp_obj.date,
                        amount=self.sw_to_bk_amount(exp_obj.owed_by_others),
                        memo=exp_obj.name,
                        from_account=account,
                        to_account='splitwise'
                    )
                except Exception as e:
                    self.report_line.debug = e

            else:
                # Creating T1
                self.bk.create_expense(
                    date=exp_obj.date,
                    amount=self.sw_to_bk_amount(exp_obj.i_owe, True),
                    memo=exp_obj.name,
                    fi_id=exp_obj.id,
                    general_cat=None,
                    bucket_id=exp_obj.bucket_id,
                    account=account
                )

                # Creating T2
                self.bk.create_transfer(
                    date=exp_obj.date,
                    amount=self.sw_to_bk_amount(exp_obj.owed_by_others),
                    memo=exp_obj.name,
                    fi_id=exp_obj.id,
                    from_account=account,
                    to_account='splitwise'
                )

        elif exp_obj.case == 'i_owe_something':
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
            self.report_line.case = "They paid"

            if exp_obj.already_exists:
                self.bk.update_expense(
                    existing_transactions=exp_obj.existing_transactions,
                    date=exp_obj.date,
                    amount=self.sw_to_bk_amount(exp_obj.i_owe, True),
                    memo=exp_obj.name,
                    general_cat=None,
                    bucket_id=exp_obj.bucket_id,
                    account='splitwise'
                )
            else:
                self.bk.create_expense(
                    date=exp_obj.date,
                    amount=self.sw_to_bk_amount(exp_obj.i_owe, True),
                    memo=exp_obj.name,
                    fi_id=exp_obj.id,
                    general_cat=None,
                    bucket_id=exp_obj.bucket_id,
                    account='splitwise'
                )
        else:
            self.report_line.debug = (
                "Error: this expense is marked as paid by others but then "
                "your owed share is 0, this should be an Splitwise's API "
                "mistake, check it out.")

    def run(self):
        self.process_sw_expenses()
        self.print_report()


SplitwiseToBucketsSynch().run()
