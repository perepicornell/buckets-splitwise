import webbrowser
from splitwise import Splitwise

import settings


class SplitWiseManager:
    def __init__(self):
        self.instance = Splitwise(
            settings.SPLITWISE_CONSUMER_KEY,
            settings.SPLITWISE_CONSUMER_SECRET
        )

    def launch_authentication(self):
        url, state = self.instance.getOAuth2AuthorizeURL(
            settings.SPLITWISE_CALLBACK_URL
        )
        print(f"state: {state}")
        print(f"url: {url}")
        webbrowser.open(url, new=2)

    def get_access_token(self, code):
        return self.instance.getOAuth2AccessToken(
            code, settings.SPLITWISE_CALLBACK_URL
        )

    def authenticate(self, access_token):
        self.instance.setOAuth2AccessToken(access_token)

    def get_current_user(self):
        return self.instance.getCurrentUser()
