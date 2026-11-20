// CHAPTER IV - Methodology (follows the team's latest PDF; every [value] and blank filled)
// Uses the helper functions defined at the top of main.typ (hd, cap, tbl, tc, td, figimg, figcap, eqtext).

#chap[CHAPTER IV][Methodology]

The researchers used the CRISP-DM (Cross-Industry Standard Process for Data Mining) methodology. CRISP-DM has six phases: Business Understanding, Data Understanding, Data Preparation, Modeling, Evaluation, and Deployment. The process is cyclical, allowing the researchers to revisit earlier phases when new findings arise during the study.

#figimg("images/crisp_dm.png", 258pt)

#figcap[Figure 2. #strong[#underline[The Process Model of the System]];]

#emph[Figure 2]; represents the Process Model consisting of six (6) major phases\/stages of the CRISP-DM Model that was used in developing the study.

#hd[Overview of Process Model Phases]

#hd[Business Understanding Phase]

In the initial stage, known as business understanding, the researchers identified the problem in the fuel management of the Guimaras State University fleet. The General Services Office approves fuel requests based on experience and past records, and excessive fuel use is detected only during liquidation after the trip. This shows the need for a model that predicts the fuel needed for each official trip before a request is approved.

#hd[Data Understanding Phase]

Secondly, during data understanding, the researchers identified the data needed to predict fuel consumption. The team collected 93 trips from the historical Monthly Report of Official Travel and the vehicle records of the nine fleet vehicles, and gathered a supplementary dataset from open online sources. The data was then checked for missing entries, inconsistencies, and the relationship of distance traveled, engine power, and fuel type to fuel consumed.

#hd[Data Preparation Phase]

Further, the researchers produced a clean, modeling-ready dataset. They merged the trip and vehicle records using the plate number and combined them with the supplementary dataset. Incomplete records and extreme outliers were removed, only records within the operating range of the fleet were kept, records the equation could not represent were removed, fuel type was encoded into numeric form, distance and engine power were centered, and an interaction term between the two was added. The final dataset holds 34,116 records.

#hd[Modeling Phase]

In this phase, the researchers designed the data pipeline, the analytical data model, the machine learning lifecycle, and the inference and integration architecture of the system. The dataset was split into 80 percent training and 20 percent testing sets. The researchers checked the predictors for correlation and multicollinearity, and the Linear Regression model was then trained by weighted least squares to learn the relationship between the predictors and the fuel consumed per trip.

#hd[Evaluation Phase]

Next, the researchers checked the model assumptions through a residual plot, a residual histogram, a normal Q-Q plot, and statistical tests. Predictions on the testing set were compared with the actual fuel consumed using R-Squared, Mean Absolute Error, and Root Mean Squared Error. A 5-fold cross-validation confirmed whether the accuracy held across other partitions of the data.

#hd[Deployment Phase]

Lastly, the trained model was integrated into a web application. The staff of the General Services Office and the Transportation Office select a vehicle and enter the trip distance. The system returns a predicted fuel figure before a fuel request is approved.

#pagebreak()

#hd[Discussion of the Process Model Phases]

#cap[Table 1. #strong[#underline[PHASES OF THE PROCESS MODEL AND CORRESPONDING TASK]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); table(columns: (190pt, 1fr), stroke: 0.6pt, inset: (x: 4pt, y: 2.5pt), tc[Phase], tc[Task Description], table.cell(rowspan: 6, align: center + horizon, strong[Business Understanding]), td[T1 Group Organization], td[T2 Project Planning], td[T3 Proposal Making and Title Defense], td[T4 Finalizing the Study Title], td[T5 Literature Review and Problem Definition], td[T6 User Requirements Analysis], table.cell(rowspan: 2, align: center + horizon, strong[Data Understanding]), td[T7 Dataset Collection], td[T8 Data Exploration and Quality Verification], table.cell(rowspan: 3, align: center + horizon, strong[Data Preparation]), td[T9 Data Merging and Cleaning], td[T10 Outlier Removal and Encoding], td[T11 Data Splitting and Interaction Term Creation], table.cell(rowspan: 3, align: center + horizon, strong[Modeling]), td[T12 Inference and Integration Architecture], td[T13 Correlation and VIF Analysis], td[T14 Linear Regression Model Training], table.cell(rowspan: 2, align: center + horizon, strong[Evaluation]), td[T15 Model Assumption Checks], td[T16 Model Performance Evaluation and Cross-Validation], table.cell(rowspan: 2, align: center + horizon, strong[Deployment]), td[T17 Web Application Design, Development and Model Integration], td[T18 System Testing, Implementation and Documentation]) }

#emph[Table 1]; presents the phases of the CRISP-DM (Cross-Industry Standard Process for Data Mining) process and the tasks completed in each phase during the development of the Fuel Consumption Prediction System using Linear Regression. The process consists of six phases, namely Business Understanding, Data Understanding, Data Preparation, Modeling, Evaluation, and Deployment. Each phase holds specific tasks guiding the researchers from defining the fuel request problem, to preparing the travel and vehicle records, training and evaluating the model, and delivering the web application to its users.

#pagebreak()

#hd[Business Understanding Phase]

#hd[T1. Group Organization]

The study was done by a group of three researchers. Each researcher held a role in the development of the system. The researchers organized themselves and assigned tasks to finish the work on schedule.

#block(height: 158pt, below: 8pt, grid(columns: (196pt, 1fr), align: horizon,
  rect(width: 196pt, inset: 12pt, stroke: 0.8pt, align(center, par(first-line-indent: 0pt, strong[Aleah M. Casuyon] + linebreak() + [Project Manager \/ Technical Writer]))),
  pad(left: 46pt, grid(rows: (auto, auto), row-gutter: 24pt,
    rect(width: 100%, inset: 14pt, stroke: 0.8pt, align(center, par(first-line-indent: 0pt, strong[Warren G. Gania] + linebreak() + [Programmer]))),
    rect(width: 100%, inset: 12pt, stroke: 0.8pt, align(center, par(first-line-indent: 0pt, strong[Ace Ryan A. Erandio] + linebreak() + [Field Researcher \/ Data Analyst])))))))

#figcap[Figure 3. #strong[#underline[Organizational Structure of the Project Team]];]

#emph[Figure 3]; illustrates the Organizational Structure of the Project Team, showing the hierarchy and roles of the project team members, with Aleah M. Casuyon as the Project Manager and Technical Writer overseeing the Programmer and the Field Researcher \/ Data Analyst.

#cap[Table 2. #strong[#underline[GROUP ORGANIZATION AND RESPONSIBILITIES]];]

#{ set par(first-line-indent: 0pt, justify: true, leading: 6pt); table(columns: (108pt, 108pt, 1fr), stroke: 0.6pt, inset: (x: 5pt, y: 4pt),
 tc[Researchers], tc[Role\/s], tc[Role Description],
 table.cell(align: center + horizon)[Aleah M. Casuyon], table.cell(align: center + horizon)[Project Manager \/ Technical Writer], [The person responsible for managing the project and keeping it within the defined timeline and scope. She coordinates with the adviser and writes and formats the manuscript.],
 table.cell(align: center + horizon)[Warren G. Gania], table.cell(align: center + horizon)[Programmer], [The person responsible for developing the Linear Regression model and the web application, while coordinating with the project manager.],
 table.cell(align: center + horizon)[Ace Ryan A. Erandio], table.cell(align: center + horizon)[Field Researcher \/ Data Analyst], [The person responsible for gathering the Monthly Report of Official Travel records and vehicle records from the General Services Office, compiling the supplementary dataset, and encoding, exploring, and verifying the data before modeling.],
) }

