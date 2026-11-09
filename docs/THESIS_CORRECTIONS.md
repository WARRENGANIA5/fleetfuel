# Manuscript corrections — match the papers to the system (November 9, 2026)

Checked against `Fuel Consumption Prediction (5).pdf`. Page numbers are the printed ones. The system is the
reference: each change below makes the manuscript describe what the system does. Figures come from
`model/metrics.json` (model v20261030104247).

## A. Method: text that differs from the system

**1. p.22–23, IQR grouping.** Replace "Engine power is first grouped into ranges, and the method is applied to the
fuel used per 100 kilometers for each range, so large vehicles are compared only with vehicles of similar size."
with:

> The records are first grouped by engine power, and the method is applied to the fuel used per 100 kilometers
> within each group of vehicles with the same engine power, so large vehicles are compared only with vehicles of
> the same size.

**2. p.23, correlation.** Replace "the researchers analyze the training set for correlations among the variables."
with:

> the researchers analyze the cleaned and merged dataset for correlations among the variables, with distance and
> engine power centered on the training means.

**3. p.23, VIF.** Replace "the Variance Inflation Factor (VIF) is calculated for each predictor." with:

> the Variance Inflation Factor (VIF) is calculated for each predictor on the cleaned and merged dataset.

**4. p.24, after the Breusch-Pagan sentence.** Add:

> The Ramsey RESET test checks linearity and the Jarque-Bera test and a Q-Q plot check normality, where a p-value
> above 0.05 meets the assumption. Since the equal-variance assumption is not met, the coefficient standard errors
> and p-values are heteroskedasticity-robust (HC3).

**5. p.24, Durbin-Watson.** Replace "tests the residuals of the local trips in the training set, arranged according
to the date of travel" with:

> tests the residuals of all 93 local trips, arranged according to the date of travel

**6. p.25, metrics.** Replace "The metrics are computed for the full testing set and again for the local trips
alone, since the local trips reflect the performance of the model on the university fleet." with:

> The metrics are computed for the full testing set.

**7. p.25, last paragraph.** Replace "The staff compare this figure with the fuel request before approval, and each
prediction is stored in the prediction history of the system." with:

> Each prediction is stored in the prediction history of the system and submitted as a fuel request. The
> administrator compares the predicted figure with the request, then approves it with the liters to release or
> rejects it.

## B. Data

**8. p.22, "[name of online source]".** Replace "is taken from [name of online source]." with:

> is taken from two open datasets licensed under CC BY 4.0: 50,508 real-world gasoline trips from Fan and Song
> [42], and 49,390 diesel vans from the European Environment Agency [43], whose distance and fuel consumed are
> lifetime totals read from each van's on-board fuel consumption meter.

**9. p.22, after "...to identify the local trips after merging."** Add:

> When the model was trained, the Trip Records module of the system listed 7,589 trips: the 93 local trips and 7,496 of the European Environment
> Agency records. For these 7,496 records the distance and fuel consumed are the recorded values, while the fleet
> vehicle, with an engine power within 10 kW of the source van, and the date of travel were assigned by a fixed
> procedure. They are not actual trips of the university fleet. Each online record is used only once, giving 99,991
> records before cleaning: 93 local trips, 7,496 online records in Trip Records, and 92,402 other online records.

**10. p.5, Limitations.** Replace "Only vehicles with available records in the Monthly Report of Official Travel are
included, so predictions for other vehicles in the fleet are not validated." with:

> The Monthly Report of Official Travel records gathered cover one vehicle, SFA 4714, from January to June 2026. All
> nine fleet vehicles can be selected in the system, but predictions for vehicles without trip records are not
> validated against their own trips, and the system displays a warning for them.

**11. p.5, Limitations, after "...encoding errors."** Add:

> The fuel consumed in the 93 local records follows an allocation rule of one liter per 10 kilometers. It is not a
> measured value.

**12. p.7, Fuel Consumption, second paragraph.** Replace the first sentence with:

> In this study, this term refers to the total liters of fuel per official trip of a government vehicle, as recorded
> in the Monthly Report of Official Travel, where the figure follows an allocation of one liter per 10 kilometers.

## C. Scope and technologies: what the system has that the papers omit

**13. p.5, Scope, at the end.** Add:

> The system also includes user sign-up with administrator approval, role-based user accounts, vehicle and trip
> record management, fuel request review by the administrator, recording of the actual fuel consumed,
> notifications, and a Model Performance page where the model trained in Google Colab is uploaded. Each fuel request
> adds a pending trip to the trip records, which is used in training only after its actual fuel is recorded. The
> system is deployed online at https://gsu-fleetfuel.vercel.app.

**14. p.5, Limitations.** Replace "The predicted fuel figure serves as a reference only and does not approve or
reject fuel requests." with:

> The predicted fuel figure serves as a reference only. It does not approve or reject fuel requests; the
> administrator makes that decision in the system.

