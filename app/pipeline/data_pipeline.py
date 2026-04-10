import pandas as pd
from typing import Any
import logging

logger = logging.getLogger(__name__)


class DataPipeline:
    def __init__(self):
        self._pipelines: dict[str, Any] = {
            "default": self._default_pipeline,
            "normalize": self._normalize_pipeline,
            "filter": self._filter_pipeline,
        }

    def _default_pipeline(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.dropna()
        return df

    def _normalize_pipeline(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.dropna()
        numeric_cols = df.select_dtypes(include="number").columns
        for col in numeric_cols:
            col_min = df[col].min()
            col_max = df[col].max()
            if col_max != col_min:
                df[col] = (df[col] - col_min) / (col_max - col_min)
        return df

    def _filter_pipeline(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.dropna()
        numeric_cols = df.select_dtypes(include="number").columns
        for col in numeric_cols:
            mean = df[col].mean()
            std = df[col].std()
            if std > 0:
                df = df[abs(df[col] - mean) <= 3 * std]
        return df

    def run(self, data: list[dict[str, Any]], pipeline_name: str = "default") -> dict[str, Any]:
        if pipeline_name not in self._pipelines:
            raise ValueError(f"Pipeline '{pipeline_name}' not found. Available: {list(self._pipelines.keys())}")

        df = pd.DataFrame(data)
        processed_df = self._pipelines[pipeline_name](df)
        processed_records = processed_df.to_dict(orient="records")

        return {
            "processed_data": processed_records,
            "pipeline_name": pipeline_name,
            "records_processed": len(processed_records),
            "status": "success",
        }

    def list_pipelines(self) -> list[str]:
        return list(self._pipelines.keys())


data_pipeline = DataPipeline()