#emph[Table 2]; shows the Project Development Group, with their respective roles and responsibilities. The group discussed the study and its development to reach the objectives of the project.

#hd[T2. Project Planning]

The researchers planned the project around the six phases of CRISP-DM and assigned each task in #emph[Table 1]; to the member whose role fits it. #emph[Table 3]; shows the development plan of the study.

#cap[Table 3. #strong[#underline[STUDY DEVELOPMENT PLAN]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: (40pt, 1fr, 120pt, 110pt), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[Task No.], tc[Task], tc[In-Charge], tc[Schedule]),
 table.cell(colspan: 4, align: center, strong[1. Business Understanding]),
 td[T1], td[Group Organization], td[Project Team], td[#strong[\[month – month 2026\]]],
 td[T2], td[Project Planning], td[Project Manager], td[#strong[\[month – month 2026\]]],
 td[T3], td[Proposal Making and Title Defense], td[Project Team], td[#strong[\[month – month 2026\]]],
 td[T4], td[Finalizing the Study Title], td[Project Team], td[#strong[\[month – month 2026\]]],
 td[T5], td[Literature Review and Problem Definition], td[Project Team], td[#strong[\[month – month 2026\]]],
 td[T6], td[User Requirements Analysis], td[Project Manager \/ Programmer], td[#strong[\[month – month 2026\]]],
 table.cell(colspan: 4, align: center, strong[2. Data Understanding]),
 td[T7], td[Dataset Collection], td[Field Researcher \/ Data Analyst], td[#strong[\[month 2026\]]; (records cover January–June 2026)],
 td[T8], td[Data Exploration and Quality Verification], td[Field Researcher \/ Data Analyst], td[October 16–18, 2026],
 table.cell(colspan: 4, align: center, strong[3. Data Preparation]),
 td[T9], td[Data Merging and Cleaning], td[Data Analyst \/ Programmer], td[October 16 – November 9, 2026],
 td[T10], td[Outlier Removal and Encoding], td[Data Analyst \/ Programmer], td[October 18 – November 9, 2026],
 td[T11], td[Data Splitting and Interaction Term Creation], td[Programmer], td[October 28 – November 9, 2026],
 table.cell(colspan: 4, align: center, strong[4. Modeling]),
 td[T12], td[Inference and Integration Architecture], td[Programmer], td[October 16 – November 14, 2026],
 td[T13], td[Correlation and VIF Analysis], td[Data Analyst \/ Programmer], td[October 28 – November 9, 2026],
 td[T14], td[Linear Regression Model Training], td[Programmer], td[October 28 – November 9, 2026],
 table.cell(colspan: 4, align: center, strong[5. Evaluation]),
 td[T15], td[Model Assumption Checks], td[Data Analyst \/ Programmer], td[November 2–9, 2026],
 td[T16], td[Model Performance Evaluation and Cross-Validation], td[Data Analyst \/ Programmer], td[November 2–9, 2026],
 table.cell(colspan: 4, align: center, strong[6. Deployment]),
 td[T17], td[Web Application Design, Development and Model Integration], td[Programmer], td[October 16 – November 15, 2026],
 td[T18], td[System Testing, Implementation and Documentation], td[Project Team], td[November 9–15, 2026],
) }

#emph[Table 3]; outlines the development plan of the study. The dates of T8 to T18 come from the project's version history, from the first version of the system on October 16, 2026, to the final model on November 9, 2026, and the last system update on November 15, 2026. Each member worked on the tasks aligned with their role, and the team worked together on shared tasks to finish everything on or before each deadline.

#hd[T3. Proposal Making and Title Defense]

Fuel for the official trips of the university fleet is requested and approved through paper-based forms, and the fuel consumed is recorded only after the trip in the Monthly Report of Official Travel. The researchers noticed the General Services Office approves fuel requests based on experience and past records, with no computed reference for a specific trip. To bridge this gap, the researchers prepared a proposal for a system using Linear Regression to predict the fuel consumed per trip from the records of the fleet. The proposal was presented to the panel during the title defense on #strong[\[date of title defense\]];, and the comments and suggestions of the panel were addressed before proceeding to the next phase.

#hd[T4. Finalizing the Study Title]

The researchers conducted a meeting and finalized the title of the study, which is “Performance of Linear Regression Model in Predicting Fuel Consumption for Government Fleet.” The researchers planned to develop and evaluate a Linear Regression model predicting the fuel consumed per official trip, and to integrate the trained model into a web application for the General Services Office and the Transportation Office.

#hd[T5. Literature Review and Problem Definition]

The researchers reviewed studies on fuel consumption prediction to understand the methods, predictors, and evaluation metrics used in similar work. The reviewed studies applied Linear Regression and other machine learning models to trucks, light-duty vehicles, marine generators, and fleet records \[1\], \[2\], \[3\], \[8\], and several compared Linear Regression with Random Forest, Support Vector Regression, and neural networks \[9\], \[10\], \[11\]. The literature showed distance traveled, engine power, and fuel type among the predictors of fuel use \[5\], \[20\], \[22\].

From the review, the researchers defined the problem of the study. Previous studies relied on sensor or national datasets, while none addressed a government fleet relying on manually encoded records. The study therefore focused on evaluating how well a Linear Regression model, trained on the fleet records and a supplementary dataset, predicts the fuel consumed per trip.

#hd[T6. User Requirements Analysis]

To achieve the objectives of the study, the following requirements were identified:

#ni[#strong[Functional Requirements:];]

#sli[• Users must sign up for an account, and the account can be used only after the administrator approves it.]
#sli[• The staff must select a vehicle, enter the trip distance, and receive the predicted fuel consumption in liters with its predicted range of plus or minus the RMSE.]
#sli[• The system must warn the user when the distance or engine power is outside the range the model was trained on (30 to 400 km and 51 to 177 kW) or the vehicle has no trip records of its own.]
#sli[• Each prediction must be saved, submitted as a fuel request, and added to the trip records as a pending trip.]
#sli[• The staff must view the status of their own fuel requests in the prediction history.]
#sli[• The administrator must approve a fuel request with the liters to release, or reject it.]
#sli[• The actual fuel consumed must be recorded after the trip, and the same figure is saved to the fuel request and its trip.]
#sli[• The administrator must manage the vehicle records, trip records, and user accounts.]
#sli[• The administrator must upload a model retrained in Google Colab through the Model Performance page, and the system checks it before it replaces the active model.]

#ni[#strong[Technical Requirements:];]

#sli[• Datasets: the system requires complete trip, vehicle, and supplementary records to train an accurate model.]
#sli[• Hardware: the system requires a computer able to run a web browser and the Flask server.]
#sli[• Internet connection: the system requires internet access to reach Firebase Firestore.]

#ni[#strong[Non-functional Requirements:];]

#sli[• The system must validate the inputs before sending them to the model.]
#sli[• The system must restrict each user to the features of their role.]
#sli[• The system must keep the current model active and giving predictions until a valid new model is uploaded.]

#ni[#strong[Performance and Accuracy Requirements:];]

#sli[• The R-Squared, Mean Absolute Error, and Root Mean Squared Error of the model are measured and shown on the Model Performance page.]

#hd[Data Understanding Phase]

#hd[T7. Dataset Collection]

The researchers collected the Monthly Report of Official Travel records from the General Services Office of Guimaras State University, which provide the date of travel, distance traveled, and fuel consumed per trip. The vehicle records, consisting of the plate number, vehicle model, fuel type, and engine power of each vehicle, were compiled for the university fleet. The online records came from two open datasets: the real-world gasoline trips of Fan and Song \[42\] and the 2024 real-world records of diesel vans of the European Environment Agency \[43\].

#block(breakable: false)[
#cap[Table 4. #strong[#underline[COLLECTED RECORDS PER SOURCE]];]

#tbl((165pt, 60pt, 211pt,), tc[Source], tc[Records], tc[Description], td[Monthly Report of Official Travel (GSO)], td[93], td[Official trips of SFA 4714, January–June 2026], td[Vehicle records of the university fleet], td[9 vehicles], td[Plate number, vehicle model, fuel type and engine power (kW)], td[Trip records from online datasets], td[7,496], td[Diesel van trips from the European Environment Agency (2025)], td[Other online records], td[92,402], td[50,508 gasoline records (Fan and Song) and the other 41,894 diesel van records (EEA)], td[#strong[Total trip records]], td[#strong[99,991]], td[Each record is used only once])
]

#emph[Table 4]; shows the number of records collected from each source. The total of 99,991 counts only trip records. The 9 vehicle records describe the fleet vehicles and are not trips. By the time the model was trained, the system had added 6 trips recorded through completed fuel requests, so 99,997 trip records entered preprocessing.

#hd[T8. Data Exploration and Quality Verification]

The researchers checked every record before modeling. They reviewed the records for missing entries, zero distances, encoding errors, and inconsistencies. Distances in the supplementary data were converted into kilometers. Fuel rates recorded in liters per 100 kilometers were converted into total liters per trip, so all sources share the same unit. The researchers also examined how distance traveled, engine power, and fuel type relate to fuel consumed, to confirm their use as predictors.

The 93 local trips cover 32 to 372 km, with a mean of 176 km, and a mean recorded fuel of 17.6 liters per trip. Every local record follows the same allocation of one liter per 10 kilometers, so the local fuel figure is an allocated value rather than a metered one. The local records also cover only one vehicle, SFA 4714, over six months, which is why the supplementary dataset was needed to cover the other engine sizes of the fleet.

#hd[Data Preparation Phase]

#hd[T9. Data Merging and Cleaning]

After verifying the data, the researchers merged the trip records and vehicle records using the plate number, then combined them with the supplementary dataset using their shared variables. Each record was labeled according to its source to identify the local trips after merging. Records with missing values or zero distance were removed.

#hd[T10. Outlier Removal and Encoding]

The researchers removed extreme outliers with the Interquartile Range (IQR) method. The records were grouped by engine power, and the method was applied to the fuel used per 100 kilometers within each group of vehicles with the same engine power, so large vehicles were compared only with vehicles of similar size.

$ "IQR" = Q_3 - Q_1 $

$ "Lower bound" = Q_1 - 1.5("IQR") #h(2em) "Upper bound" = Q_3 + 1.5("IQR") $

Records below the lower bound or above the upper bound were removed. The researchers then kept only records inside the operating range of the university fleet: diesel vehicles, trips of 30 to 400 kilometers, and engines of 51 to 177 kilowatts. Last, the researchers removed the records that the regression equation could not represent. The model was fitted, and each record received a standardized residual:

$ z_i = ((y_i - hat(y)_i) sqrt(w_i)) / s $

#ni[where #emph[w];#sub[i]; is the weight of the record (see T14) and #emph[s]; is the standard deviation of the weighted residuals. Records with #emph[z];#sub[i]; beyond ±3 were dropped, and the fit was repeated until none was left. Fuel type was encoded as 1 for gasoline and 0 for diesel.]

#block(breakable: false)[
#cap[Table 5. #strong[#underline[RECORDS BEFORE AND AFTER PREPROCESSING]];]

#tbl((176pt, 90pt, 90pt, 80pt,), tc[Source], tc[Before], tc[After], tc[Removed], td[Local Trips (GSO)], td[99], td[97], td[2], td[Fleet-matched online records], td[7,496], td[7,098], td[398], td[Supplementary online records], td[92,402], td[26,921], td[65,481], td[#strong[Total]], td[#strong[99,997]], td[#strong[34,116]], td[#strong[65,881]])
]

#emph[Table 5]; shows the records kept after cleaning, outlier removal, and the operating-range filter. The local trips are the 93 trips of the Monthly Report of Official Travel and 6 trips recorded through completed fuel requests. All 93 trips of the Monthly Report passed every check, while 2 short fuel-request trips with an unusually high fuel use per 100 km were removed by the IQR method. The IQR method removed 3,858 records, 61,663 records were outside the operating range of the fleet, including every gasoline record, and the residual check removed 360 records, about 1 percent. Most removed records came from the supplementary data, since many of those vehicles fall outside the fuel type, distance, and engine power range of the university fleet. The final dataset holds 34,116 diesel records.

#block(breakable: false)[
#cap[Table 6. #strong[#underline[DESCRIPTIVE STATISTICS OF THE FINAL DATASET]];]

#tbl((126pt, 80pt, 80pt, 75pt, 75pt,), tc[Variable], tc[Mean], tc[Std. Dev.], tc[Minimum], tc[Maximum], td[Distance traveled (km)], td[151.18], td[92.05], td[30.00], td[400.00], td[Engine power (kW)], td[95.23], td[22.03], td[51.00], td[177.00], td[Fuel consumed (L)], td[14.12], td[8.56], td[1.90], td[66.78])
]

#emph[Table 6]; shows the descriptive statistics of the final dataset. The average trip covers 151.18 km and uses 14.12 L of fuel. Distances range from 30 km to 400 km, and engine power ranges from 51 kW to 177 kW. Since every record is diesel, the fuel type is 0 in all 34,116 records.

#hd[T11. Data Splitting and Interaction Term Creation]

The dataset was split into an 80 percent training set of 27,292 records and a 20 percent testing set of 6,824 records. A fixed random seed (42) reproduces the same split in every run. Distance traveled and engine power were then centered on the mean values of the training set, 150.924 km and 95.2289 kW. An interaction term between the centered variables accounts for the higher fuel use per kilometer of larger engines.

$ "Distance"_c = "Distance" - overline("Distance")_"train" $

$ "Engine Power"_c = "Engine Power" - overline("Engine Power")_"train" $

$ "Interaction" = "Distance"_c times "Engine Power"_c $

Centering reduces the overlap between the interaction term and its parent variables. The training means were saved with the model and applied to every new input in the web application.

#hd[Modeling Phase]

#hd[Data and Process Modeling]

Before training, the researchers modeled how the data moves through the study and how the trained model is used in the system. Four diagrams describe the data pipeline, the analytical data model, the machine learning lifecycle, and the inference and integration architecture.

#hd[Data Pipeline Diagrams]

#block(breakable: false)[
#figimg("images/fig1_data_pipeline.png", 370pt)

#figcap[Figure 4. #strong[#underline[Data Pipeline Diagram]];]
]

#emph[Figure 4]; traces the records from collection to the trained model in eight stages. (1) The data sources are the GSO trip records, which hold the 93 trips of the Monthly Report of Official Travel and the trips of completed fuel requests, the 9 vehicle records, the 7,496 online trip records of European Environment Agency vans, and the other 92,402 online records. (2) The trips, vehicles, and fuel requests are stored in Firebase Firestore, while the online records are kept in CSV files. (3) The administrator exports three CSV files from the Model Performance page, namely the trip records, the vehicle records, and the supplementary data, and loads them into the Google Colab notebook. (4) The notebook joins the trips and vehicles by plate number and merges them with the online data, tagging each record with its data source. (5) Cleaning removes records with missing values or zero distance, removes outliers with the IQR rule within each engine power, keeps only the fleet range of diesel vehicles, 30 to 400 km, and 51 to 177 kW, and removes records with a standardized residual beyond ±3, leaving 34,116 clean records. Pending trips have no fuel figure, so they are dropped in this step. (6) Feature engineering builds the four terms of the model: the centered Distance (X1), the centered Engine Power (X2), Fuel Type (X3, 0 for diesel), and Distance × Engine Power (X4). (7) The data is split into a 27,292-record training set and a 6,824-record test set, with 5-fold cross-validation. (8) The output is the Linear Regression model trained by weighted least squares, saved as a Joblib file with its metrics file, with an R² of 0.9020 and an MAE of 1.91 L.

#hd[Analytical Data Model Schema]

#block(breakable: false)[
#figimg("images/fig2_analytical_data_model.png", 370pt)

#figcap[Figure 5. #strong[#underline[Analytical Data Model Schema]];]
]