**15. p.5, last sentence.** Replace with:

> The output is a web application only, with no mobile application, and it requires an internet connection since
> the vehicle records and prediction history are stored in Firebase Firestore.

**16. p.20, Firebase Firestore, second paragraph.** Replace with:

> Firebase Firestore stores the vehicle records, including the engine power and fuel type of each vehicle, the local
> trip records, the user accounts, and the prediction history of the web application.

**17. p.20–22, technologies.** Add in alphabetical order:

> **Bootstrap** - a front-end toolkit of responsive layouts and interface components [40]. Bootstrap is used for the
> layout, forms, and tables of the web application.
>
> **Chart.js** - a JavaScript library for drawing charts on web pages [41]. Chart.js draws the charts of the
> Model Performance page.

## D. Errors in the manuscript

| Page | Change |
|---|---|
| i | "Guimbards State University" → "Guimaras State University" |
| ii | Keywords → Linear Regression, Fuel Consumption Prediction, Government Fleet, Machine Learning, Web Application |
| 3 | Replace Figure 1 (it shows GSU.Go) using the content in section E |
| 7 | "Govenrment Fleets" → "Government Fleets" |
| 16 | Replace "guiding the selection of trip duration, passenger or cargo load, and route and road type as independent variables in this study." with "although these variables are absent from the Monthly Report of Official Travel, so this study relies on distance traveled, engine power, fuel type, and their interaction." |
| 26 | "to help the help the" → "to help the" |
| 29, 34 | "Interference and Integration Architecture" → "Inference and Integration Architecture" |
| 29, 36 | Use one name for T18: "System Implementation and Documentation" |

**References to add after [27]:**

- [28] "Firestore | Firebase." [Online]. Available: https://firebase.google.com/docs/firestore
- [29] "Flask." [Online]. Available: https://flask.palletsprojects.com/
- [30] "Google Colab." [Online]. Available: https://colab.research.google.com/
- [31] "HTML: HyperText Markup Language." [Online]. Available: https://developer.mozilla.org/en-US/docs/Web/HTML
- [32] "JavaScript." [Online]. Available: https://developer.mozilla.org/en-US/docs/Web/JavaScript
- [33] "Joblib." [Online]. Available: https://joblib.readthedocs.io/
- [34] "Matplotlib." [Online]. Available: https://matplotlib.org/
- [35] "NumPy." [Online]. Available: https://numpy.org/
- [36] "pandas." [Online]. Available: https://pandas.pydata.org/
- [37] "Python." [Online]. Available: https://www.python.org/
- [38] "seaborn." [Online]. Available: https://seaborn.pydata.org/
- [39] "Visual Studio Code." [Online]. Available: https://code.visualstudio.com/
- [40] "Bootstrap." [Online]. Available: https://getbootstrap.com/
- [41] "Chart.js." [Online]. Available: https://www.chartjs.org/
- [42] P. Fan and G. Song, "Which factor contributes more to the fuel consumption gap between in-laboratory vs. real-world driving conditions? An independent component analysis" (Version 2), Mendeley Data, 2022, doi: 10.17632/jzjxcdn6k4.2.
- [43] European Environment Agency, "2024 real-world CO2 emissions from cars and vans," 2025, doi: 10.2909/13e6fad9-149c-4b86-9d83-cdf3569ccfee.

## E. Figure 1 content (p.3)

| Input | Process | Output |
|---|---|---|
| Monthly Report of Official Travel (date of travel, distance traveled, fuel consumed) | **Data Preparation:** merge by plate number, combine with the supplementary dataset, remove missing values and zero distance, IQR outlier removal, fuel type encoding, interaction term | Trained Linear Regression model with its R², MAE, and RMSE results |
| Vehicle records (plate number, vehicle model, fuel type, engine power) | **Model Development:** correlation and VIF checks, 80/20 split, model training | Web application that returns a predicted fuel figure in liters |
| Supplementary dataset (distance traveled, engine power, fuel type, fuel consumed) | **Model Evaluation:** residual plots, residual histogram, Durbin-Watson, R², MAE, RMSE, 5-fold cross-validation | |
| | **System Development:** web application design, model integration, implementation | |

## F. Text still to be written

| Part | Source |
|---|---|
| Abstract | Draft below |
| Chapter IV, T7–T16 and T17 results | `docs/THESIS_CHAPTER_IV.md` |
| Chapter V | `docs/THESIS_CHAPTER_V.md` |
| [CODE] placeholders (14) | `docs/THESIS_CHAPTER_III_CODE.md` |
| Project Description name and logo | `docs/THESIS_UPDATE_LOGO.md` |
| T2–T6 (planning, title defense, user requirements) | Only the team has these details |
| Month YYYY, approval date, adviser's date | Only the team has these details |

**Draft abstract:**

