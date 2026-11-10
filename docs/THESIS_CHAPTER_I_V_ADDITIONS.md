# Additions to Chapters I–V (from "Fuel Consumption Prediction (10) - fix.pdf")

Each item says where it goes in the manuscript. Everything is based on the current system.
Text in **[brackets]** is a fact the system cannot supply (dates, panel comments). Fill these in before submission.

---

## Chapter I

**Limitations of the Study: add at the end of the paragraph.**

> The online link at https://gsu-fleetfuel.vercel.app cannot save files, so a newly trained model is uploaded on the computer of the General Services Office and then deployed to the online link.

Everything else in Chapter I matches the system.

## Chapter II

No change needed.

---

## Chapter III

**Details of the technologies to be used: add these four in alphabetical order.**

After **Flask**:

> **Font Awesome** - an icon library for web pages [44].
>
> Font Awesome provides the icons of the menus, buttons, and page sections of the web application.

After **Font Awesome**, before **Google Colab**:

> **Git and GitHub** - a version control system and an online service for hosting its repositories [45].
>
> Git records the changes to the source code, and GitHub holds the repository from which the online application is deployed.

After **Statsmodels**:

> **Vercel** - a cloud platform for deploying web applications from a source code repository [46].
>
> Vercel hosts the online link of the web application at https://gsu-fleetfuel.vercel.app.

After **Visual Studio Code**:

> **Waitress** - a production web server for Python web applications [47].
>
> Waitress serves the Flask application on the computer of the General Services Office.

**How the Project will work: add after the last paragraph.**

> Every user has one of two roles. The administrator of the General Services Office reviews fuel requests, manages the vehicle records, trip records, and user accounts, and uploads the trained model. The staff submit fuel requests and see only the requests they made. A new user signs up and can log in only after the administrator approves the account.
>
> Each fuel request adds a pending trip to the Trip Records. Once the actual fuel consumed is recorded, the same figure is saved to both the fuel request and its trip. If the request is rejected, its pending trip is removed. Pending trips have no fuel figure, so they are left out of model training. Prediction History also shows a predicted range, which is the predicted fuel plus or minus the RMSE of the model, and marks a trip whose actual fuel falls outside this range.

**References: add after [43].**

> [44] "Font Awesome." [Online]. Available: https://fontawesome.com/
>
> [45] "GitHub." [Online]. Available: https://github.com/
>
> [46] "Vercel." [Online]. Available: https://vercel.com/
>
> [47] "Waitress." [Online]. Available: https://docs.pylonsproject.org/projects/waitress/

---

## Chapter IV

### T2. Project Planning (replaces "[To be completed by the researchers.]")

> The researchers planned the project around the six phases of CRISP-DM and divided the work according to the roles in Table 2. Each task in Table 1 was assigned a schedule so that the data, the model, and the web application would be completed before the final defense. Table 3 shows the schedule.

Table 3. **PROJECT SCHEDULE**

| Phase | Tasks | Responsible | Period |
|---|---|---|---|
| Business Understanding | T1–T6 | All researchers | **[start – end]** |
| Data Understanding | T7–T8 | Field Researcher / Data Analyst | **[start – end]** |
| Data Preparation | T9–T11 | Programmer, Data Analyst | **[start – end]** |
| Modelling | T12–T14 | Programmer | **[start – end]** |
| Evaluation | T15–T16 | Programmer, Data Analyst | **[start – end]** |
| Deployment | T17–T18 | Programmer, Project Manager | October 16 – November 9, 2026 **[extend if work continued]** |

