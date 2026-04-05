from .base import BasePipeline

class PandasPipeline(BasePipeline):

    def run(self):
        self.logger.info("Running Pandas pipeline")

        df = self.load_data()
        df = self.build_features(df)

        model = self.train(df)

        return model