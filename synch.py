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
    # Expense object docs: https://splitwise.readthedocs.io/en/stable/api.html#splitwise.expense.Expense  #noqa
    date = expense.getDate()
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
        owed_by_others = round(paid_share - owed_share, 2)
        print(f"{expense.getDescription()} paid by me!, {owed_by_others=}")
    elif owed_share > 0:
        """
        CASE B: Ticket that someone else paid, in which I'm included
        Say someone paid 30€ and my share is 5€.
        We need 1 transaction to be registered in Buckets:
        T1: An expense transaction charged at the bks,splitwise_acc account
        by the amount of my share of the expense, at the corresponding Bucket
        according to the Splitwise category of the expense. 

        By now the expense Bucket is not set and needs to be set manually
        after importing them.
        """
        print(f"{expense.getDescription()} paid by someone else!")
    else:
        print("Error: this expense is marked as paid by others but then your "
              "owed share is 0, this should be an Splitwise's API mistake, "
              "check it out.")
        print("Expense dump: " + my_expense_user_obj.__dict__)

    print("")
    # i += 1
    # if i == 2:
    #     break


expense_object_example = {
    'id': 1085155940,
    'group_id': 19188874,
    'description': 'Fruites i verdures',
    'repeats': False,
    'repeat_interval': 'never',
    'email_reminder': True,
    'email_reminder_in_advance': None,
    'next_repeat': None,
    'details': '',
    'comments_count': 0,
    'payment': False,
    'creation_method': 'split',
    'transaction_method': 'offline',
    'transaction_confirmed': False,
    'cost': '30.43',
    'currency_code': 'EUR',
    'created_by': '',
    'date': '2020-09-23T13:30:10Z',
    'created_at': '2020-09-23T13:30:31Z',
    'updated_at': '2020-09-23T13:30:31Z',
    'deleted_at': None,
    'receipt': 'receipt object',
    'category': 'category object',
    'updated_by': None,
    'deleted_by': None,
    'friendship_id': None,
    'expense_bundle_id': None,
    'repayments': ['debt object', 'debt object', 'debt object', ],
    'users': ['expense user object', 'expense user object', ],
    'transaction_id': None
}