#emph[Figure 5]; shows the analytical data model as a star schema built from the Firestore collections of the system. Fact Trip holds one row per trip of the trip_records collection, with its distance (X1) and actual fuel consumed (Y). It links to Dim Vehicle by vehicle_id, to Dim Date by the date of travel, and to Dim Data Source, which marks each record as local, online trips, or supplementary. Fact Prediction holds one row per fuel request of the predictions collection, with the distance, the predicted fuel ŷ, the approval status, the liters approved for release, and the actual fuel. It links to Dim Vehicle, to Dim User (the staff member or administrator who made the request), and through trip_record_id to the pending trip it creates, so each fuel request has at most one trip. Dim Vehicle supplies the engine power (X2) and fuel type (X3) of every trip and request. The Model Input View is derived from these tables and holds the 34,116 clean records with X1 to X4 and the target Y, the actual fuel consumed in liters.

#hd[ML Lifecycle and Decision Flow]

#block(breakable: false)[
#figimg("images/fig3_ml_lifecycle_decision_flow.png", 370pt)

#figcap[Figure 6. #strong[#underline[ML Lifecycle and Decision Flow]];]
]

#emph[Figure 6]; shows the CRISP-DM cycle of the project and the decisions in it. The six phases follow the order of this chapter, and the dashed arrow from Evaluation back to Business Understanding marks a model that is not good enough and must be revised. Part A shows how the model is built: the administrator exports the training data, the model is trained in Google Colab, and if the accuracy is not acceptable or a VIF is above 5, the data is revised and the model is trained again. An acceptable model is uploaded, and the system checks it before it becomes the active model. Part B shows how the model is used: a fuel request with an invalid input shows an error and returns to the form. A valid request receives a predicted fuel figure with any warnings, and the administrator approves it with the liters to release or rejects it, which removes its pending trip. After an approved trip, the actual fuel is recorded, and when retraining is needed the cycle returns to Part A with the new trips included.

