// Performance of Linear Regression Model in Predicting Fuel Consumption for Government Fleet
// Compile with: typst compile main.typ   (Times New Roman and Consolas must be installed or uploaded)

#set page(paper: "a4", margin: (left: 108pt, right: 51.3pt, top: 112pt, bottom: 46pt),
  background: place(top + left, dx: 98pt, dy: 5pt, image("images/letterhead.png", width: 450pt)))
#set text(font: "Times New Roman", size: 12pt, lang: "en", hyphenate: true)
#set par(justify: true, leading: 9pt, spacing: 21.5pt, first-line-indent: (amount: 36pt, all: true))
#show raw: set text(font: ("Consolas", "DejaVu Sans Mono"), size: 7.4pt)
#show math.equation: set block(above: 14pt, below: 18pt)

#let frontnum = context align(center, counter(page).display("i"))
#let letterhead = place(top + left, dx: 98pt, dy: 5pt, image("images/letterhead.png", width: 450pt))
#let topnum = place(top + left, dy: 19pt, box(width: 569pt, align(right, context counter(page).display("1"))))
#let hd(t) = block(sticky: true, above: 21.5pt, below: 21.5pt, par(first-line-indent: 0pt, justify: false, strong(t)))
#let ni(just: true, t) = par(first-line-indent: 0pt, justify: just, t)
#let cent(t) = align(center, par(first-line-indent: 0pt, justify: false, t))
#let chap(a, b) = { pagebreak(weak: true); align(center, par(first-line-indent: 0pt, leading: 9pt, text(14pt, strong(a)) + linebreak() + text(14pt, strong(b)))); v(6pt) }
#let cap(t) = block(sticky: true, below: 6pt, align(center, par(first-line-indent: 0pt, justify: false, t)))
#let figcap(t) = align(center, par(first-line-indent: 0pt, justify: false, t))
#let eqtext(t) = align(center, par(first-line-indent: 0pt, text(11pt, t)))
#let figimg(p, w) = block(sticky: true, below: 4pt, align(center, image(p, width: w)))
#let code(s) = block(stroke: 0.5pt, inset: (x: 6pt, y: 5pt), width: 100%, breakable: false, { set par(first-line-indent: 0pt, leading: 3.2pt, justify: false); raw(s, block: true) })
#let li(t) = par(first-line-indent: 0pt, hanging-indent: 20pt, t)
#let sli(t) = pad(left: 24pt, par(first-line-indent: 0pt, hanging-indent: 20pt, t))
#let obj(t) = pad(left: 36pt, par(first-line-indent: 0pt, hanging-indent: 20pt, spacing: 6pt, t))
#let tc(t) = table.cell(align: center + horizon, strong(t))
#let td(t) = table.cell(align: left + horizon, t)
#let tbl(cols, ..cells) = block(breakable: false, { set par(first-line-indent: 0pt, justify: false, leading: 4pt); set text(10.5pt); table(columns: cols, stroke: 0.6pt, inset: (x: 6pt, y: 4pt), ..cells) })
#let refi(n, t) = grid(columns: (28pt, 1fr), n, par(first-line-indent: 0pt, t))
#let names(l) = align(center, par(first-line-indent: 0pt, leading: 9pt, l))
#let sign(name, role) = align(center, par(first-line-indent: 0pt, strong(underline(name)) + linebreak() + role))
#let fbox(w, title, items) = rect(width: w, height: 100%, inset: 0pt, stroke: 0.8pt, {
  set par(first-line-indent: 0pt, justify: false, leading: 3.5pt, spacing: 8pt)
  set text(8.2pt)
  align(center, pad(y: 4pt, text(9pt, strong(title)))); line(length: 100%, stroke: 0.8pt)
  pad(x: 5pt, y: 5pt, items.join(parbreak()))
})
#let figure1 = block(height: 196pt, above: 8pt, below: 6pt, grid(columns: (136pt, 16pt, 152pt, 16pt, 108pt), rows: 100%,
  fbox(136pt, [INPUT], ([Monthly Report of Official Travel: date of travel, distance traveled, fuel consumed], [Vehicle records: plate number, vehicle model, fuel type, engine power], [Supplementary dataset: distance traveled, engine power, fuel type, fuel consumed])),
  align(center + horizon, sym.arrow.r),
  fbox(152pt, [PROCESS], ([Data Preparation: merge by plate number, combine with the supplementary dataset, remove missing values and zero distance, IQR outlier removal, fleet operating range only, residual outlier removal, interaction term], [Model Development: 80/20 split, correlation and VIF checks, model training by weighted least squares], [Model Evaluation: residual plots, residual histogram, assumption tests, R², MAE, RMSE, 5-fold cross-validation], [System Development: web application design, model integration, implementation])),
  align(center + horizon, sym.arrow.r),
  fbox(108pt, [OUTPUT], ([Trained Linear Regression model with its R², MAE, and RMSE results], [Web application that returns a predicted fuel figure in liters])),
))


#set page(numbering: none, footer: frontnum, footer-descent: 0pt, margin: (left: 108pt, right: 51.3pt, top: 112pt, bottom: 46pt))
#counter(page).update(1)
#set par(first-line-indent: 0pt)
#align(center)[
  #v(12pt)
  #strong[Performance of Linear Regression Model in Predicting \ Fuel Consumption for Government Fleet]
  #v(40pt)
  A Research \/ Capstone Project \ Presented to the Faculty of the \ College of Science and Technology \ Guimaras State University \ Alaguisoc, Jordan, Guimaras
  #v(40pt)
  In Partial Fulfillment \ of the Requirements for the Degree \ Bachelor of Science in Information Technology
  #v(36pt)
  By:
  #v(10pt)
  Aleah M. Casuyon \ Warren G. Gania \ Ace Ryan A. Erandio
  #v(26pt)
  Divon G. Tamdang \ Adviser
  #v(36pt)
  Month YYYY
]
#pagebreak()
#set par(first-line-indent: (amount: 36pt, all: true))


#ni[#strong[CASUYON, A. M., GANIA, W. G., and ERANDIO, A. R. A. YYYY. Performance of Linear Regression Model in Predicting Fuel Consumption for Government Fleet.]; Research Capstone Project, College of Science and Technology, Guimaras State University, Alaguisoc, Jordan, Guimaras.]

#cent[#strong[ABSTRACT];]

Fuel requests for the government fleet of Guimaras State University are reviewed from experience and past records, and excessive use is found only during liquidation. This study developed and evaluated a Linear Regression model that predicts the fuel consumed per trip from distance traveled, engine power, and the interaction of distance and engine power, then integrated it into a web application. The data combined 93 trips from the Monthly Report of Official Travel, the records of nine fleet vehicles, and open online datasets, leaving 34,116 diesel records within the operating range of the fleet after cleaning and outlier removal. Because the error of a trip grows with the fuel it uses, the coefficients were estimated by weighted least squares. Under an 80\/20 train-test split, the model reached an R-squared of 0.9020, a Mean Absolute Error of 1.91 liters, and a Root Mean Squared Error of 2.69 liters. Five-fold cross-validation gave a mean R-squared of 0.9002 with a standard deviation of 0.0023. All Variance Inflation Factors were below 5, and the linearity, independence, normality, and equal-variance checks were all met. The local fuel figures follow an allocation rule and only one vehicle has local records, which limits validation on the other vehicles. The web application lets staff select a vehicle and enter the trip distance to receive a predicted fuel figure that serves as a reference when fuel requests are reviewed.

#ni[#strong[Keywords:]; Linear Regression, Fuel Consumption Prediction, Government Fleet, Machine Learning, Web Application.]

#pagebreak()
#set par(first-line-indent: (amount: 36pt, all: true))
#align(center, strong[APPROVAL SHEET])

This study\/project entitled #strong[PERFORMANCE OF LINEAR REGRESSION MODEL IN PREDICTING FUEL CONSUMPTION FOR GOVERNMENT FLEET] prepared and submitted by ALEAH M. CASUYON, WARREN G. GANIA, and ACE RYAN A. ERANDIO has been examined and is recommended for approval and acceptance.

#ni[RECOMMENDED:]

#grid(columns: (1fr, 1fr), sign[DIVON G. TAMDANG, MIT][Adviser], sign[JAMES RYAN B. GA, MIT][Research Coordinator])
#line(length: 100%, stroke: 2pt)

#ni[APPROVED by the committee on Oral Examination with a grade of #strong[PASSED] on Month Day, Year.]

#sign[ADRIAN J. FORCA, MIT][Panel Chairperson]

#sign[MARIA E. GATUNGAY][Panel Member]

#grid(columns: (1fr, 1fr), sign[JAMES RYAN B. GA, MIT][Panel Member], sign[LOVESON C. GALLOS, MIT][Panel Member])

#ni[ACCEPTED and APPROVED in partial fulfillment of the requirements in Bachelor of Science in Information Technology.]

#sign[DIVON G. TAMDANG, MIT][Program Head, BSIT]

#sign[ADRIAN J. FORCA, MIT][Dean, College of Science and Technology]


#pagebreak()
#counter(page).update(1)
#set page(footer: none, background: { letterhead; topnum })


#chap[CHAPTER I][Introduction]

#hd[#strong[Background of the Study];]

Fuel management is one of the important aspects in government fleet operations because fuel represents the largest component of vehicle operating costs \[1\]. Public agencies and state universities have a fixed annual budget, so every liter being released for an official trip is charged against public funds. Reliable estimation of fuel consumption is significant because understanding fuel dependencies improves the management efficiency of the entire fleet \[2\]. Precise estimates also support the quantification of energy cost caused by transportation which guides the decisions of both vehicle users and administrators \[3\]. In the university fleet, fuel is recorded through the paper-based Monthly Report of Official Travel and post-trip liquidation, which record consumption only after a vehicle has already returned.

Administrators and drivers face an operational challenge due to the lack of predicted fuel estimates. Administrators approve fuel requests based on experience and past track records instead of a computed reference for a specific trip. Excessive consumption is detected only during liquidation, when the fuel has already been used. Relying on manual input can cause rounding discrepancies, gaps, and inconsistencies in records that weaken the comparisons between actual and reasonable usage. Existing research shows that a vehicle’s fuel use is directly affected by quantifiable trip and vehicle factors, including its total weight, the steepness of the road, and the average speed when driving without traffic \[1\], \[4\]. In the Philippine setting, researchers use real driving data to link distance, speed, and fuel type to actual fuel use. This regression modeling explains the gap between factory fuel estimates and real road performance \[5\]. The Monthly Report of Official Travel records the distance traveled and fuel consumed per trip, but these records remain unused for prediction.

Locally, state universities utilize a government service fleet for inter-campus transport and official travel within the province. The transportation system records trips and fuel issuances through paper-based forms, yet it lacks a predictive model for estimating fuel use on future trips. Fuel requests and consumption review still depend on manual judgment.

