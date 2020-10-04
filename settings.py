import confuse


class MyConfiguration(confuse.Configuration):
    def config_dir(self):
        return './'


config = MyConfiguration('SplitwiseToBuckets')