#hd[Inference and Integration Architecture]

#block(breakable: false)[
#figimg("images/fig4_inference_integration_architecture.png", 370pt)

#figcap[Figure 7. #strong[#underline[Inference and Integration Architecture]];]
]

#emph[Figure 7]; shows the three tiers of the system. The client tier is the web browser of the GSO staff and the administrator, with pages built from HTML, Bootstrap, and Chart.js. The application server is the Flask web application, run by Waitress on the computer of the General Services Office and by Vercel for the online link. Inside it, the pages and routes handle the forms and the JSON API, the prediction module validates the input, predicts the fuel, and adds the warnings, and the data access layer reads and writes the data. The data and model tier holds the CSV datasets of online trips, the trained model with its metrics file, and Firebase Firestore with the users, vehicles, trips, and fuel requests. The numbered arrows follow one prediction, and the lower part shows how a new model trained in Google Colab replaces the active one.

#hd[T12. Inference and Integration Architecture]

The encoding, the centering values, and the regression model are saved together in one pipeline with Joblib, so a prediction goes through the same steps as the training data. As numbered in #emph[Figure 7];, one prediction follows five steps: (1) the staff member sends the vehicle and the planned distance from the browser; (2) the route checks the input and gets the engine power and fuel type of the vehicle from Firebase Firestore; (3) the trained model predicts the fuel in liters and the system adds a range of plus or minus the RMSE and any warnings; (4) the fuel request and its pending trip are saved in Firestore; and (5) the result is shown, and the administrator later approves or rejects the request.

A new model is added in three steps. The administrator exports the training data, trains and evaluates the model in Google Colab, and uploads the Joblib model file and its metrics file on the Model Performance page. The system then checks that the uploaded model uses the same terms (Distance, Engine Power, Fuel Type, and their interaction) and gives the same results as its metrics file before it replaces the active model. If the check fails, the upload is refused and the current model stays active. The upload is done on the computer of the General Services Office, since the online link cannot save files.

#hd[T13. Correlation and VIF Analysis]

Before training, the researchers measured the correlation among the variables. The correlation heatmap shows the strength and direction of the relationship between each pair of variables. Values close to 1 or −1 mean a strong relationship. Values close to 0 mean a weak one.

#block(breakable: false)[
#figimg("images/correlation_heatmap.png", 330pt)

#figcap[Figure 8. #strong[#underline[Correlation Heatmap of the Variables]];]
]

#emph[Figure 8]; shows distance traveled as the strongest predictor of fuel consumed, with a correlation of 0.89. The interaction term follows at 0.22, and engine power at 0.15. Engine power alone has a weak link to fuel consumed. Its effect shows up through the interaction term, since a larger engine burns more fuel for every added kilometer. Fuel type does not appear in the heatmap because it is 0 (diesel) in every record, so it has no variation to correlate. The predictors share little information with one another. Distance and engine power correlate at −0.17. The interaction term correlates at only 0.06 with distance and 0.06 with engine power, which confirms the centering step kept the interaction term separate from its parent variables.

The researchers then computed the Variance Inflation Factor (VIF) of each predictor. A VIF above 5 signals high collinearity.

$ "VIF"_j = 1 / (1 - R_j^2) $

#ni[where #emph[R];#sub[j];#super[2]; is the coefficient of determination from regressing predictor #emph[j]; on all the other predictors.]

#block(breakable: false)[
#figimg("images/vif.png", 330pt)

#figcap[Figure 9. #strong[#underline[Multicollinearity Check (VIF)]];]
]