Regression-based fuel prediction has been established across several transport contexts, including heavy-duty trucks modeled from telematics data \[1\], marine diesel generator plants \[2\], light-duty vehicle datasets \[3\], \[6\], engine design parameters \[7\], and driver behavior data \[8\]. Several works compare linear regression with random forest, support vector regression, and neural networks to identify the best model for a specific dataset \[9\], \[10\], \[11\]. While previous studies rely on national or industrial datasets, none address government fleets that depend on manually encoded government records rather than sensor-collected data.

To address the operational limitations, this study develops and evaluates the performance of a Linear Regression model in predicting fuel consumption for the government fleet. The model is trained on the historical travel and fuel records of the university fleet, combined with a supplementary dataset from open online sources. Each vehicle is described by its engine power and fuel type, attributes present in both the local and online records, which allow the model to learn from vehicles outside the fleet and apply the learned pattern to the university vehicles. The added diesel records widen the range of distances and engine sizes in the training data, since local records cover a limited number of trips and vehicles. Predictive performance is assessed through R-Squared, Mean Absolute Error, and Root Mean Squared Error under an 80\/20 train-test split and 5-fold cross-validation, a validation strategy applied in prior fleet-level modeling to minimize data selection bias \[11\]. Prediction from manual records carries known constraints, including encoding errors, missing entries, and the straight-line assumption of the model, which leaves nonlinear patterns unmodeled.

Moreover, the trained model is integrated into an interactive web application with input fields for the required trip metrics and vehicle attributes, then deployed for the General Services Office and the Transportation Office. By providing per trip fuel estimates, the study supports the fuel request validation and university fleet management.

#hd[#strong[Objectives of the Project];]

To develop and evaluate the performance of a Linear Regression model in predicting fuel consumption based on historical travel and fuel records from the government fleet, and to integrate the trained model into an interactive web application.

Specifically, this study aims to:

#obj[1\. collect historical fleet travel and fuel records and compile a supplementary dataset;]

#obj[2\. preprocess and merge the collected dataset through data cleaning, outlier removal, and encoding of categorical variables to produce a final modelling-ready dataset;]

#obj[3\. develop a Linear Regression model for predicting fuel consumption using an 80\/20 train-test split, where 80% of the data is used for training and 20% for testing;]

#obj[4\. train the model and evaluate the predictive performance using R-Squared (R²), Mean Absolute Error (MAE), and Root Mean Squared Error (RMSE), and validate its stability using 5-fold cross-validation;]

#obj[5\. design and develop an interactive web application interface with input fields for the required trip metrics and vehicle attributes;]

#obj[6\. integrate the trained Linear Regression model into the system; and]

#obj[7\. implement the web application for end-user access.]

#figure1

#figcap[Figure 1. #strong[#underline[The Conceptual Framework of the Study]];]

#emph[Figure 1]; shows the conceptual framework of the study. It traces how each input becomes the final output through four process stages. The Input component holds three data sources. The Monthly Report of Official Travel serves as the primary source and gives the date of travel, distance traveled, and fuel consumed per trip. The vehicle records of the university fleet supply the plate number, vehicle model, fuel type, and engine power. The plate number links each trip to its vehicle. The supplementary dataset includes distance traveled, engine power, fuel type, and fuel consumed, and it expands the training and testing sample. The distance traveled and engine power serve as the predictors, while the fuel consumed serves as the value to predict. The date of travel is not a predictor. It orders the local trips for the Durbin-Watson test.

The Process component has four stages. Data Preparation merges the travel records and vehicle records through the plate number, then combines them with the supplementary dataset using their shared variables. Records with missing values or zero distance are removed. The Interquartile Range method removes extreme outliers in fuel used per 100 kilometers, applied to each group of vehicles with the same engine power, and only diesel records of 30 to 400 km and 51 to 177 kW are kept. An interaction term between distance traveled and engine power accounts for the higher fuel use per kilometer of larger engines. Model Development splits the dataset into 80 percent training and 20 percent testing portions, checks the correlation among variables, computes the Variance Inflation Factor of each predictor, where a value above 5 signals high collinearity, and trains the Linear Regression model on the training portion. Model Evaluation checks the model assumptions through residual plots, a residual histogram, and the Durbin-Watson statistic. The predictions on the testing portion are compared with the recorded fuel consumption using R-Squared, Mean Absolute Error (MAE), and Root Mean Squared Error (RMSE). A 5-fold cross-validation then tests whether the same accuracy holds across other partitions of the data. System Development designs the web application, integrates the trained model, and implements the system for the General Services Office and the Transportation Office.

The Output component has two parts. The first is the trained Linear Regression model with its R², MAE, and RMSE results, which show how accurately the model estimates the fuel needed for a planned trip. The second is the web application. Staff select a vehicle and enter the trip distance, and the system returns a predicted fuel figure in liters. The administrator uses this figure as a reference when reviewing fuel requests.

#pagebreak(weak: true)

#hd[#strong[Scope of the Study];]

The study covers the government fleet of Guimaras State University. It develops and evaluates a Linear Regression model for predicting fuel consumption per trip, then integrates the trained model into an interactive web application. Training and testing use the Monthly Report of Official Travel records and the vehicle records of the university fleet, combined with a supplementary dataset from open online sources. The predictors are the distance traveled and engine power, along with an interaction term between them, for diesel records of 30 to 400 km and 51 to 177 kW. The predicted value is the fuel consumed in liters. Model evaluation uses an 80\/20 train-test split and 5-fold cross-validation, measured through R-Squared, Mean Absolute Error, and Root Mean Squared Error. The web application lets the staff of the General Services Office and the Transportation Office select a vehicle, enter the trip distance, and receive a predicted fuel figure. The system stores each prediction in a prediction history. The system also includes user sign-up with administrator approval, role-based user accounts, vehicle and trip records, fuel request review by the administrator, actual fuel recording, notifications, and a Model Performance page where the trained model is uploaded. Each fuel request adds a pending trip to the trip records. The system is deployed online at https:\/\/gsu-fleetfuel.vercel.app.

#hd[#strong[Limitations of the Study];]

The study limits its data to the government fleet of Guimaras State University, so the results do not extend to other agencies or to privately owned vehicles used for official travel. The Monthly Report of Official Travel records gathered cover one vehicle, SFA 4714, from January to June 2026. All nine fleet vehicles can be selected in the system, but predictions for vehicles without trip records are not validated against their own trips, and the system displays a warning for them. Accuracy of the local data depends on the manually prepared Monthly Report of Official Travel, which carries rounding, missing entries, and encoding errors. The fuel consumed in the 93 local records follows an allocation rule of one liter per 10 kilometers, not a measured value. Of the variables used in this study, the report provides only the date of travel, the distance traveled, and the fuel consumed per trip. Variables absent from either dataset are dropped during merging, which limits the final predictors to distance traveled, engine power, and their interaction term. The Interquartile Range method removes extreme trips, so the model gives less reliable estimates for unusually long or unusually fuel-heavy trips. The study tests Linear Regression alone, so it assumes a straight-line relationship. The predicted fuel figure serves as a reference only; the administrator approves or rejects fuel requests in the system. The study does not cover fuel budget monitoring or financial reporting. The output is a web application only, with no mobile application, and it requires an internet connection since the vehicle records and prediction history are stored in Firebase Firestore. The online link at https:\/\/gsu-fleetfuel.vercel.app cannot save files, so a newly trained model is uploaded on the computer of the General Services Office and then deployed to the online link.
#pagebreak(weak: true)

#hd[#strong[Significance of the Study];]

The results of the study will be beneficial to the following:

#strong[Guimaras State University.]; This study will help the university manage the fuel use of its service vehicles through a computed basis instead of manual judgment. It supports better use of the fixed annual budget, since every liter released for an official trip is charged against public funds.

#strong[General Services Office.]; This study will help the office review fuel requests through a web application where staff select a vehicle, enter the trip distance, and receive a predicted fuel figure before approval. It replaces manual judgment with a clear basis for each decision.

#strong[Transportation Office.]; This study will help the office plan official trips with an estimate of the fuel each vehicle needs for a given distance. It reduces guesswork and disputes over fuel releases between the office and the drivers.

#strong[Chief Administration Office.]; This study will help the office oversee fleet fuel spending with predicted figures tied to each trip. It supports informed approval of fuel allocations and better planning of the university’s fuel budget.

#strong[Researchers.]; This study will help the researchers apply data preparation, regression modeling, and model evaluation to a real government problem. It strengthens their skills in building and deploying a machine learning application.

#strong[Future Researchers.]; This study will help future researchers studying fuel consumption prediction in government fleets. It provides baseline performance results for comparing Linear Regression against other machine learning methods.

#pagebreak(weak: true)

#hd[#strong[Definition of Terms];]

For clarity, the terms used in this study are defined technically and operationally.

#strong[Fuel Consumption.]; The amount of fuel a vehicle uses over a given distance, expressed in liters per 100 kilometers and influenced by measurable factors such as travel distance, travel time, engine displacement, road conditions, and fuel characteristics \[5\].

In this study, this term refers to the total liters of fuel per official trip of a government vehicle, as recorded in the Monthly Report of Official Travel, where the figure follows an allocation of one liter per 10 kilometers. It serves as the dependent variable the Linear Regression model predicts.

#strong[Government Fleets.]; A group of vehicles operating under a common owner and vocation, where fuel consumption differs between individual vehicles and across the routes they travel \[11\].

In this study, this term refers to the service vehicles owned and operated by a state university for inter-campus transport and official travel. The trip and fuel records of these vehicles, merged with the supplementary dataset, form the data used to train and test the model.

#strong[Linear Regression Model.]; A statistical technique for modeling the relationship between a dependent variable and one or more independent variables, trained by adjusting its coefficients to reduce the difference between predicted and actual values \[8\].

In this study, this term refers to the algorithm trained on the merged fleet and supplementary records to estimate fuel consumption per trip. It uses the distance traveled and the engine power of diesel vehicles as independent variables.

#strong[Performance.]; The validity and accuracy of a regression model in estimating fuel consumption, assessed through the mean absolute error, the coefficient of determination, and the root mean squared error \[2\].

In this study, this term refers to how closely the predicted fuel consumption of the Linear Regression model matches the recorded fuel consumption of the fleet. It is measured through R-Squared, MAE, and RMSE under a train-test split and k-fold cross-validation.

#strong[Prediction.]; An estimate of how much fuel a vehicle will use, generated from collected data, which helps vehicle owners reduce their fuel costs \[10\].

In this study, this term refers to the expected fuel figure in liters for a planned trip. The trained model produces this figure once the staff of the General Services Office and the Transportation Office select a vehicle and enter the trip distance into the web application.

#chap[CHAPTER II Review of Related Literature][Theoretical Background]

The development of a fuel consumption prediction system for a government fleet is based on established theories of regression analysis, model validation, and performance measurement. Linear regression provides the foundation that relates a dependent variable to one or more independent variables \[12\]. Ordinary Least Squares estimates the coefficients of this regression model by minimizing the sum of squared residuals, where each residual is the difference between the recorded and the predicted fuel consumption \[13\]. The Gauss-Markov theorem establishes that these estimators are unbiased and possess the smallest variance among all linear unbiased estimators \[12\]. In this study, the model estimates fuel consumption in liters from the distance traveled, the engine power, and an interaction term between distance traveled and engine power. Each coefficient measures the average change in fuel consumption per unit change in a predictor while holding the other variables constant. An interaction term lets the effect of one predictor depend on the value of another \[12\]. The fuel added per kilometer rises with engine power, so the effects of distance and engine power are read together rather than separately.