> Fuel requests for the government fleet of Guimaras State University are reviewed from experience and past records,
> and excessive use is found only during liquidation. This study developed and evaluated a Linear Regression model
> that predicts the fuel consumed per trip from distance traveled, engine power, fuel type, and the interaction of
> distance and engine power, then integrated it into a web application. The data combined 93 trips from the Monthly
> Report of Official Travel, the records of nine fleet vehicles, and open online datasets, leaving 96,134 records
> after cleaning and outlier removal. Under an 80/20 train-test split, the model reached an R-squared of 0.9502, a
> Mean Absolute Error of 2.51 liters, and a Root Mean Squared Error of 4.84 liters. Five-fold cross-validation gave a
> mean R-squared of 0.951 with a standard deviation of 0.0008. All Variance Inflation Factors were below 5, while the
> linearity, independence, normality, and equal-variance checks were not met, so the estimates are read as an
> approximation. The local fuel figures follow an allocation rule and only one vehicle has local records, which limits
> validation on the other vehicles. The web application lets staff select a vehicle and enter the trip distance to
> receive a predicted fuel figure that serves as a reference when fuel requests are reviewed.

## G. Second pass

| Page | Change |
|---|---|
| ii | "ERANDIO, A. A.." → "ERANDIO, A. R. A." |
| 5 | Replace "The report records only the distance traveled and the fuel consumed per trip." with "Of the variables used in this study, the report provides only the date of travel, the distance traveled, and the fuel consumed per trip." |
| 8 | Replace "and inflates their variable. This leads to variance in the estimates" with "and inflates their variance" |
| 8 | Replace "since diesel and gasoline engines in the fleet and the supplementary dataset differ in typical power ranges" with "since the diesel and gasoline engines in the merged dataset differ in typical power ranges" (every fleet vehicle is diesel) |
| 18 | [21], relevance paragraph: delete "shows manually reported records support fuel prediction and" and the last sentence on manual records; the text was copied from [20], and p.13 does not describe [21] as manual records |
| 21 | "It used to style" → "It is used to style" |
| 21–22 | Put Seaborn before Statsmodels (the list is alphabetical) |
| 22 | Replace "Where the supplementary dataset records fuel use in liters per 100 kilometers, the values are converted into total liters per trip by multiplying the rate by the distance traveled and dividing by 100, so both sources share the same unit." with "Both online datasets record fuel consumed in liters, the same unit as the local records, and the distances of the Fan and Song dataset are converted from meters to kilometers." |
| 22 | Replace "The datasets are stored in CSV files." with "The trip and vehicle records are stored in Firebase Firestore and exported as CSV files for training, together with the supplementary dataset." |
| 20 | Google Colab, second paragraph: replace with "The Google Colab notebook of the study holds the data cleaning, encoding, merging, model training, and evaluation of the Linear Regression model. The model in the system was produced by running this notebook on the researchers' computer." |

## H. Third pass (checked line by line against the system)

| Page | Change |
|---|---|
| 2 | "By providing accurate per trip fuel estimates" → "By providing per trip fuel estimates" |
| 3 | Model Development: 80/20 split first, then correlation and VIF, then training |
| 4 | "The staff use this figure" → "The administrator uses this figure" |
| 6 | General Services Offices: "staff select a vehicle, enter the trip distance" |
| 9, 16, 17, 21–22 | No variable selection happens in the system: reword to data cleaning, outlier removal and correlation analysis |
| 21–22 | Chart.js: Dashboard and Model Performance pages. Statsmodels: also the other assumption tests |
| 28 | "before approving a fuel request" → "before a fuel request is approved" |
| Ch. IV, V | The actual fuel may be recorded by the staff member too; larger errors occur on long trips, not on larger vehicles |

## I. Last proofreading

| Page | Change |
|---|---|
| 6 | "General Services Offices." → "General Services Office." |
| 9 | "addresses the problems" → "addresses the problem"; "goes into a web in which" → "goes into a web application in which" |
| 30 | "six(6)" → "six (6)" |
| 49 | Curly quotes in references [28]–[43] |
| 10, 16 | Citation [2]: MAE 3.932 and RMSE 2.935 are the values printed in the article's abstract, so they stay |

## J. Fleet-range performance

Added to the system (Model Performance) and the manuscript: on the 6,852 test records within the fleet's operating range (diesel, 30–400 km, 51–177 kW), R² = 0.8893, MAE = 2.0069 L, RMSE = 2.9178 L. The full testing-set results (R² = 0.9502) are kept. Changed: Abstract, the metrics paragraph and its code in Chapter III, T16 and Table 9, Chapter V.

## K. To confirm

- The drafts in `docs/THESIS_CHAPTER_IV.md` and `THESIS_CHAPTER_V.md` say "motorpool staff" where the manuscript says
  "Transportation Office". Use one name throughout.
- The README and Colab notebook title say "Government Fleets"; the manuscript title says "Government Fleet".