#emph[Figure 9]; shows VIF values of 1.03 for distance traveled, 1.03 for engine power, and 1.01 for the interaction term. All values sit close to 1, the lowest possible VIF, and far below the threshold of 5. Fuel type has no VIF because it is constant. The predictors carry separate information, so the coefficients of the model stay stable.

#hd[T14. Linear Regression Model Training]

The researchers trained the Linear Regression model on the 27,292 records of the training set using Scikit-learn. The model follows the equation below.

$ hat(y) = & beta_0 + beta_1("Distance"_c) + beta_2("Engine Power"_c) \ & + beta_3("Fuel Type") + beta_4("Distance"_c times "Engine Power"_c) $

#ni[where #emph[ŷ]; is the predicted fuel consumed in liters, #emph[β];#sub[0]; is the intercept, #emph[β];#sub[1]; to #emph[β];#sub[4]; are the coefficients of the predictors, and the subscript #emph[c]; marks a centered variable.]

A first fit by Ordinary Least Squares showed that the errors grow with the fuel a trip uses: the residuals had a standard deviation of about 1.3 L for trips predicted below 10 L and about 5.3 L for trips predicted above 30 L. The researchers therefore estimated the coefficients by Weighted Least Squares (WLS), which is still Linear Regression with the same equation \[12\]. The error variance of each record was modeled from the first fit:

$ log(e_i^2) = gamma_0 + gamma_1 log(hat(y)_i) $

#ni[which gave #emph[γ];#sub[0]; \= −4.48 and #emph[γ];#sub[1]; \= 1.88. Each record received the weight #emph[w];#sub[i]; \= 1 \/ exp(#emph[γ];#sub[0]; \+ #emph[γ];#sub[1]; log #emph[ŷ];#sub[i];), so a long, fuel-heavy trip with a larger error counts less, and the model was fitted again by minimizing the weighted sum of squared residuals:]

$ min_beta sum_(i=1)^n w_i (y_i - hat(y)_i)^2 $

#block(breakable: false)[
#cap[Table 7. #strong[#underline[COEFFICIENTS OF THE TRAINED MODEL]];]

#tbl((180pt, 90pt, 80pt, 86pt,), tc[Term], tc[Coefficient], tc[Std. Error], tc[p-value], td[Intercept (β#sub[0])], td[14.3283], td[0.0168], td[\< 0.001], td[Distance#sub[c] (β#sub[1])], td[0.0866], td[0.00017], td[\< 0.001], td[Engine Power#sub[c] (β#sub[2])], td[0.1143], td[0.00073], td[\< 0.001], td[Fuel Type (β#sub[3])], td[0.0000], td[–], td[–], td[Distance#sub[c] × Engine Power#sub[c] (β#sub[4])], td[0.000626], td[0.0000077], td[\< 0.001])
]

#emph[Table 7]; lists the coefficients of the trained model. Each coefficient gives the average change in liters for a one-unit change in its predictor while the other predictors stay constant. The standard errors are heteroskedasticity-robust (HC3), and every term except fuel type is significant at α \= 0.05.

Since both parent variables are centered, the intercept of 14.328 L is the predicted fuel for a trip of average distance (150.9 km) in a vehicle of average engine power (95.2 kW). β#sub[1] means each added kilometer uses about 0.087 L (about 8.7 L per 100 km) for a vehicle of average engine power, and β#sub[2] means each added kilowatt uses about 0.114 L on a trip of average distance. The positive β#sub[4] shows that larger engines use more fuel for every added kilometer. β#sub[3] is 0 because every training record is diesel, so the model learned no difference between gasoline and diesel; the term stays in the equation so that the same pipeline can accept gasoline vehicles if they are added later.

Written with the original, uncentered values, the same model is:

#eqtext[ŷ \= −0.6283 \+ 0.02696(Distance) \+ 0.01978(Engine Power) \+ 0.000626(Distance × Engine Power)]

For example, a 176 km trip of SFA 4714 (diesel, 95 kW) gives about 16.47 liters, close to the 17.5-liter average of its recorded trips. The trained model and the training means were exported with Joblib for use in the web application.

#hd[Evaluation Phase]

#hd[T15. Model Assumption Checks]

After training, the researchers examined the residuals to test the assumptions of linear regression. A residual is the actual fuel consumed minus the predicted fuel consumed. A positive residual means the model predicted too little fuel. A negative residual means it predicted too much. Since the model was fitted by weighted least squares, the assumptions apply to the standardized residuals #emph[z];#sub[i]; defined in T10, which put every trip on the same scale. With more than 300 records, the p-values of the formal tests flag even trivial departures, so the researchers judged linearity, normality, and equal variance by the size of the departure and report the p-values for reference \[48\], \[49\], \[50\].

#block(breakable: false)[
#figimg("images/residual_plot.png", 330pt)

#figcap[Figure 10. #strong[#underline[Residual Plot of the Standardized Residuals]];]
]

#emph[Figure 10]; plots the standardized residuals of the 6,824 test trips against the predicted fuel consumption. The points form an even band around the zero line, between about −2.6 and \+3.0, with no curved pattern and no funnel shape. The spread is the same for short and long trips: the standard deviation of the standardized residuals is 1.04 for trips predicted below 10 L, 0.98 for 10 to 30 L, and 0.95 above 30 L. In liters, a long trip still has a larger error than a short one, and the weights account for this difference. Across five equal groups of predicted fuel, the largest residual variance is 1.27 times the smallest, within the limit of 3 \[50\]. The Breusch-Pagan test gave a statistic of 96.51 with a p-value below 0.001; with 27,292 training records the test reacts to this very small difference, so the variance ratio was used for the decision.

#block(breakable: false)[
#figimg("images/residual_histogram.png", 330pt)

#figcap[Figure 11. #strong[#underline[Histogram of Residuals]];]
]

#emph[Figure 11]; shows the distribution of the residuals in liters. The bars form a bell shape centered on zero, and 73.4 percent of the residuals fall between −2.5 L and \+2.5 L. The two tails are nearly balanced: 273 trips have residuals above \+5 L and 239 below −5 L. Only 30 of the 6,824 test trips, or 0.44 percent, have residuals beyond 10 L in either direction.

#block(breakable: false)[
#figimg("images/residual_qq_plot.png", 330pt)

#figcap[Figure 12. #strong[#underline[Normal Q-Q Plot of the Standardized Residuals]];]
]

#emph[Figure 12]; compares the standardized residuals with a normal distribution. The points follow the reference line between about −2.5 and \+2.5 theoretical quantiles, which covers almost all of the test trips. The ends level off near −2.6 and \+3.0 because records beyond ±3 were removed during cleaning. The skewness is 0.36 and the excess kurtosis is −0.10, both close to the 0 of a normal distribution and well within the limits of ±2 and ±7 \[48\]. The Jarque-Bera test gave a statistic of 615.27 with a p-value below 0.001; with 27,292 training records it reacts to this small skew, so the skewness and kurtosis were used for the decision.

The Ramsey RESET test checked linearity by adding the square of the predicted fuel to the model. It gave F \= 15.49 with a p-value below 0.001, but the added term raised the explained variation by almost nothing: Cohen's f² was 0.0003, far below 0.02, the smallest effect that matters \[49\]. The relationship between the predictors and the fuel consumed is therefore linear.