#hd[#strong[Regression Analysis Theory];]

Regression theory also explains the conditions that a model must meet and the tools used to check them. There are four conditions for multiple linear regression, known as the LINE conditions. The response is a linear function of the predictors, the errors must be independent, the errors must follow a normal distribution, and the errors must have equal variances. These conditions apply to the population errors, so the researchers assess them using residuals which are the differences between the actual observed values and the values predicted by the model \[14\]. The Ordinary Least Squares method also depends on the independence of the predictors. When the predictors are correlated the design matrix becomes close to singular which makes the least squares estimate highly sensitive to errors in the response and inflates their variance \[13\]. The Variance Inflation Factor is used to measure this effect for each predictor, and a value above 5 indicates high collinearity and large standard errors in the model estimates \[15\]. The diagnostic applies to predictors carrying overlapping information, such as distance traveled and engine power. It applies most to the interaction term, which is built from distance traveled and engine power and shares information with both. Centering both variables before multiplying them reduces this structural collinearity \[12\]. Outliers are screened through the interquartile range rule, which flags values more than 1.5 times the interquartile range below the first quartile or above the third quartile \[16\]. The residual plots check for patterns indicating model misspecification, the Durbin-Watson statistic tests for autocorrelation, and tests for nonconstant variance and normality complete the assessment \[12\], \[15\], guiding the data cleaning and the removal of outliers. When the error variance is not constant, weighted least squares gives each record a weight equal to the inverse of its error variance, which restores equal variance in the weighted errors \[12\]. With very large samples, the p-values of these tests flag even trivial departures, so the size of the departure is judged instead: skewness within ±2 and excess kurtosis within ±7 for normality \[48\], an effect size below the small effect of Cohen's f² \= 0.02 for nonlinearity \[49\], and a ratio of the largest to the smallest error variance of at most 3 for equal variance \[50\].

#hd[#strong[Model Validation Theory];]

Model validation theory affects how the model’s performance is evaluated. Training the predictor and testing it on the same data is a methodological flaw. A model scoring perfectly on the samples it has already seen still fails to predict new trips, a problem called overfitting. Setting aside a portion of the samples as a test set addresses the problem \[13\]. The K-fold cross-validation further improves the situation by partitioning the samples into k folds of equal size, training on k minus one folds, testing on the remaining fold, and averaging the results across the iterations \[13\]. This technique is appropriate for this study as it uses every record for both training and testing, reducing the effect of a single random partition on the reported results. Prior fleet-level modeling applies the same strategy to limit training data selection bias \[11\]. Prediction errors are also divided into bias and variance components \[17\]. Linear Regression model has high bias and low variance because of its linear form \[17\], which explains the stated limitation of this study on nonlinear patterns.

#hd[#strong[Performance Measurement Theory];]

Performance measurement theory provides the three metrics reported as the output of this study. The coefficient of determination, R², shows the proportion of variance in fuel consumption explained by the predictors, with 1.0 being the best possible score, and negative values showing that the model is performing worse than a constant prediction of the mean \[13\]. The Mean Absolute Error shows the average of absolute differences between the recorded and predicted values of liters \[13\]. The Mean Squared Error shows the average of the squared differences, and its square root, the Root Mean Squared Error, returns the error in the same unit as the target variable \[13\], so the result reads directly in liters.

These theories work as one integrated approach. First, regression estimation generates the fuel figure, then the diagnostics confirm the validity of the model, and lastly, the validation and performance measures state how close the predictions are to the actual consumption. The trained model then goes into a web application in which the staff of the General Services Office and the Transportation Office provide the details about their trip and receive a predicted fuel figure before a trip begins.

#pagebreak(weak: true)

#hd[#strong[Related Literature];]

The following is the related literature for this study:

The study titled #strong[“Fuel Prediction Model for Driving Patterns Using Machine Learning Techniques”]; \[8\] focused on predicting the fuel efficiency of vehicles for different drivers based on driving conditions and driver behavior. The authors applied Linear Regression and Support Vector Regression with linear, polynomial, radial basis function, and sigmoid kernels to a real dataset. Before training, the dataset went through preprocessing to handle missing values, normalize numerical features, and encode categorical variables, followed by feature selection to retain the most relevant predictors. The evaluation showed Linear Regression delivering the strongest results, with an R-squared value of 0.9963 and low mean squared error, mean absolute error, and root mean squared error, while the SVR models produced higher prediction errors. This research supports the use of Linear Regression as a simple, interpretable, and accurate method for fuel prediction when the data goes through proper preprocessing.

The study titled #strong[“Regression Modelling Estimation of Marine Diesel Generator Fuel Consumption and Emissions”]; \[2\] focused on estimating the fuel consumption of marine diesel generators on board an oceangoing oil and chemical tanker. The authors collected technical specifications and operational data from the ship’s power generating plant and port calls, then built a mathematical model in Python and MATLAB. Four regression algorithms were compared, including Linear Regression, Support Vector Regression, and Artificial Neural Networks, and evaluated through mean absolute error, the coefficient of determination, and root mean squared error. Ordinary Least Squares Regression emerged as the optimal model, predicting fuel consumption with an R-squared of 0.999, an MAE of 3.932, and an RMSE of 2.935, and was then used for one-year, five-year, and ten-year forecasts. This research demonstrates how a linear model built on operational records supports long-term fuel planning and emission calculation.

The study titled #strong[“Modeling Fuel Consumption of Heavy-duty Trucks Using Telematics Data”]; \[1\] focused on developing fuel consumption models for Euro-3 and Euro-4 heavy-duty trucks operating in Indonesia. The authors gathered telematics data from February to March 2024 through manufacturer-integrated systems linked with GPS, capturing average operational speed, gross vehicle weight, fuel consumption, and road gradient. Using multiple linear regression, the resulting model explained 85.8 percent of the variation in fuel consumption, confirming the combined effect of speed, load, and road gradient on fuel use. The study also noted fuel as the largest component of vehicle operating costs. This research establishes speed, weight, and road condition as practical predictors for fleet fuel estimation and offers a basis for fuel planning and fleet modernization decisions.

The study titled #strong[“Effective Modeling of CO2 Emissions for Light-Duty Vehicles: Linear and Non-Linear Models with Feature Selection”]; \[6\] focused on analyzing vehicle features and their influence on fuel consumption and carbon dioxide emissions of light-duty vehicles. The authors examined feature correlations, then assessed linear regression models and non-linear generalized additive models with different feature subsets for accuracy and consistency. The results showed linear models reaching prediction performance comparable to non-linear models while offering superior interpretability and reliability. The generalized additive models achieved higher accuracy but varied in performance depending on model and parameter choices. The study also confirmed the strong influence of fuel consumption and powertrain attributes on emissions. This research highlights feature selection as a key step in building stable and interpretable linear prediction models.

The study titled #strong[“Data-Driven Machine Learning Techniques for Fuel Economy Prediction in Sustainable Transportation Systems”]; \[9\] focused on identifying the factors influencing fuel economy and comparing machine learning models for its prediction. The authors performed data and correlation analysis on vehicle class, engine size, cylinders, fuel type, and city fuel consumption, then developed Linear Regression, Random Forest Regression, and Support Vector Regression models evaluated through mean squared error, mean absolute error, and R-squared. Random Forest Regression achieved the best results with an R-squared of 0.9843, compared with 0.8567 for Linear Regression. The study also found feature selection reduced dimensionality and improved model performance. This research shows model accuracy depends on the dataset, reinforcing the need to test Linear Regression directly on the target data.

The study titled #strong[“Route-Sensitive Fuel Consumption Models for Heavy-Duty Vehicles”]; \[11\] focused on estimating fuel consumption over one-kilometer road segments for delivery trucks and refuse trucks. The authors compared parametric linear regression models with artificial neural networks using the same input features, and applied k-fold cross-validation to reduce the effect of training data selection. Both approaches differentiated fuel consumption between two vehicles from the same fleet and between two routes of the same vehicle, though neural networks produced narrower 95 percent confidence intervals. The study recommended vocation-specific models for optimizing fuel use of a given fleet, since general models only describe aggregated consumption. This research supports building fleet-specific models and validating them through k-fold cross-validation.

The study titled #strong[“Analysis and Prediction Model of Fuel Consumption and Carbon Dioxide Emissions of Light-Duty Vehicles”]; \[3\] focused on the relationship between vehicle features, fuel consumption, and carbon dioxide emissions using a dataset of 4,973 light-duty vehicles from Canada. The authors applied Linear Regression, Multiple Linear Regression, Univariate Polynomial Regression, and Multivariate Polynomial Regression, then compared model accuracy through R-squared values. Multiple Linear Regression and Multivariate Polynomial Regression reached approximately 75 percent accuracy using several vehicle features, while the univariate polynomial model reached 98.6 percent. The findings showed fuel consumption as a strong predictor of emissions. This research demonstrates how the choice of predictors directly shapes the accuracy of regression-based fuel models.

The study titled #strong[“A Regression-Based Model for Estimating Motorcycle Fuel Consumption”]; \[5\] focused on addressing the gap between manufacturer-reported fuel efficiency and actual riding conditions of motorcycles. The authors, based in Cavite, Philippines, obtained real-world commuting data from the Spritmonitor database and applied descriptive statistics, correlation analysis, and multiple linear regression, with fuel consumption in liters per 100 kilometers as the dependent variable and travel distance, speed category, and fuel type as independent variables. The results showed travel distance and speed significantly influencing fuel consumption, while fuel type showed no significant effect. The regression model achieved an overall accuracy of 98.48 percent with low error values. This research confirms the suitability of multiple linear regression for estimating fuel consumption from operational trip variables.

The study titled #strong[“A Machine Learning Framework for Predicting Fuel Consumption and CO2 Emissions in Hybrid and Combustion Vehicles: Comparative Analysis and Performance Evaluation”]; \[18\] focused on predicting both fuel consumption and carbon dioxide emissions of light-duty vehicles. The authors merged separate datasets of internal combustion engine vehicles and plug-in hybrid vehicles from the Government of Canada into one modeling workflow. They compared 13 models across linear, nonlinear, and ensemble groups. For fuel consumption, Random Forest reached an R-squared of 0.972, while Linear Regression reached 0.928. A 5-fold cross-validation confirmed the stability of the results across all folds. The authors stated the merged dataset improved how well the model generalized. This research supports merging separate data sources into one dataset and validating the model through 5-fold cross-validation.

