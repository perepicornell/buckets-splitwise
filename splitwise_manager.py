import webbrowser
from splitwise import Splitwise

import settings


class SplitWiseManager:
    authentication_state = None
    current_user = None

    def __init__(self):
        self.instance = Splitwise(
            settings.SPLITWISE_CONSUMER_KEY,
            settings.SPLITWISE_CONSUMER_SECRET
        )

    def launch_authentication(self):
        url, state = self.instance.getOAuth2AuthorizeURL(
            settings.SPLITWISE_CALLBACK_URL
        )
        self.authentication_state = state
        print(f"putting state into class: {state}")
        webbrowser.open(url, new=2)

    def get_access_token(self, code):
        return self.instance.getOAuth2AccessToken(
            code, settings.SPLITWISE_CALLBACK_URL
        )

    def authenticate(self, access_token):
        self.instance.setOAuth2AccessToken(access_token)
        self.current_user = self.get_current_user()

    def get_current_user(self):
        return self.instance.getCurrentUser()

    def get_expenses(self):
        dated_after = settings.SPLITWISE_EXPENSES_DATED_AFTER
        # updated_after = '2020-08-01'
        return self.instance.getExpenses(
            dated_after=dated_after
        )

    def get_my_expense_user_obj(self, expense):
        """
        :param expense: Expense object
        :return: ExpenseUser obj corresponding to the fraction you paid, if
        there's any
        https://splitwise.readthedocs.io/en/stable/api.html#splitwise.user.ExpenseUser  #noqa
        """
        paid_by_me = False
        users = expense.getUsers()
        for expense_user_obj in users:
            if expense_user_obj.getId() == self.current_user.getId():
                if expense_user_obj.getPaidShare() != '0.0':
                    paid_by_me = True
                return paid_by_me, expense_user_obj
        return None, None
