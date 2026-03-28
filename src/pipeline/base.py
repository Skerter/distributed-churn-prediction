class BasePipeline:
    def __init__(self, config, logger, client=None):
        self.config = config
        self.logger = logger
        self.client = client

    def run(self):
        raise NotImplementedError