The study titled #strong[“Trip Based Modeling of Fuel Consumption in Modern Heavy-Duty Vehicles Using Artificial Intelligence”]; \[19\] focused on predicting the total and instantaneous fuel consumption of a trip for modern heavy-duty trucks. The authors used on-road data recorded every second through a portable emissions monitoring system at West Virginia University. The model used only three inputs, namely engine load, engine speed, and vehicle speed. An artificial neural network was compared with Linear Regression and Random Forest through mean absolute error, root mean squared error, and R-squared. The neural network reached an R-squared of 0.7806 on the test data. Linear Regression followed at 0.7340, and Random Forest reached 0.7210. For one test trip, Linear Regression overestimated the total fuel by about 5 percent, and Random Forest underesti- mated it by about 5 percent. This research shows per-trip fuel prediction from a small set of available parameters, with Linear Regression performing close to more complex models.

The study titled #strong[“Estimation of Real-World Fuel Consumption Rate of Light-Duty Vehicles Based on the Records Reported by Vehicle Owners”]; \[20\] focused on estimating the real-world fuel consumption rate of light-duty vehicles in China from records submitted by vehicle owners. The authors built five models: linear regression, naive Bayes regression, neural network regression, decision tree regression, and light gradient boosting machine. The light gradient boosting machine performed best, with a mean absolute error of 0.911 liters per 100 kilometers, a mean absolute percentage error of 10.4 percent, a mean squared error of 1.536, and an R-squared of 0.642. The three most important factors were the reference fuel consumption rate, engine power, and vehicle brand. Among vehicle factors, brand, engine power, and engine displacement had the greatest impact. This research shows manually reported records support fuel prediction and places engine power among the strongest predictors.

The study titled #strong[“Predicting Gasoline Vehicle Fuel Consumption in Energy and Environmental Impact Based on Machine Learning and Multidimensional Big Data”]; \[21\] focused on the gap between the reference fuel consumption reported by manufacturers and the real-world fuel consumption of light-duty gasoline vehicles in China. The authors built five regression models using 25 factors grouped into vehicle, environment, and driving behavior. The models were linear regression, naive Bayes, neural network, random forest, and light gradient boosting machine. Random Forest performed best, with a mean absolute error of 0.630 liters per 100 kilometers, a mean absolute percentage error of 7.5 percent, an R-squared of 0.776, and a 10-fold cross-validation score of 0.791. The three most important factors were brake and accelerator habits, engine power, and the fuel economy awareness of vehicle owners. This research confirms engine power as a key vehicle factor and supports k-fold cross-validation for checking model stability.

The study titled #strong[“Machine Learning Vehicle Fuel Efficiency Prediction”]; \[22\] focused on predicting vehicle fuel efficiency from key vehicle attributes such as fuel type, engine displacement, and vehicle grade. The authors built a custom dataset from the fuel efficiency labeling system of the Korea Energy Agency and added tire size and rolling resistance data. Six regression models were compared, including Linear Regression, Extra Trees, Random Forest, and Gradient Boosting, using mean squared error, root mean squared error, mean absolute error, and R-squared with k-fold cross-validation. Extra Trees and Random Forest gave the best accuracy, with Extra Trees reaching an R-squared of 0.998 on the validation data for Hyundai vehicles. Analysis through SHAP, LIME, and odds ratios identified combined CO2, vehicle grade, fuel type, engine displacement, and transmission type as key markers. This research supports fuel type and engine size as predictors and shows the use of a dataset compiled from published vehicle specifications.

The study titled #strong[“A Machine Learning Model for Average Fuel Consumption in Heavy Vehicles”]; \[23\] focused on developing an individual fuel consumption model for each vehicle in a fleet. The authors summarized data by distance traveled instead of by time period. Seven predictors from vehicle speed and road grade were grouped into fixed distance windows and used to train a neural network. A 1-kilometer window predicted fuel consumption with an R-squared of 0.91 and a mean absolute peak-to-peak percent error below 4 percent for routes with both city and highway segments. The authors stated the model is simple to develop and deploy for each vehicle, which helps a fleet manager reduce total fleet fuel use. This research supports distance as the basis for organizing fleet fuel data and supports vehicle-level models for fleet management.

The study titled #strong[“Vehicular Fuel Consumption and CO2 Emission Estimation Model Integrating Novel Driving Behavior Data Using Machine Learning”]; \[24\] focused on estimating the monthly fuel consumption and carbon dioxide emissions of individual vehicles in Japan. The authors used 228,281 monthly driving records of medium-sized gasoline and hybrid Toyota vehicles, provided by an insurance company. The inputs included total monthly driving time and distance, distance by road type, counts of speeding, sudden acceleration, and sudden braking, and the vehicle specification. Multiple Linear Regression and Random Forest Regression were compared using an 80\/20 train-test split and 5-fold cross-validation. Random Forest reached an R-squared of 0.975, with an RMSE of 13.293 kg and an MAE of 8.329 kg, while Multiple Linear Regression reached 0.842 using the same features. The vehicle specification ranked as the most important feature, followed by driving time and distance. This research shows monthly distance and vehicle attributes support fuel prediction, with Multiple Linear Regression producing reasonable accuracy under the same validation approach used in the present study.

The study titled #strong[“A Comparative Study on Fuel Consumption Prediction Methods of Heavy-Duty Diesel Trucks Considering 21 Influencing Factors”]; \[25\] focused on identifying the factors affecting the fuel consumption of heavy-duty diesel trucks in China. The authors used 1,153 naturalistic driving records from 34 trucks, collected through the fleet management system of a transportation company. The 21 factors covered engine condition, road features, weather, and temperature, while fuel consumption per 100 kilometers was classified as either normal or high. A binary logistic regression first identified the significant factors. A back-propagation neural network, a decision tree, and a random forest were then compared. Random Forest reached the highest classification accuracy at 86.58 percent, followed by the neural network at 83.98 percent and the decision tree at 81.38 percent. This research shows records from a fleet management system support fuel analysis, and identifying significant factors before modeling improves the choice of predictors.

The study titled #strong[“Utilizing Machine Learning Approach to Forecast Fuel Consumption of Backhoe Loader Equipment”]; \[26\] focused on predicting the fuel consumption of backhoe loaders in India. The authors used daily logs from IoT-enabled sensors collected from March 2022 to January 2023. The variables included distance computed from location data, average speed, run hours, and fuel consumption from fuel level sensors. Distance, total run hours, and average speed showed the strongest correlation with fuel consumption. Multiple Linear Regression, Support Vector Regression, and Decision Tree Regression were compared through MAE, MSE, RMSE, and R-squared. Decision Tree reached the highest R-squared at 0.61, while Multiple Linear Regression produced the lowest MAE, MSE, and RMSE at 9.18, 152.54, and 12.35. This research shows distance as a strong predictor of fuel consumption, with Multiple Linear Regression producing the smallest prediction errors even with a lower R-squared.

#pagebreak(weak: true)

#hd[#strong[Relevance to the Cited Literature];]

The study entitled #strong[#emph[“Fuel Prediction Model for Driving Patterns Using Machine Learning Techniques”];]; \[8\] demonstrated Linear Regression achieving an R-squared value of 0.9963 with low MSE, MAE, and RMSE in predicting fuel efficiency, outperforming Support Vector Regression across all tested kernels.

This literature is relevant to the present study as it confirms Linear Regression as an accurate and interpretable model for fuel prediction when the dataset undergoes proper preprocessing, supporting the data cleaning and encoding steps adopted in this study.

The study entitled #strong[#emph[“Regression Modelling Estimation of Marine Diesel Generator Fuel Consumption and Emissions”];]; \[2\] identified Ordinary Least Squares Regression as the optimal model among four algorithms, predicting fuel consumption with an R-squared of 0.999, an MAE of 3.932, and an RMSE of 2.935.

This literature is relevant to the present study as it uses the same three evaluation metrics adopted in this study and shows how a linear model trained on operational records produces reliable fuel estimates, which the present study applies to the university fleet.

The study entitled #strong[“Modeling Fuel Consumption of Heavy-duty Trucks Using Telematics Data”]; \[1\] developed a multiple linear regression model explaining 85.8 percent of the variation in truck fuel consumption using average speed, gross vehicle weight, and road gradient.

This literature is relevant to the present study as it establishes trip speed, vehicle load, and road condition as practical predictors of fuel use, although these variables are absent from the Monthly Report of Official Travel, so this study relies on distance traveled, engine power, and their interaction.

The study entitled #strong[“Effective Modeling of CO2 Emissions for Light-Duty Vehicles: Linear and Non-Linear Models with Feature Selection”]; \[6\] showed linear models reaching prediction performance comparable to non-linear models while providing superior interpretability and reliability.

This literature is relevant to the present study as it justifies the choice of Linear Regression over more complex algorithms, since government offices need a model whose predictions are easy to explain when validating fuel requests.

The study entitled #strong[“Data-Driven Machine Learning Techniques for Fuel Economy Prediction in Sustainable Transportation Systems”]; \[9\] found Random Forest Regression outperforming Linear Regression, with R-squared values of 0.9843 and 0.8567 respectively.

This literature is relevant to the present study as it shows the accuracy of Linear Regression varies by dataset, reinforcing the need to evaluate its performance directly on government fleet records instead of assuming results from other contexts.

The study entitled #strong[“Route-Sensitive Fuel Consumption Models for Heavy-Duty Vehicles”]; \[11\] demonstrated linear regression and neural network models differentiating fuel consumption between vehicles of the same fleet and across routes, with k-fold cross-validation applied to reduce the effect of training data selection.

This literature is relevant to the present study as it supports building a fleet-specific model and adopting k-fold cross-validation, both of which the present study applies in evaluating Linear Regression on the university fleet.

The study entitled #strong[“Analysis and Prediction Model of Fuel Consumption and Carbon Dioxide Emissions of Light-Duty Vehicles”]; \[3\] showed Multiple Linear Regression reaching approximately 75 percent accuracy on 4,973 Canadian vehicles, with accuracy changing depending on the predictors used.

This literature is relevant to the present study as it demonstrates how predictor choice shapes model accuracy, supporting the correlation analysis performed in this study before model training.

The study entitled #strong[“A Regression-Based Model for Estimating Motorcycle Fuel Consumption”]; \[5\] showed travel distance and speed significantly influencing fuel consumption, with the multiple linear regression model achieving an overall accuracy of 98.48 percent.

This literature is relevant to the present study as it confirms the suitability of linear regression for estimating fuel consumption from trip-level variables, supporting the use of distance traveled as a primary predictor in this study.

The study entitled #strong[“A Machine Learning Framework for Predicting Fuel Consumption and CO2 Emissions in Hybrid and Combustion Vehicles: Comparative Analysis and Performance Evaluation”]; \[18\] merged two separate vehicle datasets into one modeling workflow and found Linear Regression reaching an R-squared of 0.928 in predicting fuel consumption, with 5-fold cross-validation confirming the stability of the results.

This literature is relevant to the present study as it supports merging separate data sources into one dataset and validating the model through 5-fold cross-validation, both of which the present study applies in combining the university fleet records with the supplementary dataset.

The study entitled #strong[“Trip Based Modeling of Fuel Consumption in Modern Heavy-Duty Vehicles Using Artificial Intelligence”]; \[19\] predicted the total fuel consumption of a trip from a few key parameters, with Linear Regression reaching an R-squared of 0.7340, close to the 0.7806 of the artificial neural network.

