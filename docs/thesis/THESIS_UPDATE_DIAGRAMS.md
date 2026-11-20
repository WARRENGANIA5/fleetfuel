> **Updated 2026-11-20 — the numbers in this file are superseded.** The model was retrained with weighted least squares and residual-outlier removal: 34,111 records (27,288 training / 6,823 testing), R² 0.9008, MAE 1.87 L, RMSE 2.66 L, 5-fold CV R² 0.9002 ± 0.0007, and all five assumption checks met. The current text is `docs/thesis/typst/main.typ` (PDF: `docs/thesis/typst/thesis.pdf`).

# Thesis update: CRISP-DM system diagrams (November 14, 2026)

Text for Chapter III. The study follows CRISP-DM, so the system is shown with four data-science diagrams
instead of the usual DFD, ERD and flowchart. Put each figure where the old diagram was, then paste its paragraph
below it. Number the figures to follow the figures already in the chapter.

| New figure | Replaces | CRISP-DM phases |
|---|---|---|
| Data Pipeline Diagram | Data Flow Diagram (DFD) | Data Understanding, Data Preparation, Modeling |
| Analytical Data Model Schema | Entity Relationship Diagram (ERD) | Data Understanding, Data Preparation |
| ML Lifecycle and Decision Flow | Flowchart | All six phases |
| Inference and Integration Architecture | System architecture | Deployment |

## Files

- Images for Word (3000 px wide): `docs/diagrams/fig1_data_pipeline.png`, `fig2_analytical_data_model.png`,
  `fig3_ml_lifecycle_decision_flow.png`, `fig4_inference_integration_architecture.png`
- All four on long bond with these descriptions: `docs/diagrams/FleetFuel_CRISP-DM_Diagrams.pdf`
- To redraw them after a change in the system: `python docs/diagrams/make_diagrams.py`

## 1. Data Pipeline Diagram

**Figure caption:** Data Pipeline Diagram of the FleetFuel Prediction System

The figure shows the seven stages that turn the collected records into the trained model. The data come from
the GSO trip reports (93 trips), the vehicle records (9 vehicles), the fuel requests of the GSO staff, and two
online datasets (99,898 records). They are stored in Firebase Firestore and in CSV files. The trips are joined
with their vehicles by plate number and merged with the online data. Cleaning removes missing and invalid
values and outliers (IQR rule), and it keeps only the fleet's range: diesel, 30–400 km, and 51–177 kW. This
leaves 34,471 clean records. Four model terms are formed: distance, engine power, fuel type, and distance ×
engine power. The data are split 80/20 with 5-fold cross-validation, and the trained Linear Regression model is
saved with its results (R² = 0.8877).

## 2. Analytical Data Model Schema

**Figure caption:** Analytical Data Model Schema of the FleetFuel Prediction System

The figure shows the data as a star schema. The two fact tables are Fact Trip, with one row per trip and the
measures distance and actual fuel consumption, and Fact Prediction, with one row per fuel request and the
predicted and actual fuel. They are described by the dimension tables Vehicle (plate number, model, fuel type,
engine power), Date, Data Source (local, online trips, or supplementary), and User. A fuel request is linked to
at most one trip. The Model Input View is derived from the trips and vehicles. It holds the predictors X1 to X4
and the target Y used to train the model.

## 3. ML Lifecycle and Decision Flow

**Figure caption:** Machine Learning Lifecycle and Decision Flow (CRISP-DM)

The figure shows the six CRISP-DM phases of the study as a cycle. If the evaluation is not good enough, the work
goes back to an earlier phase. Part A shows how the model is built: the data are prepared and the model is
trained, then it is deployed only if it is accurate and every VIF is at most 5; otherwise the data are revised.
Part B shows how the model is used: a fuel request with valid input is predicted, the administrator approves or
rejects it, and the actual fuel is recorded. When enough new trips have been collected, the model is retrained.

## 4. Inference and Integration Architecture

**Figure caption:** Inference and Integration Architecture of the FleetFuel Prediction System

The figure shows the three tiers of the system. Users work in the web browser (client). The Flask web
application runs on the GSO office server or on the online link (application server). Firebase Firestore, the
CSV datasets, and the trained model form the data and model tier. The numbered steps show one prediction: the
request is sent, the input is checked, the model predicts the fuel, the request and a pending trip are saved,
and the result is shown for approval. A new model is trained in Google Colab, uploaded by the administrator, and
checked before it replaces the current model.
