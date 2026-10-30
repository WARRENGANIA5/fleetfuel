"""Refresh the Google Colab files in this folder from the web application's data:

* trip_records.csv, vehicle_records.csv, supplementary_data.csv - the same three
  files as Model Performance > Upload Trained Model (app.training_dataset_csv);
* fuel_consumption_linear_regression_AUTO.ipynb - the three files built in;
* both notebooks - the code of model/preprocess.py and model/diagnostics.py.

Run:  python colab/make_colab_files.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)

NAMES = ("trip_records", "vehicle_records", "supplementary_data")
AUTO = os.path.join(HERE, "fuel_consumption_linear_regression_AUTO.ipynb")
UPLOAD = os.path.join(HERE, "fuel_consumption_linear_regression.ipynb")

MERGE_CELL = '''trips = pd.read_csv(TRIPS_PATH)
vehicles = pd.read_csv(VEHICLES_PATH)
local = merge_trips_and_vehicles(trips, vehicles)
# The GSO's own trips are the local trips ("system"); the online-dataset trips of
# Trip Records have their source filled in. The supplementary file holds the other
# online records, so no record is counted twice.
online = local["source"].notna() if "source" in local else False
local["data_source"] = np.where(online, "trip_records_online", "system")
supplementary = pd.read_csv(SUPPLEMENTARY_PATH).assign(data_source="supplementary")
raw = pd.concat([f for f in (local, supplementary) if not f.empty], ignore_index=True)
df = clean_data(raw)
print(f"Records before cleaning: {len(raw)}  after cleaning: {len(df)}")
print(df["data_source"].value_counts().to_string())
df.to_csv("cleaned_merged_dataset.csv", index=False)  # the cleaned and merged dataset (Pandas output)
print("Saved cleaned_merged_dataset.csv")
df.head()'''

MERGE_TEXT = '''## 3. Merge and clean the data
The trips are merged with the vehicle records using the plate number; each record is labeled with its source:
**system** (the GSO's own trips), **trip_records_online** (the online-dataset trips of Trip Records) and
**supplementary** (the other online records).'''

AUTO_DATA_TEXT = '''## 1. Data collection — the datasets (built into this notebook)
This version already contains the data exported from the web application (Model Performance → Upload Trained Model):
**trip_records.csv** ({trips:,} trips of Trip Records: {gso:,} from the GSO's Monthly Reports of Official Travel and
{online:,} online-dataset trips, column `source`), **vehicle_records.csv** ({vehicles} vehicles: plate number, model,
fuel type, engine power) and **supplementary_data.csv** ({supp:,} other online records). The online records are
real-world gasoline trips from Fan & Song, 2022, Mendeley Data, https://doi.org/10.17632/jzjxcdn6k4.2, and
real-world diesel vans from the European Environment Agency, 2024,
https://doi.org/10.2909/13e6fad9-149c-4b86-9d83-cdf3569ccfee (both CC BY 4.0); each one is used once.
The next cell writes the three files, so **Runtime → Run all** trains the model with no file upload.'''

UPLOAD_DATA_TEXT = '''## 1. Data collection — upload the datasets
Download the three files from the web application: **Model Performance → Upload Trained Model from Google Colab →**
**trip_records.csv**, **vehicle_records.csv** and **supplementary_data.csv**, then upload them when the file picker appears.

* **trip_records.csv** — every trip of Trip Records: date of travel, plate number, distance traveled (km) and fuel
  consumed (L); `source` is empty for the GSO's own trips (Monthly Report of Official Travel) and names the online
  dataset for the online-dataset trips.
* **vehicle_records.csv** — plate number, vehicle model, fuel type and engine power (kW).
* **supplementary_data.csv** — the other online records, with the same variables.'''

DW_TEXT = '''## 7. Regression assumption checks (LINE conditions)
Durbin-Watson is computed on the residuals of the GSO's own trips (data_source "system") arranged by date of travel. Coefficient standard errors and p-values are heteroskedasticity-robust (HC3).'''


def lines(text):
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


def set_cell(nb, i, text, kind):
    cell = nb["cells"][i]
    assert cell["cell_type"] == kind, (i, cell["cell_type"])
    cell["source"] = lines(text)
    if kind == "code":
        cell["outputs"], cell["execution_count"] = [], None


def code_file(path):
    with open(os.path.join(BASE, "model", path), encoding="utf-8") as f:
        return f"%%writefile model/{path}\n" + f.read().rstrip("\n")


def main():
    from app import app, training_dataset_csv
    with app.app_context():
        data = {n: training_dataset_csv(n).decode("utf-8") for n in NAMES}
    for n in NAMES:
        with open(os.path.join(HERE, f"{n}.csv"), "w", encoding="utf-8", newline="") as f:
            f.write(data[n])

    import io
    import pandas as pd
    trips = pd.read_csv(io.StringIO(data["trip_records"]))
    counts = {"trips": len(trips), "online": int(trips["source"].notna().sum()),
              "gso": int(trips["source"].isna().sum()),
              "vehicles": len(pd.read_csv(io.StringIO(data["vehicle_records"]))),
              "supp": len(pd.read_csv(io.StringIO(data["supplementary_data"])))}

    for path in (AUTO, UPLOAD):
        with open(path, encoding="utf-8") as f:
            nb = json.load(f)
        set_cell(nb, 7, code_file("preprocess.py"), "code")
        set_cell(nb, 8, code_file("diagnostics.py"), "code")
        set_cell(nb, 10, MERGE_TEXT, "markdown")
        set_cell(nb, 11, MERGE_CELL, "code")
        set_cell(nb, 18, DW_TEXT, "markdown")
        if path == AUTO:
            set_cell(nb, 3, AUTO_DATA_TEXT.format(**counts), "markdown")
            set_cell(nb, 4, "\n".join([
                "# Data exported from the web application. For newer records, download the three CSV files again from",
                "# Model Performance and use fuel_consumption_linear_regression.ipynb (the upload version).",
                'TRIPS_PATH, VEHICLES_PATH, SUPPLEMENTARY_PATH = "trip_records.csv", "vehicle_records.csv", "supplementary_data.csv"',
                f"TRIPS_CSV = {data['trip_records']!r}",
                f"VEHICLES_CSV = {data['vehicle_records']!r}",
                f"SUPPLEMENTARY_CSV = {data['supplementary_data']!r}",
                "for path, text in ((TRIPS_PATH, TRIPS_CSV), (VEHICLES_PATH, VEHICLES_CSV), (SUPPLEMENTARY_PATH, SUPPLEMENTARY_CSV)):",
                '    with open(path, "w", encoding="utf-8") as f:',
                "        f.write(text)",
                'print("Wrote", TRIPS_PATH, VEHICLES_PATH, SUPPLEMENTARY_PATH)']), "code")
        else:
            set_cell(nb, 3, UPLOAD_DATA_TEXT, "markdown")
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                cell["outputs"], cell["execution_count"] = [], None
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
            f.write("\n")
    print("Colab files refreshed:", counts)


if __name__ == "__main__":
    main()
