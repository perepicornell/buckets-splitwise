"""
La part de detectar si existeixen o no les transaccions per fer correctament
l'update o l'insert sembla ser que ja funciona.

NEXT:

No està categoritzant les transaccions, cal revisar com fer-ho en el nou
sistema, pel tema que ara pot fer un update si han canviat la categoria
però l'update només s'ha de fer si la nova no és empty i coincideix amb
una de les que tinguem configurades al settings.

"""

import sys
import textwrap
import traceback
from decimal import Decimal, getcontext
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
    total_amount: Decimal = 0.0
    i_paid: Decimal = 0.0
    i_owe: Decimal = 0.0
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
    total_amount: Decimal
    i_paid: Decimal
    i_owe: Decimal
    case: str
    bucket_name: str
    bucket_id: int
    owed_by_others: Decimal
    is_cash: bool
    is_payment: bool


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
                if config['debug'].get() is True:
                    traceback.print_exc()
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
        obj['total_amount'] = Decimal(expense.getCost())
        obj['i_paid'] = Decimal(my_expense_user_obj.getPaidShare())
        obj['i_owe'] = Decimal(my_expense_user_obj.getOwedShare())
        obj['owed_by_others'] = self.sw.get_owed_by_others(expense)
        obj['is_cash'] = self.sw.is_cash(expense)
        obj['is_payment'] = True if expense.getPayment() else False
        obj['bucket_name'] = config['SplitwiseCategoriesToBucketNames'].get()[
            expense.getCategory().getId()
        ]
        # TO DO: put all buckets in a dict to make it 1 query
        obj['bucket_id'] = self.bk.get_bucket_id(obj['bucket_name'])

        obj['case'] = 'deprecated'

        return Expense(**obj)

    def handle_expense(self, exp_obj):
        """
        The "4 transactions approach" explained:

        Combining every possible situation in Splitwise, for each SW expense
        there's a maximum of 4 transasctions that could happen in buckets.

        The BucketManager driver is made in a way that if you try to do a 0€
        amount transaction it will be ignored if it's the first time importing
        it, but if it detects that we already have it registered, then it will
        update the existing transactions and therefore turn them into 0€ ones.

        This system also solves:
        If after having changed, the expense needs a different combination
        of transactions.
        - If it needs less transactions than existing, we'll be passing all the
        rest anyway with 0€, so they will be updated.
          Example: It was a 1€ expense from payment + 24€ transfer to
          splitwise account, but now it should be only 1 expense of 25€
          to any of the accounts.
        - If it needs more transactions than existing, now it will include the
        amounts of the new transactions, therefore they will be created.
          Example: it was 1 transfer and now it should be 1 transfer
          + 1 expense from any of the accounts.

        With this system if an expense is modified in Splitwise in so many ways
        that goes through all the possible states, you might end up with a
        transaction for the right amount and 3 other transactions for 0€.
        At least that will give you a clue of what was going on but, more
        importantly, in order to fix this you should remember to cancel your
        friendship with whoever is messing it up with Splitwise so much.

        But more practically, just delete the 0€ Buckets' transactions after
        you verify that the expense details are finally correct in Splitwise.
        """
        payment_expense_details = {
            'date': exp_obj.date,
            'amount': 0.00,
            'memo': exp_obj.name,
            'fi_id': exp_obj.id,
            'general_cat': None,
            'bucket_id': exp_obj.bucket_id,
            'account': 'cash' if exp_obj.is_cash else 'payment'
        }

        splitwise_expense_details = {
            'date': exp_obj.date,
            'amount': 0.00,
            'memo': exp_obj.name,
            'fi_id': exp_obj.id,
            'general_cat': None,
            'bucket_id': exp_obj.bucket_id,
            'account': 'splitwise'
        }

        transfer_to_splitwise = {
            'date': exp_obj.date,
            'amount': 0.00,
            'memo': exp_obj.name,
            'fi_id': exp_obj.id,
            'from_account': 'cash' if exp_obj.is_cash else 'payment',
            'to_account': 'splitwise'
        }

        if exp_obj.is_payment:
            """
            In the incoming transfers you got paid some money, so your
            Splitwise balance is decreased (in Splitwise app) and therefore
            in Buckets a transfer is made from your splitwise account into
            the account you got the payment.
            
            That case is treated separately to make sure that only this
            transaction is executed in that case.
            
            That's because if two create_or_update_transfers are executed,
            we cannot apply the system of sending 0€ transactions even if we
            don't need them, because for transfers the 0€ ones are processed
            and updated.
            Therefore: in multiple create_or_update_transfers, the last one
            will override the prior.
            """
            transfer_from_splitwise = {
                'date': exp_obj.date,
                'amount': exp_obj.total_amount,
                'memo': exp_obj.name,
                'fi_id': exp_obj.id,
                'from_account': 'splitwise',
                # If you're getting money in cash, put in the right account:
                'to_account': 'cash' if exp_obj.is_cash else 'payment'
            }
            self.bk.create_or_update_transfer(**transfer_from_splitwise)
        else:
            if exp_obj.i_paid < exp_obj.i_owe:
                """
                Say..
                I paid: 1€              I owe: 25€
                Paid by other: 49€      Owed by other: 25€
                
                Means 1 expense is the 1€ from payments account,
                and another expense is 24€ from splitwise account.

                But if...
                I paid: 0€              I owe: 25€
                Paid by other: 50€      Owed by other: 25€
                
                There's only one expense of 24€ from splitwise account.
                Nonetheless we don't know if that's an expense already
                existing in Buckets (previously marked as I paid something) and
                now it's modified. To handle that situation we need the 0€
                expense to be passed to BucketManager, so it will detect that
                it's an update and set the existing payments account expense
                to 0€.
                Not super elegant to end up with a 0€ transaction in Buckets,
                but it's the most informative and less problematic option I
                came up with.
                """
                payment_amount = exp_obj.i_paid * -1
                payment_expense_details['amount'] = payment_amount
                splitwise_amount = exp_obj.i_owe - exp_obj.i_paid
                splitwise_expense_details['amount'] = splitwise_amount

            if exp_obj.i_paid == exp_obj.i_owe:
                """
                Say..
                I paid: 25€             I owe: 25€
                Paid by other: 25€      Owed by other: 25€
    
                Means only 1 expense of 25€ from payments account.
                
                """
                payment_expense_details['amount'] = exp_obj.i_paid * -1
            if exp_obj.i_paid > exp_obj.i_owe:
                """
                Say..
                I paid: 49€             I owe: 25€
                Paid by other: 1€       Owed by other: 25€

                Means:
                - One 25€ expense from payments account,
                - A transfer from payments account to splitwise account
                  for 24€.

                Say..
                I paid: 13€             I owe: 0€
                Paid by other: 0€       Owed by other: 13€

                Means:
                - A transfer from payments acc to splitwise acc. for 13€
                So we can leave the payment_expense_details bc it's going to
                be 0€ and not do anything anyway.
                """
                payment_amount = exp_obj.i_owe * -1
                payment_expense_details['amount'] = payment_amount
                transfer_amount = exp_obj.i_paid - exp_obj.i_owe
                transfer_to_splitwise['amount'] = transfer_amount

            print(f"Starting {transfer_to_splitwise=}")
            self.bk.create_or_update_transfer(**transfer_to_splitwise)
            print(f"Starting {payment_expense_details=}")
            self.bk.create_or_update_expense(**payment_expense_details)
            print(f"Starting {splitwise_expense_details=}")
            self.bk.create_or_update_expense(**splitwise_expense_details)

    def run(self):
        self.process_sw_expenses()
        self.print_report()


SplitwiseToBucketsSynch().run()