The Durbin-Watson statistic tested the residuals of the 97 local trips, arranged by date of travel. Their average residual of \+1.08 L was removed first, since a constant difference for one vehicle is not a relation between consecutive trips. The statistic was 1.630, inside the range of 1.5 to 2.5, where a value close to 2 indicates independent errors. The errors of consecutive local trips are therefore independent.

#block(breakable: false)[
#cap[Table 8. #strong[#underline[SUMMARY OF ASSUMPTION CHECKS]];]

#tbl((88pt, 110pt, 108pt, 80pt, 50pt,), tc[Assumption], tc[Test], tc[Result], tc[Rule], tc[Met?], td[Linearity], td[Ramsey RESET test], td[F \= 15.49, p \< 0.001; f² \= 0.0003], td[f² \< 0.02], td[Yes], td[Independence], td[Durbin-Watson (97 local trips by date)], td[1.630], td[1.5 to 2.5], td[Yes], td[Normality], td[Jarque-Bera test], td[skewness 0.36, excess kurtosis −0.10; p \< 0.001], td[skewness and excess kurtosis within ±2 and ±7], td[Yes], td[Equal variance], td[Breusch-Pagan test], td[LM \= 96.51, p \< 0.001; variance ratio \= 1.27], td[variance ratio ≤ 3], td[Yes], td[No multicollinearity], td[Variance Inflation Factor], td[highest VIF \= 1.03], td[every VIF ≤ 5], td[Yes])
]

#emph[Table 8]; summarizes the assumption checks. All five assumptions were met. The removal of the records with standardized residuals beyond ±3 corrected the heavy tails, and weighted least squares corrected the growing spread of the errors, which the earlier ordinary least squares model without the residual check did not meet (variance ratio of 30.27 and excess kurtosis of 9.23). The p-values of the RESET, Jarque-Bera, and Breusch-Pagan tests stay below 0.05 because, with 27,292 training records, they detect departures too small to matter, so the decisions follow the size of each departure. As an added safeguard, the coefficient standard errors in #emph[Table 7]; use the heteroskedasticity-robust HC3 method.

#hd[T16. Model Performance Evaluation and Cross-Validation]

The researchers generated predictions for the 6,824 trips in the testing set and compared them with the actual fuel consumed. Three metrics measured the accuracy of the model. R-Squared (R²) measures how much of the variation in fuel consumed the predictors explain. A value of 1 means the model explains all of the variation. A value of 0 means it performs no better than the average fuel consumed.

$ R^2 = 1 - (sum (y_i - hat(y)_i)^2) / (sum (y_i - overline(y))^2) $

Mean Absolute Error (MAE) measures the average difference between the actual and predicted fuel in liters, regardless of direction.

$ "MAE" = 1 / n sum_(i=1)^n abs(y_i - hat(y)_i) $

Root Mean Squared Error (RMSE) squares each error before averaging, so large errors weigh more. A wide gap between RMSE and MAE means some trips have unusually large errors.

$ "RMSE" = sqrt(1 / n sum_(i=1)^n (y_i - hat(y)_i)^2) $

#ni[where #emph[n]; is the number of trips in the testing set, #emph[y];#sub[i]; is the actual fuel consumed, #emph[ŷ];#sub[i]; is the predicted fuel consumed, and #emph[ȳ]; is the average of the actual fuel consumed.]

#block(breakable: false)[
#figimg("images/actual_vs_predicted.png", 330pt)

#figcap[Figure 13. #strong[#underline[Actual vs Predicted Fuel Consumption]];]
]

#emph[Figure 13]; plots the predicted fuel against the actual fuel for each test trip. The model reached an R² of 0.9020 on the testing set, so the predictors explain 90.20 percent of the variation in fuel consumed. The MAE was 1.91 L, so a prediction differs from the actual fuel by about 2 liters on average, and the RMSE was 2.69 L. The RMSE is higher than the MAE because a few trips have larger errors. The points cluster tightly along the line of perfect prediction up to about 35 L and spread more for heavier trips. Above 45 L, 28 of the 32 test trips fall below the line, so the model tends to underestimate the few heaviest trips.

To test whether the accuracy holds for other partitions of the data, the researchers applied 5-fold cross-validation. The dataset was divided into five equal folds. The model was trained on four folds and tested on the fifth, five times, so each fold served once as the test set. The centering step was repeated inside each fold, so each test fold stayed unseen during training.

#block(breakable: false)[
#figimg("images/cv_r2_scores.png", 330pt)

#figcap[Figure 14. #strong[#underline[5-Fold Cross-Validation]];]
]

#emph[Figure 14]; shows an R² of about 0.90 in every fold: 0.9020, 0.9025, 0.9005, 0.8961, and 0.8999. The mean R² is 0.9002 with a standard deviation of 0.0023. The mean differs from the test-set R² of 0.9020 by only 0.0018. The mean MAE across the folds was 1.902 L (standard deviation 0.018) and the mean RMSE was 2.705 L (standard deviation 0.030). The model gives the same accuracy on every partition of the data. It does not depend on one lucky split and shows no sign of overfitting.

#block(breakable: false)[
#cap[Table 9. #strong[#underline[SUMMARY OF MODEL PERFORMANCE]];]

#tbl((150pt, 70pt, 216pt,), tc[Metric], tc[Result], tc[Interpretation], td[R² (testing set)], td[0.9020], td[The model explains 90.20% of the variation in fuel consumed], td[MAE (testing set)], td[1.91 L], td[Average prediction error per trip], td[RMSE (testing set)], td[2.69 L], td[Typical error with large misses weighted more], td[Mean R² (5-fold CV)], td[0.9002], td[Same accuracy across all five folds], td[Std. dev. of R² (5-fold CV)], td[0.0023], td[Very small spread of R² across folds], td[Mean MAE \/ RMSE (5-fold CV)], td[1.90 L \/ 2.70 L], td[Same error level as the testing set])
]

#emph[Table 9]; summarizes the performance of the Linear Regression model. The model explains about 90 percent of the variation in fuel consumed with an average error of about 2 liters per trip, and the result holds across every partition of the data. In liters, errors stay small for short and medium trips and are larger for long, fuel-heavy trips. The predicted range in the web application uses the RMSE (plus or minus 2.69 L), so the staff read it as a tighter guide for short trips than for long ones.

#hd[Deployment Phase]

#hd[T17. Web Application Design, Development and Model Integration]

The researchers designed the web application around the tasks of its two user roles, then built it with Flask, HTML, CSS, and JavaScript. Every page shares one layout with a side menu of Dashboard, Prediction, Vehicles, Trip Records, Model Performance, User Accounts, and Settings, works on desktop and mobile browsers, and has a light and a dark mode. Staff see only Dashboard, Prediction, Trip Records, and Settings. #emph[Table 10]; lists the modules of the system and the users who can open each one.

