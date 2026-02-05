import pandas as pd
from fastapi import UploadFile


def parse_csv(file: UploadFile):
    """
    Reads an uploaded CSV file and returns rows as a list of dictionaries.
    No embeddings, no AI yet.
    """
    file.file.seek(0)
    df = pd.read_csv(file.file)

    # Convert DataFrame to list of dicts
    rows = df.to_dict(orient="records")

    return rows
