from .base import BasePipeline

class DaskPipeline(BasePipeline):

    def run(self):
        self.logger.info("Running Dask pipeline")

        df = self.load_data()

        df = self.build_features(df)

        self.logger.info("Persisting dataframe")
        df = df.persist()

        model = self.train(df)

        return model