#cap[Table 10. #strong[#underline[MODULES OF THE WEB APPLICATION]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: (95pt, 1fr, 110pt), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[Module], tc[Description], tc[Access]),
 td[Sign Up and Login], td[Account creation with administrator approval, and role-based login], td[All users],
 td[Dashboard], td[Actual versus predicted fuel, monthly fuel consumption trend, model summary, and recent fuel requests], td[All users],
 td[Prediction (New Prediction)], td[Vehicle selection, trip distance input, predicted fuel with its range, and warnings], td[All users],
 td[Prediction (Prediction History)], td[Fuel requests, predicted range, approval with the liters to release, and actual fuel recording; shown as My Fuel Requests to staff], td[All users; only the administrator approves or rejects],
 td[Trip Records], td[Local trips, online-dataset trips, and pending trips from fuel requests], td[All users view; administrator edits],
 td[Vehicle Management], td[Plate number, vehicle model, fuel type, and engine power], td[Administrator],
 td[Model Performance], td[Metrics, coefficients, assumption tests, charts, training data export, and model upload], td[Administrator],
 td[User Accounts], td[Sign-up approval, accounts, and password reset], td[Administrator],
 td[Settings], td[Profile, profile picture, and password], td[All users],
 td[Notifications], td[Alerts for sign-ups, pending requests, and decisions on requests], td[All users],
) }

The trained Linear Regression model was then integrated into the system. Flask loads the Joblib model file and the saved training means when the server starts. When a staff member selects a vehicle and enters the trip distance, the system first checks the input: the distance must be a number greater than 0 and at most 1,000 km, and the vehicle must have an engine power and a fuel type in its record. It then retrieves the engine power and fuel type of the vehicle from Firebase Firestore, applies the same encoding and centering used in training, builds the interaction term, and passes the values to the model. The system returns the predicted fuel in liters with a predicted range of plus or minus the RMSE (2.69 L). It warns the user when the distance or engine power is outside the range the model was trained on (30 to 400 km and 51 to 177 kW), and when the vehicle has no trip records of its own in the Monthly Report of Official Travel. Each prediction is saved to the prediction history.

Every user holds one of two roles. The administrator of the General Services Office reviews fuel requests, manages the vehicle records, trip records, and user accounts, and uploads the trained model. Staff submit fuel requests and see only their own requests. A new user signs up and logs in only after the administrator approves the account.

Each prediction is submitted as a fuel request and adds a pending trip to the trip records. The administrator approves the request with the liters to release, using the predicted fuel as the reference, or rejects it. Once the actual fuel consumed is recorded, the same figure is saved to both the fuel request and its trip. A rejected request removes its pending trip and cannot receive an actual fuel figure. Pending trips have no fuel figure, so they stay out of model training. The prediction history marks any trip whose actual fuel falls outside the predicted range.

#hd[T18. System Testing, Implementation and Documentation]

The researchers tested each main function of the system against the expected result in #emph[Table 11];, using both the administrator and the staff roles.

#cap[Table 11. #strong[#underline[SYSTEM TEST CASES]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10pt); table(columns: (28pt, 85pt, 1fr, 1fr), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[No.], tc[Function], tc[Test Input], tc[Expected Result]),
 td[1], td[Sign up], td[New user submits the sign-up form], td[Account is saved as pending and cannot log in until the administrator approves it],
 td[2], td[Account approval], td[Administrator approves or rejects the sign-up], td[Approved user can log in; a rejected sign-up is removed],
 td[3], td[Login], td[Wrong username or password], td[Message “Invalid username or password.” and no access],
 td[4], td[Role restriction], td[Staff opens an administrator page], td[Access is refused; staff see only their own pages and requests],
 td[5], td[Input validation], td[Blank distance, text, 0 km, or more than 1,000 km], td[No prediction is made and the input error is shown],
 td[6], td[Fuel prediction], td[SFA 4714 (diesel, 95 kW), 176 km], td[About 16.47 L, with a range of plus or minus 2.69 L],
 td[7], td[Range warning], td[Distance outside 30 to 400 km], td[Prediction is shown with a warning that it is outside the training range],
 td[8], td[No-records warning], td[Vehicle with no Monthly Report trips], td[Prediction is shown with a warning that it is not validated against its own trips],
 td[9], td[Fuel request and pending trip], td[Prediction is saved], td[Fuel request appears in the prediction history and a pending trip in the trip records],
 td[10], td[Approval], td[Administrator approves with the liters to release, or rejects], td[Status is updated; a rejected request removes its pending trip],
 td[11], td[Actual fuel recording], td[Actual fuel entered after the trip], td[Same figure is saved to the fuel request and its trip; a value outside the predicted range is marked],
 td[12], td[Model upload], td[Administrator uploads the Joblib model and metrics file from Google Colab], td[The files are checked; a valid model replaces the active one and an invalid one is refused],
) }

#emph[Table 11]; lists the test cases of the system, from account handling to model upload. The researchers implemented the system for the General Services Office and the Transportation Office of Guimaras State University and documented the setup, user roles, and steps for using the system. The system runs on the computer of the General Services Office and was deployed on Vercel at https:\/\/gsu-fleetfuel.vercel.app, and both use the same Firebase Firestore database. Since the online link cannot save files, a newly trained model is uploaded on the computer of the General Services Office and then deployed to the online link. Authorized staff of the General Services Office and the Transportation Office open the system through a web browser on any device with an internet connection.

#block(breakable: false)[
#rect(width: 100%, height: 200pt, stroke: (dash: "dashed", thickness: 0.8pt), align(center + horizon, text(10pt)[Insert a screenshot of the Fuel Prediction page here \ (save it as images/system_ui.png and replace this box with \ \#figimg("images/system_ui.png", 400pt))]))

#figcap[Figure 15. #strong[#underline[System User Interface]];]
]

#emph[Figure 15]; shows the Fuel Prediction page of the system. The staff member selects a vehicle and enters the trip distance, and the page shows the predicted fuel in liters with its predicted range of plus or minus 2.69 L.

#hd[Development]

#hd[Software Specification]

The following software specifications were identified to support the development of the Fuel Consumption Prediction System.

#cap[Table 12. #strong[#underline[SOFTWARE SPECIFICATION]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: (110pt, 130pt, 1fr), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[Software], tc[Specification], tc[Usage]),
 td[Operating System], td[Windows 10\/11], td[Host OS of the development machine and the GSO computer. Users open the system through a web browser on any OS.],
 td[Programming Framework], td[Flask], td[Backend of the web application. Loads the trained model, handles requests, and returns predictions.],
 td[Programming Language], td[Python, HTML, CSS, JavaScript], td[Python for data preparation, model training, and the backend. HTML, CSS, and JavaScript for the web pages.],
 td[Algorithm], td[Linear Regression (Weighted Least Squares)], td[Predicts fuel consumed in liters from distance traveled, engine power, fuel type, and their interaction term.],
 td[Machine Learning Libraries], td[Scikit-learn, Statsmodels, Pandas, NumPy, Joblib], td[Data cleaning, splitting, model training, 5-fold cross-validation, VIF, Durbin-Watson, Breusch-Pagan, RESET and Jarque-Bera tests, and saving the model.],
 td[Visualization], td[Matplotlib, Seaborn], td[Correlation heatmap, VIF chart, residual plots, and actual vs predicted charts.],
 td[Database], td[Firebase Firestore], td[Cloud storage of users, vehicles, trips, fuel requests, and prediction history.],
 td[Development Environment], td[Google Colab, Visual Studio Code], td[Google Colab for model training and evaluation. Visual Studio Code as the main editor for Flask, HTML, CSS, and JavaScript code.],
 td[Web Server and Hosting], td[Waitress, Vercel], td[Waitress runs the system on the GSO computer. Vercel deploys it at https:\/\/gsu-fleetfuel.vercel.app.],
 td[Web Browser], td[Google Chrome, Mozilla Firefox, Microsoft Edge], td[Access to the system by the administrator and staff.],
) }