This literature is relevant to the present study as it shows per-trip fuel prediction from a small set of available inputs, supporting the use of Linear Regression to estimate the fuel needed for each official trip of the university fleet.

The study entitled #strong[“Estimation of Real-World Fuel Consumption Rate of Light-Duty Vehicles Based on the Records Reported by Vehicle Owners”]; \[20\] estimated fuel consumption from records submitted by vehicle owners and identified engine power as one of the three most important factors, with the best model reaching an R-squared of 0.642.

This literature is relevant to the present study as it shows manually reported records support fuel prediction and confirms engine power as a key predictor. The moderate accuracy also reflects the known limits of manual records, which the present study faces with the Monthly Report of Official Travel.

The study entitled #strong[“Predicting Gasoline Vehicle Fuel Consumption in Energy and Environmental Impact Based on Machine Learning and Multidimensional Big Data”]; \[21\] compared five regression models using 25 factors and ranked engine power as the second most important factor, with the best model reaching a 10-fold cross-validation score of 0.791.

This literature is relevant to the present study as it confirms engine power as a key predictor. It also supports the interaction term between distance traveled and engine power, since engine power raises the fuel consumed per kilometer.

The study entitled #strong[“Machine Learning Vehicle Fuel Efficiency Prediction”]; \[22\] built a dataset from published vehicle specifications and identified fuel type and engine displacement among the key markers of fuel efficiency, with Extra Trees reaching an R-squared of 0.998.

This literature is relevant to the present study as it supports fuel type and engine size as predictors of fuel use. It also supports taking engine power from published manufacturer specifications matched to each vehicle model, as done in this study.

The study entitled #strong[“A Machine Learning Model for Average Fuel Consumption in Heavy Vehicles”]; \[23\] organized fleet data by distance traveled and built a model for each vehicle, predicting fuel consumption with an R-squared of 0.91 over a 1-kilometer window.

This literature is relevant to the present study as it supports distance traveled as the basis for fleet fuel prediction and shows fuel models built for a specific fleet help managers plan fuel use, which the present study applies to the university fleet.

The study entitled #strong[“Vehicular Fuel Consumption and CO2 Emission Estimation Model Integrating Novel Driving Behavior Data Using Machine Learning”]; \[24\] estimated monthly fuel consumption from driving distance and vehicle specification, with Multiple Linear Regression reaching an R-squared of 0.842 and Random Forest reaching 0.975 under an 80\/20 split and 5-fold cross-validation.

This literature is relevant to the present study as it supports distance and vehicle attributes as predictors of fuel use. It also follows the same 80\/20 train-test split and 5-fold cross-validation adopted in this study, showing Multiple Linear Regression producing reasonable accuracy under this validation approach.

The study entitled #strong[“A Comparative Study on Fuel Consumption Prediction Methods of Heavy-Duty Diesel Trucks Considering 21 Influencing Factors”]; \[25\] used records from the fleet management system of 34 diesel trucks to identify significant fuel factors, with Random Forest reaching a classification accuracy of 86.58 percent.

This literature is relevant to the present study as it shows records kept by a fleet office support fuel analysis, as the present study does with the Monthly Report of Official Travel. It also supports identifying significant factors before modeling, which the present study applies through correlation analysis and the Variance Inflation Factor.

The study entitled #strong[“Utilizing Machine Learning Approach to Forecast Fuel Consumption of Backhoe Loader Equipment”]; \[26\] identified distance as one of the variables most correlated with fuel consumption, with Multiple Linear Regression producing the lowest MAE and RMSE at 9.18 and 12.35.

This literature is relevant to the present study as it supports distance traveled as a primary predictor of fuel use. It also shows the value of reporting MAE and RMSE alongside R-squared, since Multiple Linear Regression gave the smallest errors in liters despite a lower R-squared.

#chap[CHAPTER III][Technicality of the Project]

This chapter presents the technicalities in the development and implementation of the project. It describes the technical framework, tools, techniques, and evaluation metrics used to achieve the objectives of the study. It also details the specific steps involved in data collection, preprocessing, model implementation, and performance evaluation.

#hd[Details of the technologies to be used]

The following are the technologies to be utilized in developing a system:

#strong[Bootstrap]; - a front-end toolkit of responsive layouts and interface components \[40\].

Bootstrap is used for the layout, forms, and tables of the web application.

#strong[Chart.js]; - a JavaScript library for drawing charts on web pages \[41\].

Chart.js draws the charts of the Dashboard and Model Performance pages.

#strong[CSS (Cascading Style Sheets)]; - a stylesheet language used to describe the presentation of documents written in HTML, controlling layout, colors, fonts, and spacing across different screen sizes \[27\].

It is used to style the web application interface and keep the input forms and prediction results readable on both desktop and mobile browsers.

#strong[Firebase Firestore]; - a cloud NoSQL document database by Google for storing and syncing data in real time \[28\].

Firebase Firestore stores the vehicle records, including the engine power and fuel type of each vehicle, the local trip records, the user accounts, and the prediction history of the web application.

#strong[Flask]; - a lightweight web framework written in Python for building web applications, providing routing, request handling, and templating without requiring a fixed project structure \[29\].

Flask serves as the backend of the web application. It loads the saved model, receives the trip and vehicle details entered by the staff, passes them to the model, and returns the predicted fuel consumption.

#strong[Font Awesome]; - an icon library for web pages \[44\].

Font Awesome provides the icons of the menus, buttons, and page sections of the web application.

#strong[Git and GitHub]; - a version control system and an online service for hosting its repositories \[45\].

Git records the changes to the source code, and GitHub holds the repository from which the online application is deployed.

#strong[Google Colab]; - a cloud-based Jupyter notebook environment by Google for writing and running Python code in the browser, with free access to computing resources \[30\].

The Google Colab notebook of the study holds the data cleaning, encoding, merging, model training, and evaluation of the Linear Regression model. The model in the system was produced by running this notebook on the researchers’ computer.

#strong[HTML (HyperText Markup Language)]; - the standard markup language for creating the structure and content of web pages \[31\].

HTML is used to build the pages of the web application, including the input fields for trip metrics and vehicle attributes and the page displaying the predicted fuel figure.

#strong[JavaScript]; - a programming language used to create interactive and dynamic behavior on web pages \[32\].

JavaScript handles input validation on the client side and updates the interface once the prediction result returns from the server.

#strong[Joblib]; - a Python library for saving and loading Python objects efficiently, commonly used to store trained machine learning models \[33\].

Joblib exports the trained Linear Regression model into a file so the Flask backend loads it for predictions without retraining.

#strong[Matplotlib]; - a Python library for creating static, animated, and interactive visualizations \[34\].

Matplotlib is used to plot the actual versus predicted fuel consumption, the residuals, and other charts supporting the evaluation of the model.

#strong[NumPy]; - a Python library for numerical computing, providing support for multi-dimensional arrays and mathematical functions \[35\].

NumPy is used for numerical operations during data preprocessing and for computing the evaluation metrics.

#strong[Pandas]; - an open-source Python library for data analysis and manipulation, built around the DataFrame structure for handling tabular data \[36\].

Pandas is used to load, clean, merge, and transform the historical fleet records, the vehicle records, and the supplementary dataset, including the removal of missing entries and the encoding of categorical variables. Its output is the cleaned and merged CSV file.

#strong[Python]; - a high-level, general-purpose programming language known for its readable syntax and extensive libraries for data science and machine learning \[37\].

Python is the primary language for data preprocessing, model development, evaluation, and the backend of the web application.

#strong[Scikit-learn]; - an open-source machine learning library for Python providing tools for regression, classification, model selection, and evaluation \[13\].

Scikit-learn is used to split the dataset into 80 percent training and 20 percent testing portions, train the Linear Regression model, perform 5-fold cross-validation, and compute R-Squared, MAE, and RMSE.

#strong[Seaborn]; - a Python data visualization library built on Matplotlib for drawing statistical graphics \[38\].

Seaborn is used to generate the correlation heatmap of the predictors.

#strong[Statsmodels]; - a Python library for statistical modeling and hypothesis testing, providing regression models and diagnostic tests \[15\].

Statsmodels is used to compute the Variance Inflation Factor, the Durbin-Watson statistic, and the other assumption tests.

#strong[Vercel]; - a cloud platform for deploying web applications from a source code repository \[46\].

Vercel hosts the online link of the web application at https:\/\/gsu-fleetfuel.vercel.app.

#strong[Visual Studio Code]; - a free source-code editor developed by Microsoft with support for debugging, extensions, and integrated version control \[39\].

Visual Studio Code is used to write and manage the source code of the web application.

#strong[Waitress]; - a production web server for Python web applications \[47\].

Waitress serves the Flask application on the computer of the General Services Office.

#hd[How the Project will work]

The prediction of fuel consumption using Linear Regression estimates the liters of fuel needed for a planned official trip of the university fleet.

First, the researchers gather the Monthly Report of Official Travel records from the General Services Office of Guimaras State University, which provide the date of travel, distance traveled in kilometers, and fuel consumed in liters per trip. The vehicle records, consisting of the plate number, vehicle model, fuel type, and engine power in kilowatts of each vehicle, are compiled for the university fleet. A supplementary dataset containing the distance traveled, engine power, fuel type, and fuel consumed is taken from two open datasets licensed under CC BY 4.0: 50,508 real-world gasoline trips from Fan and Song \[42\], and 49,390 diesel vans from the European Environment Agency \[43\], whose distance and fuel consumed are lifetime totals read from each van’s on-board fuel consumption meter. Both online datasets record fuel consumed in liters, the same unit as the local records, and the distances of the Fan and Song dataset are converted from meters to kilometers. The trip and vehicle records are stored in Firebase Firestore and exported as CSV files for training, together with the supplementary dataset.

Since the trip records and vehicle records are stored separately, the two are merged using the plate number. The local and supplementary data are then combined using their shared variables, and each record is labeled according to its source to identify the local trips after merging.

When the model was trained, the Trip Records module of the system listed 7,595 trips with a recorded fuel figure: the 93 local trips of the Monthly Report of Official Travel, 6 trips recorded through completed fuel requests, and 7,496 of the European Environment Agency records. For these 7,496 records the distance and fuel consumed are the recorded values, while the fleet vehicle, with an engine power within 10 kW of the source van, and the date of travel were assigned by a fixed procedure. They are not actual trips of the university fleet. Each online record is used only once, giving 99,997 records before cleaning: 99 local trips, 7,496 online records in Trip Records, and 92,402 other online records.

#code("import pandas as pd\n\ntrips = pd.read_csv(\"trip_records.csv\")\nvehicles = pd.read_csv(\"vehicle_records.csv\")\nsupplementary = pd.read_csv(\"supplementary_data.csv\")\n\n# Merge the trip records and vehicle records using the plate number\nvehicles = vehicles[[\"plate_number\", \"fuel_type\", \"engine_power_kw\"]]\nlocal = trips.merge(vehicles, on=\"plate_number\", how=\"left\")\n\n# Label each record by its source, then combine on the shared variables\nlocal[\"data_source\"] = local[\"source\"].map(lambda s: \"local\" if pd.isna(s) else \"trip_records_online\")\nsupplementary[\"data_source\"] = \"supplementary\"\ndf = pd.concat([local, supplementary], ignore_index=True)")

