import webbrowser
from datetime import datetime, timedelta
from splitwise import Splitwise

from settings import config

config = config['Splitwise']


class SplitWiseManager:
    authentication_state = None
    current_user = None

    def __init__(self):
        self.instance = Splitwise(
            config['ConsumerKey'].get(),
            config['ConsumerSecret'].get()
        )

    def launch_authentication(self):
        url, state = self.instance.getOAuth2AuthorizeURL(
            config['CallbackUrl'].get()
        )
        self.authentication_state = state
        print(f"putting state into class: {state}")
        webbrowser.open(url, new=2)

    def get_access_token(self, code):
        return self.instance.getOAuth2AccessToken(
            code, config['CallbackUrl'].get()
        )

    def authenticate(self, access_token=None):
        if not access_token:
            access_token = config['LastValidToken'].get()
        self.instance.setOAuth2AccessToken(access_token)
        self.current_user = self.get_current_user()

    def get_current_user(self):
        return self.instance.getCurrentUser()

    def get_expenses(self):
        # Adding 1 because the API call filter skips the day itself
        days_ago = config['ExpensesDaysAgo'].get() + 1
        days_ago_date = datetime.now() - timedelta(days_ago)
        max_dated_after = config['ExpensesDatedAfter'].get()
        max_dated_after_py = datetime.strptime(max_dated_after, '%Y-%m-%d')
        dated_after = days_ago_date
        if days_ago_date < max_dated_after_py:
            dated_after = max_dated_after_py

        expenses = self.instance.getExpenses(
            dated_after=dated_after,
            limit=config['ExpensesLimit'].get()
            # updated_after = '2020-08-01'
        )

        print(f"\n{len(expenses)} imported expenses from Splitwise\n")
        if len(expenses) == config['ExpensesLimit'].get():
            print(
                "You might be hitting the SPLITWISE_EXPENSES_LIMIT, increase "
                "it or reduce the SPLITWISE_EXPENSES_DAYS_AGO to make sure "
                "you're importing all the expenses in your desired range.")

        return expenses

    def get_expense_comments(self, expense_id):
        return self.instance.getComments(expense_id)

    def expense_has_keyword(self, expense, keyword):
        if expense.getDetails() == keyword:
            return True
        if expense.getCommentsCount() > 0:
            comments = self.get_expense_comments(expense.getId())
            for comment in comments:
                user = comment.getCommentedUser()
                content = comment.getContent()
                if (
                    user.getId() == self.current_user.getId()
                    and content == keyword
                ):
                    return True
        return False

    def is_cash(self, expense):
        return self.expense_has_keyword(
            expense, config['ExpensesCashKeyword'].get()
        )

    def expense_is_ignored(self, expense):
        return self.expense_has_keyword(
            expense, config['ExpensesIgnoreKeyword'].get()
        )

    def get_my_expense_user_obj(self, expense):
        """
        :param expense: Expense object
        :return: ExpenseUser obj corresponding to the fraction you paid, if
        there's any
        https://splitwise.readthedocs.io/en/stable/api.html#splitwise.user.ExpenseUser  #noqa
        """
        users = expense.getUsers()
        for expense_user_obj in users:
            if expense_user_obj.getId() == self.current_user.getId():
                return expense_user_obj
        return None

    def get_owed_by_others(self, expense):
        """
        To avoid problems with decimal rounding, we sum the actual owed amount
        of each involved user in the expense.

        :param expense: Expense object
        :return: Sum of the amounts owed by others
        https://splitwise.readthedocs.io/en/stable/api.html#splitwise.user.ExpenseUser  #noqa
        """
        total = 0.0
        users = expense.getUsers()
        for expense_user_obj in users:
            if expense_user_obj.getId() != self.current_user.getId():
                total += float(expense_user_obj.getOwedShare())
        return total

    def print_categories_dict(self):
        categories = self.instance.getCategories()
        for category in categories:
            print(f"{category.getId()}: '',  # {category.getName()}")
            for subcategory in category.subcategories:
                print(f"{subcategory.getId()}: '',"
                      f"  # {subcategory.getName()}")