*(The Deployment dates come from the project's GitHub history. The trip data cover January–June 2026, so data collection cannot have ended before June 2026.)*

### T3. Proposal Making and Title Defense

> The researchers prepared a proposal that stated the problem in the fuel management of the university fleet, the objectives of the study, its scope and limitations, and the proposed method. The proposal was presented to the panel on **[date of title defense]**. The panel recommended **[comments or revisions given by the panel]**, and the researchers revised the proposal accordingly.

### T4. Finalizing the Study Title

> After the title defense, the researchers finalized the title as "Performance of Linear Regression Model in Predicting Fuel Consumption for Government Fleet." The title names the algorithm being evaluated, the value it predicts, and the setting of the study. It was approved by **[adviser / research coordinator]** on **[date]**.

### T5. Literature Review and Problem Definition

> The researchers reviewed studies on regression-based fuel prediction, including work on heavy-duty trucks, marine diesel generators, light-duty vehicles, and motorcycles. The review showed that distance traveled and engine power are strong predictors of fuel use, that R-Squared, MAE, and RMSE are the common performance measures, and that k-fold cross-validation is an accepted check of model stability. Most of these studies used sensor-collected, national, or industrial data, and none addressed a government fleet that relies on manually encoded records.
>
> The problem was then defined from the fuel process of the university. The General Services Office approves fuel requests based on experience and past records, there is no computed reference for a specific trip, and excessive use is found only during liquidation. The study therefore set out to evaluate a Linear Regression model that estimates the fuel needed for a trip before its request is approved.

### T6. User Requirements Analysis

> The researchers identified the users of the system and what each one needs to do **[state how: e.g., interview with the General Services Office on (date)]**. The users are the administrator of the General Services Office and the staff of the General Services Office and the Transportation Office. The requirements are listed in Tables B and C.

Table 4. **FUNCTIONAL REQUIREMENTS**

| No. | Requirement | User |
|---|---|---|
| FR1 | Sign up for an account, which can be used after the administrator approves it | Staff |
| FR2 | Log in, and change one's own profile and password | All users |
| FR3 | View a dashboard of fuel use and recent fuel requests | All users |
| FR4 | Select a vehicle, enter the trip distance, and receive a predicted fuel figure in liters | All users |
| FR5 | Have each prediction saved and submitted as a fuel request, with a pending trip added to the Trip Records | All users |
| FR6 | Receive a warning when a trip is outside the range of the model or the vehicle has no trip records of its own | All users |
| FR7 | View the Prediction History (staff see only their own requests) | All users |
| FR8 | Record the actual fuel consumed after the trip | All users |
| FR9 | View the Trip Records | All users |
| FR10 | Approve a fuel request with the liters to release, or reject it | Administrator |
| FR11 | Add, edit, and delete vehicle records and trip records | Administrator |
| FR12 | Approve or reject sign-ups, add and edit accounts, and reset passwords | Administrator |
| FR13 | View the Model Performance page, export the training data, and upload the trained model | Administrator |
| FR14 | Be notified of new sign-ups and pending fuel requests (administrator) or of the decision on one's own requests (staff) | All users |

Table 5. **NON-FUNCTIONAL REQUIREMENTS**

| Requirement | Description |
|---|---|
| Access control | Each page and action is limited by the role of the logged-in user. |
| Usability | Pages stay readable on desktop and mobile browsers, in light and dark mode. |
| Data storage | Vehicle records, trip records, user accounts, and prediction history are stored in Firebase Firestore. |
| Availability | The application is reachable on the computer of the General Services Office and online. |
| Consistency | A prediction goes through the same encoding and centering used in training. |

### T14: one correction

The worked example shows rounded coefficients, but those give 16.54 liters. The system's 16.55 uses the unrounded coefficients. Replace the last sentence with:

> For example, a 176 km trip of SFA 4714 (diesel, 95 kW) gives ŷ = −1.7904 + 0.03263(176) + 0.03167(95) + 0.000573(176 × 95) ≈ **16.55 liters** when computed with the unrounded coefficients saved in the model, close to the 17.6-liter average of its recorded trips.

### T17: add before "The application is deployed online"

Table 14. **MODULES OF THE WEB APPLICATION**

| Module | Description | Access |
|---|---|---|
| Sign Up and Login | Account creation with administrator approval, and role-based login | All users |
| Dashboard | Actual versus predicted fuel, monthly fuel consumption trend, model summary, and recent fuel requests | All users |
| Fuel Prediction | Vehicle selection, trip distance input, predicted fuel, and warnings | All users |
| Prediction History | Fuel requests, predicted range, approval, and actual fuel recording | All users; only the administrator approves or rejects |
| Trip Records | Local trips, online-dataset trips, and pending trips from fuel requests | All users view; administrator edits |
| Vehicle Management | Plate number, vehicle model, fuel type, and engine power | Administrator |
| Model Performance | Metrics, coefficients, assumption tests, charts, training data export, and model upload | Administrator |
| User Management | Sign-up approval, accounts, and password reset | Administrator |
| Settings | Profile and password | All users |
| Notifications | Alerts for sign-ups, pending requests, and decisions | All users |

Table 14 is followed by this sentence:

> *Table 14* lists the modules of the web application and the users who can access each one.

### T18: add at the end

> A newly trained model is uploaded through the Model Performance page on the computer of the General Services Office and then deployed to the online link, since the online link cannot save files.

*(Screenshots of each module can go under T17. Take them from the system, then number them after Figure 9.)*

---

## Chapter V

**Recommendation 2: replace.** Staff cannot encode trips directly. Trips are added through fuel requests, and only the administrator can add one manually.

> 2. **For the Transportation Office and drivers.** Submit each official trip through a fuel request in the system and record the actual fuel consumed soon after travel, instead of relying only on the paper-based Monthly Report of Official Travel, to reduce rounding, missing entries and encoding errors.

The Summary and Conclusion match the system.

---

## Checked against the system (no change needed)

| Paper | Result |
|---|---|
| Table 3, 4 record counts | Match; the totals add up (99,991 → 34,471) |
| Table 5 descriptive statistics | Match the cleaned dataset |
| T8 local trips (32–372 km, mean 176 km, 17.6 L) | Match; all 93 follow 1 L per 10 km |
| T11 split and centering values | Match |
| Tables 6–10 | Match model/metrics.json |
| Figure 6 (61 residuals beyond ±10 L) | Match |
| Equation | Matches |

**Outside Chapters I–V (still blank in the PDF):** "Month YYYY" on the cover, "YYYY" in the abstract citation, and the defense date on the Approval Sheet.