The records with missing values or zero distance are removed.

#code("df = df.dropna(subset=[\"distance_km\", \"engine_power_kw\", \"fuel_type\", \"actual_fuel_consumption\"])\ndf = df[df[\"distance_km\"] > 0]")

Extreme outliers are removed using the Interquartile Range (IQR) method. The records are first grouped by engine power, and the method is applied to the fuel used per 100 kilometers within each group of vehicles with the same engine power, so large vehicles are compared only with vehicles of the same size. Values below the lower bound or above the upper bound are removed.

$ "IQR" = Q_3 - Q_1 $

$ "Lower bound" = Q_1 - 1.5("IQR") #h(2em) "Upper bound" = Q_3 + 1.5("IQR") $

After the outliers are removed, only the records within the operating range of the university fleet are kept: diesel vehicles, trips of 30 to 400 kilometers, and engines of 51 to 177 kilowatts. This step removes 61,663 records, including every gasoline record, and leaves 34,476 records.

#code("def within_iqr(per_100km):\n    q1, q3 = per_100km.quantile(0.25), per_100km.quantile(0.75)\n    iqr = q3 - q1\n    return per_100km.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)\n\n# Fuel used per 100 km, compared within each group of the same engine power\nper_100km = df[\"actual_fuel_consumption\"] / df[\"distance_km\"] * 100\nkeep = per_100km.groupby(df[\"engine_power_kw\"], group_keys=False).apply(within_iqr)\ndf = df[keep]\n\n# Keep the fleet's operating range: diesel, 30-400 km, 51-177 kW\ndf = df[(df[\"fuel_type\"] == \"Diesel\") & df[\"distance_km\"].between(30, 400) & df[\"engine_power_kw\"].between(51, 177)]")

Finally, records that the regression equation cannot represent, such as recording errors and unusual trips, are removed. The model is fitted, each residual is standardized, and any record with a standardized residual beyond ±3 is dropped. The fit is repeated until no such record is left. This step removes 360 records, about 1 percent, and leaves 34,116 records.

#code("# Repeat until no record has a standardized residual beyond +/-3\nwhile True:\n    z = standardized_residuals(df)  # weighted residual / its standard deviation\n    if (abs(z) <= 3).all():\n        break\n    df = df[abs(z) <= 3]")

#strong[Encoding:]; Fuel type is a categorical variable, so it is converted into numeric form, where 1 represents gasoline and 0 represents diesel. Since only diesel records remain, the fuel type is 0 in every record and its coefficient is 0, so it has no effect on the predictions.

#code("df[\"fuel_type_code\"] = df[\"fuel_type\"].map({\"Gasoline\": 1, \"Diesel\": 0})")

The data is then split into 80 percent training and 20 percent testing sets using a fixed random seed, so the same split is reproduced in every run.

#code("from sklearn.model_selection import train_test_split\n\npredictors = [\"distance_km\", \"engine_power_kw\"]  # fuel type is 0 (diesel) in every record\nX = df[predictors]\ny = df[\"actual_fuel_consumption\"]\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)")

#strong[Centering and Interaction Term:]; Distance traveled and engine power are centered by subtracting their mean values from the training set. An interaction term between the centered variables is then added to account for the higher fuel use per kilometer of larger engines. Centering reduces the collinearity between the interaction term and its parent variables. The same mean values are saved with the model and applied to every new input in the web application.

$ "Distance"_c = "Distance" - overline("Distance")_"train" $

$ "Engine Power"_c = "Engine Power" - overline("Engine Power")_"train" $

$ "Interaction" = "Distance"_c times "Engine Power"_c $

#code("def add_terms(frame, distance_mean, power_mean):\n    out = frame.copy()\n    out[\"distance_km\"] = out[\"distance_km\"] - distance_mean\n    out[\"engine_power_kw\"] = out[\"engine_power_kw\"] - power_mean\n    out[\"distance_x_power\"] = out[\"distance_km\"] * out[\"engine_power_kw\"]\n    return out\n\n# The means come from the training set and are saved with the model\ndistance_mean = X_train[\"distance_km\"].mean()\npower_mean = X_train[\"engine_power_kw\"].mean()\nterms_train = add_terms(X_train, distance_mean, power_mean)\nterms_test = add_terms(X_test, distance_mean, power_mean)")

Once the predictors are complete, the researchers analyze the cleaned and merged dataset for correlations among the variables, with distance and engine power centered on the training means. The correlation heatmap shows the strength of the relationship between each pair of variables.

#code("import seaborn as sns\nimport matplotlib.pyplot as plt\n\nterms_all = add_terms(X, distance_mean, power_mean)\ncorr = terms_all.assign(actual_fuel_consumption=y).corr()\nsns.heatmap(corr, annot=True, fmt=\".2f\", cmap=\"coolwarm\", vmin=-1, vmax=1)\nplt.title(\"Correlation Heatmap of the Terms\")\nplt.show()")

To check whether the predictors contain overlapping information, the Variance Inflation Factor (VIF) is calculated for each predictor on the cleaned and merged dataset. A VIF value above 5 indicates high collinearity.

$ "VIF"_j = 1 / (1 - R_j^2) $

where #emph[R];#sub[j];#super[2]; is the coefficient of determination from regressing predictor #emph[j]; on all the other predictors.

#code("import statsmodels.api as sm\nfrom statsmodels.stats.outliers_influence import variance_inflation_factor\n\nX_vif = sm.add_constant(terms_all)\nfor i, term in enumerate(X_vif.columns):\n    if term != \"const\":\n        print(term, round(variance_inflation_factor(X_vif.values, i), 2))  # above 5 = high collinearity")

