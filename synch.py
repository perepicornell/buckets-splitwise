import settings
from buckets_manager import BucketManager
from splitwise_manager import SplitWiseManager


sw = SplitWiseManager()
bk = BucketManager()

sw.authenticate(settings.SPLITWISE_LAST_VALID_TOKEN)
print(sw.get_current_user())
