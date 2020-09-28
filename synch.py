from datetime import datetime

import settings
from buckets_manager import BucketManager
from splitwise_manager import SplitWiseManager


"""
Reference for the comments in the code:
bks.default_acc means BUCKETS_PAYMENTS_ACCOUNT
bks.splitwise_acc means BUCKETS_SPLITWISE_ACCOUNT_NAME
"""

sw = SplitWiseManager()
bk = BucketManager()

sw.authenticate(settings.SPLITWISE_LAST_VALID_TOKEN)

expenses = sw.get_expenses()
current_user = sw.get_current_user()

i = 0
for expense in expenses:
    # Debugging in process:
    # i += 1
    # print(expense.getDescription())
    # print(expense.getDate())
    # if expense.getDescription() == "Pa i Snickers":
    #     print(expense.__dict__)
    # print(f"total: {i}")
    # continue

    # Expense object docs: https://splitwise.readthedocs.io/en/stable/api.html#splitwise.expense.Expense  #noqa
    date_sw = expense.getDate()
    date_py = datetime.strptime(date_sw, '%Y-%m-%dT%H:%M:%SZ')
    users = expense.getUsers()
    paid_by_me, my_expense_user_obj = sw.get_my_expense_user_obj(expense)
    if not my_expense_user_obj:
        print("Error: Found an expense without any UserExpense, looks like "
              "Splitwise monkeys blew up something... skipping.")
        continue
    paid_share = float(my_expense_user_obj.getPaidShare())
    owed_share = float(my_expense_user_obj.getOwedShare())
    print(f"paid share: {my_expense_user_obj.getPaidShare()}, owed share: {owed_share}")
    if paid_by_me:
        """
        CASE A: Ticket that I paid
        Say I paid 50€ of which my share is 10€.
        We need to register 2 transactions in Buckets:
        T1: An expense transaction for my share of the expense, charged on
        bks.default_acc at the corresponding Bucket.
        T2: A TRANSFER transaction from bks.default_acc to bks.splitwise_acc 
        for the rest of the quantity that I paid.
        
        By now the expense Bucket is not set and needs to be set manually
        after importing them.
        """

        # Creating T1
        if bk.transaction_exist(expense.getId()):
            print(f"{expense.getId()=} already exists in Buckets, skipping.")
            continue
        bk.create_transaction(
            date=date_py,
            account_id=bk.payments_account_id,
            amount=bk.to_buckets_amount(owed_share, True),
            memo=expense.getDescription(),
            fi_id=expense.getId(),
            general_cat=None
        )

        # Creating T2
        owed_by_others = round(paid_share - owed_share, 2)
        bk.create_transaction(
            date=date_py,
            account_id=bk.payments_account_id,
            amount=bk.to_buckets_amount(owed_by_others, True),
            memo=expense.getDescription(),
            fi_id=expense.getId(),
            general_cat='transfer'
        )
        bk.create_transaction(
            date=date_py,
            account_id=bk.splitwise_account_id,
            amount=bk.to_buckets_amount(owed_by_others),
            memo=expense.getDescription(),
            fi_id=expense.getId(),
            general_cat='transfer'
        )

        print(f"{expense.getDescription()} paid by me!, {owed_by_others=}")
    elif owed_share > 0:
        """
        CASE B: Ticket that someone else paid, in which I'm included
        Say someone paid 30€ and my share is 5€.
        We need 1 transaction to be registered in Buckets:
        T1: An expense transaction charged at the bks.splitwise_acc account
        by the amount of my share of the expense, at the corresponding Bucket
        according to the Splitwise category of the expense. 

        By now the expense Bucket is not set and needs to be set manually
        after importing them.
        """
        if bk.transaction_exist(expense.getId()):
            print(f"{expense.getId()=} already exists in Buckets, skipping.")
            continue
        bk.create_transaction(
            date=date_py,
            account_id=bk.splitwise_account_id,
            amount=bk.to_buckets_amount(owed_share, True),
            memo=expense.getDescription(),
            fi_id=expense.getId(),
            general_cat=None
        )
        print(f"{expense.getDescription()} paid by someone else!")
    else:
        print("Error: this expense is marked as paid by others but then your "
              "owed share is 0, this should be an Splitwise's API mistake, "
              "check it out.")
        print("Expense dump: " + my_expense_user_obj.__dict__)

    print("")