#emph[Table 12]; lists the software used to build, train, store, and deploy the system.

#hd[Program Specification]

The following are the specifications utilized in the development of the Fuel Consumption Prediction System.

CSS: A stylesheet language for the layout, colors, fonts, and spacing of web pages. It keeps the input forms, prediction results, and tables readable on desktop and mobile browsers.

Firebase Firestore: A cloud NoSQL document database by Google. It stores the user accounts, vehicle records, trip records, fuel requests, and prediction history, and syncs changes across users in real time.

Flask: A lightweight Python web framework. It serves the web pages, checks user roles, validates inputs, runs the inference pipeline, and returns the predicted fuel and range.

Google Colab: A cloud-based Jupyter notebook environment. The researchers used it for data merging, cleaning, encoding, model training, and evaluation, with no need for high-end local hardware.

HTML: The standard markup language for the structure of web pages. It builds the login, prediction, fuel request, admin dashboard, and prediction history pages.

JavaScript: A programming language for interactive web pages. It validates inputs on the client side and updates the page once the prediction returns from the server.

Joblib: A Python library for saving and loading Python objects. It exports the trained model and the training means into a file the Flask backend loads without retraining.

Matplotlib and Seaborn: Python libraries for charts. They produced the correlation heatmap, VIF chart, residual plot, histogram, Q-Q plot, actual vs predicted plot, and cross-validation chart.

NumPy and Pandas: Python libraries for numerical computing and data handling. Pandas loaded, merged, and cleaned the travel, vehicle, and online records. NumPy handled array operations and metric computation.

Python: A high-level programming language used for data preparation, model development, evaluation, and the backend of the web application.

Scikit-learn: A Python machine learning library. It split the data, trained the Linear Regression model, ran the 5-fold cross-validation, and computed R², MAE, and RMSE.

Statsmodels: A Python library for statistical tests. It computed the Variance Inflation Factor, the Durbin-Watson statistic, and the Breusch-Pagan, RESET, and Jarque-Bera tests.

Vercel: A cloud platform for hosting web applications. It deploys the system and keeps it available online for the General Services Office and the Transportation Office.

Visual Studio Code: A free source-code editor by Microsoft. It served as the main editor for the Flask backend and the web pages, with Git integration for version control.

#hd[Programming Environment]

#cap[Table 13. #strong[#underline[FRONT END]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: (70pt, 1fr, 1fr, 1fr), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[Programming Language], tc[Description], tc[Advantages], tc[Disadvantages]),
 td[HTML], td[The standard markup language for the structure and content of web pages. In this project, HTML builds every page of the system, including the input fields for vehicle and trip distance.], td[Supported by all modern browsers, light, and fast to load.], td[Produces no dynamic behavior without JavaScript or a backend.],
 td[CSS], td[A stylesheet language for layout, colors, fonts, and spacing. In this project, CSS styles the forms, tables, and result display.], td[Separates design from content. Media queries adapt pages to desktop and mobile screens.], td[Browsers sometimes render styles differently, which calls for cross-browser testing.],
 td[JavaScript], td[A programming language for interactive behavior on web pages. In this project, JavaScript validates inputs and displays the prediction without a full page reload.], td[Runs in the browser, reduces server load, and gives fast feedback to the user.], td[Client-side code is visible to users, so sensitive logic stays on the server.],
) }

#emph[Table 13]; shows the programming languages used in the front end, with their description, advantages, and disadvantages.

#cap[Table 14. #strong[#underline[BACK END]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: (70pt, 1fr, 1fr, 1fr), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[Technology \/ Service], tc[Description], tc[Advantages], tc[Disadvantages]),
 td[Python \/ Flask], td[A lightweight Python web framework for routing, request handling, and templates. In this project, Flask runs the inference pipeline and connects the pages to the model and database.], td[Runs the model in the same language used for training. Simple to set up, with little overhead.], td[Needs added tools for heavy traffic and large applications.],
 td[Scikit-learn and Joblib], td[Python libraries for training the Linear Regression model and saving it as a file.], td[Reliable, well-documented, and fast for linear models. The saved model loads in seconds.], td[The saved file depends on the library version, so training and server versions must match.],
 td[Firebase Firestore], td[A cloud NoSQL database storing users, vehicles, trips, fuel requests, and prediction history.], td[Fully managed by Google, real-time sync, and no server setup.], td[Requires an internet connection. Complex queries are limited compared with SQL databases.],
 td[Vercel], td[A cloud hosting platform for deploying the web application.], td[Fast deployment from a Git repository, free tier, and HTTPS by default.], td[Serverless functions have time and size limits and cannot save files, so a new model is uploaded on the GSO computer.],
) }

#emph[Table 14]; shows the technologies and services used in the back end, with their description, advantages, and disadvantages.

#hd[Hardware Specification]

The following hardware specifications were identified for the development and use of the Fuel Consumption Prediction System. Two sets of requirements are presented: one for the development machine of the researchers, and one for the devices of the end users.

#cap[Table 15. #strong[#underline[DEVELOPMENT HARDWARE SPECIFICATION]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: (95pt, 130pt, 1fr), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[Component], tc[Specification], tc[Usage]),
 td[Processor], td[Intel Core i5 \/ AMD Ryzen 5 or higher], td[Runs Visual Studio Code, the local Flask server, and the web browser. Model training runs on Google Colab.],
 td[RAM], td[Minimum 8 GB], td[Handles the code editor, browser tabs, and local testing of the system.],
 td[Storage], td[Minimum 50 GB available disk space], td[Stores the source code, datasets, CSV files, and the saved model.],
 td[Operating System], td[Windows 10\/11], td[The host OS of the development machine.],
 td[Connectivity], td[At least broadband internet], td[Required to access Google Colab, Firebase Firestore, Vercel, and to download dependencies.],
 td[Device Type], td[Desktop PC \/ Laptop], td[The main workstation for coding, testing, and version control.],
) }

#emph[Table 15]; presents the minimum hardware requirements for the development machine.

#cap[Table 16. #strong[#underline[END-USER DEVICE HARDWARE SPECIFICATION]];]

#{ set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: (95pt, 130pt, 1fr), stroke: 0.6pt, inset: (x: 4pt, y: 3pt),
 table.header(tc[Component], tc[Specification], tc[Usage]),
 td[Device Type], td[Desktop PC, laptop, or smartphone], td[Access to the system by the GSO administrator and the staff.],
 td[Processor], td[Dual-core processor or higher], td[Runs a modern web browser without noticeable lag.],
 td[RAM], td[Minimum 4 GB], td[Keeps the browser and system pages responsive.],
 td[Web Browser], td[Latest version of Chrome, Firefox, or Edge], td[Opens the web application at https:\/\/gsu-fleetfuel.vercel.app.],
 td[Connectivity], td[Stable internet connection], td[Required to reach the Flask backend and Firebase Firestore.],
) }

#emph[Table 16]; presents the minimum hardware requirements for the devices of the end users. Since the system runs in a web browser, no installation is required on the device.

#pagebreak()