The Linear Regression model is trained on the training set with the following equation. Since the error of a trip grows with the fuel it uses, the coefficients are estimated by weighted least squares in three steps: an ordinary least squares fit, a model of the error variance from the fitted fuel, log(e#super[2]) \= γ#sub[0] \+ γ#sub[1] log(ŷ), and a second fit in which each record is weighted by the inverse of its estimated error variance.

$ hat(y) = & beta_0 + beta_1("Distance"_c) + beta_2("Engine Power"_c) \ & + beta_3("Fuel Type") + beta_4("Distance"_c times "Engine Power"_c) $

#ni[where #emph[ŷ]; is the predicted fuel consumed in liters, #emph[β];#sub[0]; is the intercept, #emph[β];#sub[1]; to #emph[β];#sub[4]; are the coefficients of the predictors, and the subscript #emph[c]; marks a centered variable.]

#code("import numpy as np\nfrom sklearn.linear_model import LinearRegression\n\n# 1. Ordinary least squares fit\nols = LinearRegression().fit(terms_train, y_train)\nfitted = np.clip(ols.predict(terms_train), 0.5, None)\n# 2. Error variance from the fitted fuel: log(e^2) = g0 + g1 log(y^)\ng1, g0 = np.polyfit(np.log(fitted), np.log((y_train - fitted) ** 2 + 1e-6), 1)\nweights = 1 / np.exp(g0 + g1 * np.log(fitted))\n# 3. Weighted least squares fit\nmodel = LinearRegression().fit(terms_train, y_train, sample_weight=weights)\nprint(\"Intercept (β0):\", model.intercept_)\nprint(\"Coefficients (β1 to β4):\", dict(zip(terms_train.columns, model.coef_)))")

After training, the residuals are examined to check the model assumptions. The checks use the standardized residuals, each residual multiplied by the square root of its weight and divided by the standard deviation. The residual plot shows whether the errors are spread evenly around zero without a visible pattern, and the histogram and Q-Q plot show whether the errors follow a normal distribution. The Ramsey RESET test checks linearity, the Jarque-Bera test checks normality, and the Breusch-Pagan test checks for nonconstant variance. With more than 300 records, the p-values of these tests flag even trivial departures, so the decision uses the size of the departure: Cohen's f² of the RESET term below 0.02 for linearity \[49\], skewness within ±2 and excess kurtosis within ±7 for normality \[48\], and a ratio of at most 3 between the largest and the smallest residual variance across five groups of predicted fuel for equal variance \[50\]. The coefficient standard errors and p-values are heteroskedasticity-robust (HC3).

#code("from statsmodels.stats.diagnostic import het_breuschpagan\n\ny_pred = model.predict(terms_test)\nresiduals = y_test - y_pred\n\nfig, ax = plt.subplots(1, 2, figsize=(12, 5))\nax[0].scatter(y_pred, residuals, alpha=0.4)\nax[0].axhline(0, linestyle=\"--\")\nax[0].set(xlabel=\"Predicted Fuel Consumed (L)\", ylabel=\"Residual (L)\", title=\"Residual Plot\")\nsns.histplot(residuals, kde=True, ax=ax[1])\nax[1].set(xlabel=\"Residual (L)\", title=\"Histogram of Residuals\")\nplt.show()\n\nwls = sm.WLS(y_train, sm.add_constant(terms_train), weights=weights).fit()\nz = wls.resid * np.sqrt(weights)  # standardized (weighted) residuals\nlm, p_value, _, _ = het_breuschpagan(z, wls.model.exog)\ngroups = np.array_split(np.argsort(wls.fittedvalues.values), 5)\nvariances = [z.values[g].var() for g in groups]\nprint(\"Breusch-Pagan p-value:\", round(p_value, 4), \" variance ratio:\", round(max(variances) / min(variances), 2))")

The Durbin-Watson statistic tests the residuals of the local trips, arranged according to the date of travel, for autocorrelation. Their average is removed first, since a constant difference for one vehicle is not a relation between consecutive trips. A value close to 2 indicates independent errors.

#code("from statsmodels.stats.stattools import durbin_watson\n\nlocal_trips = df[df[\"data_source\"] == \"local\"].sort_values(\"trip_date\")\nlocal_terms = terms_all.loc[local_trips.index]\nlocal_residuals = local_trips[\"actual_fuel_consumption\"] - model.predict(local_terms)\nprint(\"Durbin-Watson:\", round(durbin_watson(local_residuals - local_residuals.mean()), 3))")

The predicted values for the testing set are then generated using the trained model and compared with the actual fuel consumed. Model accuracy is evaluated using the following performance metrics:

#strong[R-Squared (R#super[2];):]; Measures how much of the variation in fuel consumed is explained by the predictors. A value of 1 means the model explains all of the variation, while a value of 0 means it performs no better than using the average fuel consumed.

$ R^2 = 1 - (sum (y_i - hat(y)_i)^2) / (sum (y_i - overline(y))^2) $

#ni[where #emph[y];#sub[i]; is the actual fuel consumed, #emph[ŷ];#sub[i]; is the predicted fuel consumed, and #emph[ȳ]; is the average of the actual fuel consumed.]

#strong[Mean Absolute Error (MAE):]; Measures the average difference between the actual and predicted fuel consumed, regardless of whether the prediction is too high or too low. Since it is expressed in liters, it shows the typical prediction error directly.

$ "MAE" = 1 / n sum_(i=1)^n abs(y_i - hat(y)_i) $

#ni[where #emph[n]; is the number of trips in the testing set, #emph[y];#sub[i]; is the actual fuel consumed, and #emph[ŷ];#sub[i]; is the predicted fuel consumed.]

#strong[Root Mean Squared Error (RMSE):]; Measures the average prediction error in liters by squaring each error before averaging, which gives more weight to large errors. As a result, RMSE rises sharply when a few predictions are far from the actual value. A large gap between RMSE and MAE indicates some trips have unusually large errors.

$ "RMSE" = sqrt(1 / n sum_(i=1)^n (y_i - hat(y)_i)^2) $

#ni[where #emph[n]; is the number of trips in the testing set, #emph[y];#sub[i]; is the actual fuel consumed, and #emph[ŷ];#sub[i]; is the predicted fuel consumed.]

The metrics are computed for the full testing set.

#code("import numpy as np\nfrom sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error\n\nr2 = r2_score(y_test, y_pred)\nmae = mean_absolute_error(y_test, y_pred)\nrmse = np.sqrt(mean_squared_error(y_test, y_pred))\nprint(f\"R² = {r2:.4f}   MAE = {mae:.4f} L   RMSE = {rmse:.4f} L\")")

To verify whether the same level of accuracy holds for other partitions of the dataset, 5-fold cross-validation divides the dataset into five equal sets, trains the model on four sets, and tests it on the fifth, repeating the process five times so each set serves once as the test set. The centering step is repeated inside each fold, so each test fold stays unseen during training. The mean and standard deviation of the scores across the five folds are reported.

#code("from sklearn.model_selection import KFold\n\nscores = []\nfor train_i, test_i in KFold(n_splits=5, shuffle=True, random_state=42).split(X):\n    X_a, X_b, y_a, y_b = X.iloc[train_i], X.iloc[test_i], y.iloc[train_i], y.iloc[test_i]\n    # centering is repeated inside each fold, so the test fold stays unseen\n    means = X_a[\"distance_km\"].mean(), X_a[\"engine_power_kw\"].mean()\n    fold_model = LinearRegression().fit(add_terms(X_a, *means), y_a)\n    scores.append(r2_score(y_b, fold_model.predict(add_terms(X_b, *means))))\nprint(\"R² per fold:\", np.round(scores, 4))\nprint(f\"Mean R² = {np.mean(scores):.4f}   Std = {np.std(scores):.4f}\")")

The actual and predicted values are plotted to show how closely the predictions follow the recorded fuel consumption.

#code("plt.scatter(y_test, y_pred, alpha=0.4)\nlimits = [min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())]\nplt.plot(limits, limits, \"--\")  # line of perfect prediction\nplt.xlabel(\"Actual Fuel Consumed (L)\")\nplt.ylabel(\"Predicted Fuel Consumed (L)\")\nplt.title(\"Actual vs Predicted Fuel Consumption\")\nplt.show()")

Finally, the trained model and the centering values are saved and integrated into the web application. When the staff of the General Services Office and the Transportation Office select a vehicle and enter the trip distance, the system retrieves the engine power and fuel type of the selected vehicle from its records, applies the same encoding and centering used in training, passes the values to the model, and displays the predicted fuel consumption in liters. Each prediction is stored in the prediction history of the system and submitted as a fuel request. The administrator compares the predicted figure with the request, then approves it with the liters to release or rejects it.

Every user has one of two roles. The administrator of the General Services Office reviews fuel requests, manages the vehicle records, trip records, and user accounts, and uploads the trained model. The staff submit fuel requests and see only the requests they made. A new user signs up and can log in only after the administrator approves the account.

Each fuel request adds a pending trip to the Trip Records. Once the actual fuel consumed is recorded, the same figure is saved to both the fuel request and its trip. If the request is rejected, its pending trip is removed. Pending trips have no fuel figure, so they are left out of model training. Prediction History also shows a predicted range, which is the predicted fuel plus or minus the RMSE of the model, and marks a trip whose actual fuel falls outside this range.

#pagebreak()

#hd[Project Description]

This study aims to help the General Services Office and the Transportation Office of Guimaras State University estimate the fuel needed for official trips before approving fuel requests. By evaluating the performance of a Linear Regression model in predicting the fuel consumption of diesel vehicles from the distance traveled and engine power, this study provides a computed reference for reviewing fuel requests instead of relying only on experience and past records. The trained model is integrated into a web application, named GSU FleetFuel, where the staff select a vehicle and enter the trip distance to receive a predicted fuel figure. The results of this study can also help determine how well manually recorded government trip data, combined with a supplementary dataset, supports fuel consumption prediction, which may assist future researchers in developing more accurate predictive models for government fleet management.

The logo of GSU FleetFuel is a circular emblem with a double gold margin. The upper ring carries the system name, GSU FleetFuel, and the lower ring carries its full name, Fuel Consumption Prediction System. The logo identifies the system only and is not the official seal of Guimaras State University. At the center is the FF Prediction mark, which names what the system does.

#pagebreak()




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

#chap[CHAPTER V][Summary, Conclusion, and Recommendations]

This chapter includes a summary of the researchers’ analyzed findings, documented conclusions, and recommendations that will help improve the proposed system to meet its objectives.

#hd[Summary]

This study developed and evaluated the performance of a Linear Regression model in predicting fuel consumption for the government fleet of Guimaras State University, and integrated the model into a web application for the General Services Office and Transportation Office.

#li[1\. #strong[Data collection.]; The researchers gathered 93 official trips of SFA 4714 from the Monthly Report of Official Travel (January–June 2026), the vehicle records of the nine fleet vehicles, 7,496 trip records built from online datasets, and 92,402 other online records in the supplementary dataset. With 6 trips recorded through completed fuel requests, the total was 99,997 trip records.]

#li[2\. #strong[Preprocessing.]; After merging the records, removing records with missing values or zero distance, removing extreme outliers with the IQR method within each engine-power group, keeping only the operating range of the fleet (diesel, 30 to 400 km, 51 to 177 kW), and removing records with a standardized residual beyond ±3, 34,116 records remained. All 93 trips of the Monthly Report of Official Travel were kept. The interaction term Distance × Engine Power was added. All VIF values were below 5 (highest 1.03).]

#li[3\. #strong[Model development.]; Using an 80\/20 split (27,292 training and 6,824 testing records) and weighted least squares, the model produced the equation ŷ \= −0.6283 \+ 0.02696(Distance) \+ 0.01978(Engine Power) \+ 0.000626(Distance × Engine Power). All terms were significant at α \= 0.05.]

#li[4\. #strong[Model evaluation.]; On the testing set the model reached R² \= 0.9020, MAE \= 1.91 liters and RMSE \= 2.69 liters. 5-fold cross-validation gave a mean R² of 0.9002 with a standard deviation of 0.0023. All five assumption checks were met: linearity (f² \= 0.0003), independence (Durbin-Watson \= 1.630), normality (skewness 0.36, excess kurtosis −0.10), equal variance (variance ratio \= 1.27), and no multicollinearity (highest VIF \= 1.03).]

#li[5\. #strong[Web application.]; The trained model was saved with Joblib and integrated into a Flask web application that uses Firebase Firestore. The staff select a vehicle and enter the trip distance, and the system returns the predicted fuel consumption in liters, stores it in the prediction history, and lets the administrator compare it with the fuel request before approval.]

#li[6\. #strong[Implementation.]; The web application is deployed online for end-user access at https:\/\/gsu-fleetfuel.vercel.app.]

#hd[Conclusion]

Based on the findings, the following conclusions were drawn:

#li[1\. The Monthly Report of Official Travel and the vehicle records of the university fleet, combined with a supplementary dataset, provide enough data to train a fuel consumption model, although the local records alone cover only one vehicle over six months.]

#li[2\. Distance traveled and engine power are suitable predictors of fuel consumed per trip for the diesel vehicles of the fleet. Distance is the strongest predictor, and the predictors do not carry overlapping information.]

#li[3\. Within the operating range of the fleet, Linear Regression predicts fuel consumption with good accuracy. It explains about 90 percent of the variation in fuel consumed, with an average error of about 2 liters per trip.]

#li[4\. The model is stable. Its accuracy stays almost the same across all five cross-validation folds, so the result does not depend on one particular train-test split.]

#li[5\. The errors in liters are larger for trips with higher fuel use, and weighted least squares accounts for this, so the model meets all the assumptions of Linear Regression. The model is reliable as a reference figure, although a prediction for a long trip carries a wider margin of error in liters.]

#li[6\. The web application gives the General Services Office and Transportation Office a computed, per-trip fuel estimate before a trip, so fuel requests can be reviewed against a reference figure instead of relying only on experience and past records.]

#hd[Recommendation]

Based on the conclusions, the researchers recommend the following:

#li[1\. #strong[For the General Services Office.]; Use the predicted fuel figure as a reference when reviewing fuel requests, and record the actual fuel consumed after each trip in the system so the records can be compared and used for future retraining.]

#li[2\. #strong[For the Transportation Office and drivers.]; Submit each official trip through a fuel request in the system and record the actual fuel consumed soon after travel, instead of relying only on the paper-based Monthly Report of Official Travel, to reduce rounding, missing entries and encoding errors.]

#li[3\. #strong[For data collection.]; Gather the Monthly Report of Official Travel of all fleet vehicles, not only SFA 4714, and for a longer period, so the model can be validated on every vehicle of the fleet.]

#li[4\. #strong[For model improvement.]; Retrain the model regularly as more local trips are recorded, so it relies less on the supplementary dataset and reflects local routes and driving conditions.]

#li[5\. #strong[For future researchers.];]

#sli[• Add variables the local records do not capture, such as trip duration, average speed, route, road condition, passenger count and cargo weight, which the literature shows affect fuel use.]

#sli[• Compare Linear Regression with nonlinear models such as Random Forest or Gradient Boosting, especially for the few heaviest trips that the model tends to underestimate.]

#sli[• Compare the weighted least squares used in this study with a transformation of fuel consumed, such as a logarithm, as another way of handling the larger errors of long trips.]

#sli[• Extend the study to other state universities and government agencies to test whether the model applies to other fleets.]

#pagebreak()
#align(center, text(14pt, strong[References]))
#v(4pt)

#refi[\[1\]][P. W. Nariendra, W. Santosa, and A. C. Sutandi, “Modeling fuel consumption of heavy-duty trucks using telematics data,” #emph[Periodica Polytechnica Transportation Engineering];, vol. 54, no. 1, pp. 41–48, 2026, doi: 10.3311\/PPtr.38337.]
#v(2pt)
#refi[\[2\]][O. Yuksel and B. Koseoglu, “Regression modelling estimation of marine diesel generator fuel consumption and emissions,” #emph[Transactions on Maritime Science];, vol. 11, no. 1, pp. 79–94, 2022, doi: 10.7225\/toms.v11.n01.w08.]
#v(2pt)
#refi[\[3\]][N. L. H. Hien and A.-L. Kor, “Analysis and prediction model of fuel consumption and carbon dioxide emissions of light-duty vehicles,” #emph[Applied Sciences];, vol. 12, no. 2, p. 803, 2022, doi: 10.3390\/app12020803.]
#v(2pt)
#refi[\[4\]][J. J. Posada-Henao, I. Sarmiento-Ordosgoitia, and A. A. Correa-Espinal, “Effects of road slope and vehicle weight on truck fuel consumption,” #emph[Sustainability];, vol. 15, no. 1, p. 724, 2023, doi: 10.3390\/su15010724.]
#v(2pt)
#refi[\[5\]][N. W. S. Galera, K. R. M. Cuello, N. P. Milan, M. F. Angelo, C. J. B. Oracion, and B. L. G. Lazaro, “A regression-based model for estimating motorcycle fuel consumption,” #emph[International Journal of Advanced Multidisciplinary Research and Studies];, vol. 6, no. 2, pp. 196–200, 2026, doi: 10.62225\/2583049X.2026.6.2.5947.]
#v(2pt)
#refi[\[6\]][H. T. T. Vu and J. Ko, “Effective modeling of CO2 emissions for light-duty vehicles: Linear and non-linear models with feature selection,” #emph[Energies];, vol. 17, no. 7, p. 1655, 2024, doi: 10.3390\/en17071655.]
#v(2pt)
#refi[\[7\]][Y. Egi, “Vehicle fuel emission efficiency estimation using multi-linear regression in machine learning,” #emph[European Journal of Science and Technology];, no. 34, pp. 115– 120, 2022, doi: 10.31590\/ejosat.1076596.]
#v(2pt)
#refi[\[8\]][T. K. Manjunath and P. S. Ashok Kumar, “Fuel prediction model for driving patterns using machine learning techniques,” #emph[Journal of Computer Science];, vol. 20, no. 3, pp. 291–302, 2024, doi: 10.3844\/jcssp.2024.291.302.]
#v(2pt)
#refi[\[9\]][M. S. Zahid and U. Jamil, “Data-driven machine learning techniques for fuel economy prediction in sustainable transportation systems,” #emph[Green Energy and Intelligent Transportation];, vol. 5, p. 100303, 2026, doi: 10.1016\/j.geits.2025.100303.]
#v(2pt)
#refi[\[10\]][H. I. Ashqar, M. Obaid, A. Jaber, R. Ashqar, N. O. Khanfar, and M. Elhenawy, “Incorporating driving behavior into vehicle fuel consumption prediction: Methodology development and testing,” #emph[Discover Sustainability];, vol. 5, p. 344, 2024, doi: 10.1007\/s43621-024-00511-z.]
#v(2pt)
#refi[\[11\]][A. Schoen, A. Byerly, E. C. dos Santos Jr., and Z. Ben-Miled, “Route-sensitive fuel consumption models for heavy-duty vehicles,” #emph[SAE International Journal of Commercial Vehicles];, vol. 14, no. 1, pp. 85–95, 2021, doi: 10.4271\/02-14-01-0006.]
#v(2pt)
#refi[\[12\]][D. C. Montgomery, E. A. Peck, and G. G. Vining, #emph[Introduction to Linear Regression]; #emph[Analysis];, 5th ed. Hoboken, NJ, USA: Wiley, 2012.]
#v(2pt)
#refi[\[13\]][“scikit-learn: Machine Learning in Python.” \[Online\]. Available: https:\/\/scikit-learn. org\/]
#v(2pt)
#refi[\[14\]][“STAT 501: Regression Methods.” \[Online\]. Available: https:\/\/online.stat.psu.edu\/ stat501\/]
#v(2pt)
#refi[\[15\]][“Statsmodels: Statistics in Python.” \[Online\]. Available: https:\/\/www.statsmodels. org\/]
#v(2pt)
#refi[\[16\]][J. W. Tukey, #emph[Exploratory Data Analysis];. Reading, MA, USA: Addison-Wesley, 1977.]
#v(2pt)
#refi[\[17\]][G. James, D. Witten, T. Hastie, and R. Tibshirani, #emph[An Introduction to Statistical]; #emph[Learning with Applications in R];, 2nd ed. New York, NY, USA: Springer, 2021.]
#v(2pt)
#refi[\[18\]][R. A. Ibrahim and N. E. Zakzouk, “A machine learning framework for predicting fuel consumption and CO2 emissions in hybrid and combustion vehicles: Comparative analysis and performance evaluation,” #emph[PLoS One];, vol. 21, no. 2, p. e0342418, 2026, doi: 10.1371\/journal.pone.0342418.]
#v(2pt)
#refi[\[19\]][S. Katreddi and A. Thiruvengadam, “Trip based modeling of fuel consumption in modern heavy-duty vehicles using artificial intelligence,” #emph[Energies];, vol. 14, no. 24, p. 8592, 2021, doi: 10.3390\/en14248592.]
#v(2pt)
#refi[\[20\]][I. Y. Zeng, S. Tan, J. Xiong, X. Ding, Y. Li, and T. Wu, “Estimation of real-world fuel consumption rate of light-duty vehicles based on the records reported by vehicle owners,” #emph[Energies];, vol. 14, no. 23, p. 7915, 2021, doi: 10.3390\/en14237915.]
#v(2pt)
#refi[\[21\]][Y. Yang, N. Gong, K. Xie, and Q. Liu, “Predicting gasoline vehicle fuel consumption in energy and environmental impact based on machine learning and multidimensional big data,” #emph[Energies];, vol. 15, no. 5, p. 1602, 2022, doi: 10.3390\/en15051602.]
#v(2pt)
#refi[\[22\]][S. Yoo, J. Shin, and S.-H. Choi, “Machine learning vehicle fuel efficiency prediction,” #emph[Scientific Reports];, vol. 15, p. 14815, 2025, doi: 10.1038\/s41598-025-96999-0.]
#v(2pt)
#refi[\[23\]][A. Schoen, A. Byerly, B. Hendrix, R. M. Bagwe, E. C. dos Santos Jr., and Z. Ben Miled, “A machine learning model for average fuel consumption in heavy vehicles,” #emph[IEEE Transactions on Vehicular Technology];, vol. 68, no. 7, pp. 6343–6351, 2019, doi: 10.1109\/TVT.2019.2916299.]
#v(2pt)
#refi[\[24\]][Z. Wang, M. Mae, S. Nishimura, and R. Matsuhashi, “Vehicular fuel consumption and CO2 emission estimation model integrating novel driving behavior data using machine learning,” #emph[Energies];, vol. 17, no. 6, p. 1410, 2024, doi: 10.3390\/en17061410.]
#v(2pt)
#refi[\[25\]][J. Gong, J. Shang, L. Li, C. Zhang, J. He, and J. Ma, “A comparative study on fuel consumption prediction methods of heavy-duty diesel trucks considering 21 influencing factors,” #emph[Energies];, vol. 14, no. 23, p. 8106, 2021, doi: 10.3390\/en14238106.]
#v(2pt)
#refi[\[26\]][P. Katyare, S. Joshi, and M. Kulkarni, “Utilizing machine learning approach to forecast fuel consumption of backhoe loader equipment,” #emph[International Journal of Advanced Computer Science and Applications];, vol. 15, no. 5, pp. 1194–1201, 2024.]
#v(2pt)
#refi[\[27\]][“CSS: Cascading Style Sheets.” \[Online\]. Available: https:\/\/developer.mozilla.org\/ en-US\/docs\/Web\/CSS]
#v(2pt)
#refi[\[28\]][“Firestore | Firebase.” \[Online\]. Available: https:\/\/firebase.google.com\/docs\/firestore]
#v(2pt)
#refi[\[29\]][“Flask.” \[Online\]. Available: https:\/\/flask.palletsprojects.com\/]
#v(2pt)
#refi[\[30\]][“Google Colab.” \[Online\]. Available: https:\/\/colab.research.google.com\/]
#v(2pt)
#refi[\[31\]][“HTML: HyperText Markup Language.” \[Online\]. Available: https:\/\/developer.mozilla.org\/en-US\/docs\/Web\/HTML]
#v(2pt)
#refi[\[32\]][“JavaScript.” \[Online\]. Available: https:\/\/developer.mozilla.org\/en-US\/docs\/Web\/JavaScript]
#v(2pt)
#refi[\[33\]][“Joblib.” \[Online\]. Available: https:\/\/joblib.readthedocs.io\/]
#v(2pt)
#refi[\[34\]][“Matplotlib.” \[Online\]. Available: https:\/\/matplotlib.org\/]
#v(2pt)
#refi[\[35\]][“NumPy.” \[Online\]. Available: https:\/\/numpy.org\/]
#v(2pt)
#refi[\[36\]][“pandas.” \[Online\]. Available: https:\/\/pandas.pydata.org\/]
#v(2pt)
#refi[\[37\]][“Python.” \[Online\]. Available: https:\/\/www.python.org\/]
#v(2pt)
#refi[\[38\]][“seaborn.” \[Online\]. Available: https:\/\/seaborn.pydata.org\/]
#v(2pt)
#refi[\[39\]][“Visual Studio Code.” \[Online\]. Available: https:\/\/code.visualstudio.com\/]
#v(2pt)
#refi[\[40\]][“Bootstrap.” \[Online\]. Available: https:\/\/getbootstrap.com\/]
#v(2pt)
#refi[\[41\]][“Chart.js.” \[Online\]. Available: https:\/\/www.chartjs.org\/]
#v(2pt)
#refi[\[42\]][P. Fan and G. Song, “Which factor contributes more to the fuel consumption gap between in-laboratory vs. real-world driving conditions? An independent component analysis” (Version 2), Mendeley Data, 2022, doi: 10.17632\/jzjxcdn6k4.2.]
#v(2pt)
#refi[\[43\]][European Environment Agency, “2024 real-world CO2 emissions from cars and vans,” 2025, doi: 10.2909\/13e6fad9-149c-4b86-9d83-cdf3569ccfee.]
#refi[\[44\]][“Font Awesome.” \[Online\]. Available: https:\/\/fontawesome.com\/]
#refi[\[45\]][“GitHub.” \[Online\]. Available: https:\/\/github.com\/]
#refi[\[46\]][“Vercel.” \[Online\]. Available: https:\/\/vercel.com\/]
#refi[\[47\]][“Waitress.” \[Online\]. Available: https:\/\/docs.pylonsproject.org\/projects\/waitress\/]
#refi[\[48\]][H.-Y. Kim, “Statistical notes for clinical researchers: Assessing normal distribution (2) using skewness and kurtosis,” #emph[Restorative Dentistry & Endodontics];, vol. 38, no. 1, pp. 52–54, 2013, doi: 10.5395\/rde.2013.38.1.52.]
#refi[\[49\]][J. Cohen, #emph[Statistical Power Analysis for the Behavioral Sciences];, 2nd ed. Hillsdale, NJ, USA: Lawrence Erlbaum Associates, 1988.]
#refi[\[50\]][A. Dean and D. Voss, #emph[Design and Analysis of Experiments];. New York, NY, USA: Springer, 1999.]
#v(2pt)
