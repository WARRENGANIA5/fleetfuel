# Chapter V — Summary, Conclusions and Recommendations (draft, October 30, 2026)

Draft text for Chapter V. It is based on the results in Chapter IV (`docs/THESIS_CHAPTER_IV.md`) and follows the
specific objectives of the study.

## Summary

This study developed and evaluated the performance of a Linear Regression model in predicting fuel consumption
for the government fleet of Guimaras State University, and integrated the model into a web application for the
General Services Office and motorpool staff.

1. **Data collection.** The researchers gathered 93 official trips of SFA 4714 from the Monthly Report of Official
   Travel (January–June 2026), the vehicle records of the nine fleet vehicles, 7,496 trip records built from online
   datasets, and a supplementary dataset of 99,898 records, for a total of 107,487 trip records.
2. **Preprocessing.** After merging the records, removing records with missing values or zero distance, and removing
   extreme outliers with the IQR method within each engine-power group, 96,134 records remained. All 93 local trips
   were kept. Fuel type was encoded as 1 for gasoline and 0 for diesel, and the interaction term Distance × Engine
   Power was added. All VIF values were below 5 (highest 2.28).
3. **Model development.** Using an 80/20 split (76,907 training and 19,227 testing records), the model produced the
   equation ŷ = −1.8174 + 0.04036(Distance) + 0.03258(Engine Power) − 3.0161(Fuel Type) + 0.000503(Distance ×
   Engine Power). All terms were significant at α = 0.05.
4. **Model evaluation.** On the testing set the model reached R² = 0.9502, MAE = 2.51 liters and RMSE = 4.84 liters.
   5-fold cross-validation gave a mean R² of 0.951 with a standard deviation of 0.0008. The assumption checks found
   unequal variance, non-normal residuals, a nonlinear pattern, and autocorrelation among the local trips
   (Durbin-Watson = 0.936); multicollinearity was not present.
5. **Web application.** The trained model was saved with Joblib and integrated into a Flask web application that uses
   Firebase Firestore. The staff select a vehicle and enter the trip distance, and the system returns the predicted
   fuel consumption in liters, stores it in the prediction history, and lets the administrator compare it with the
   fuel request before approval.
6. **Implementation.** The web application is deployed online for end-user access at https://gsu-fleetfuel.vercel.app.

## Conclusions

Based on the findings, the following conclusions were drawn:

1. The Monthly Report of Official Travel and the vehicle records of the university fleet, combined with a
   supplementary dataset, provide enough data to train a fuel consumption model, although the local records alone
   cover only one vehicle over six months.
2. Distance traveled, engine power and fuel type are suitable predictors of fuel consumed per trip. Distance is the
   strongest predictor, and the predictors do not carry overlapping information.
3. Linear Regression predicts fuel consumption for the government fleet with high accuracy. It explains about 95
   percent of the variation in fuel consumed, with an average error of about 2.5 liters per trip.
4. The model is stable. Its accuracy stays almost the same across all five cross-validation folds, so the result does
   not depend on one particular train-test split.
5. The errors are larger for long trips and large vehicles, and the residuals do not fully meet the assumptions of
   Linear Regression. The model is reliable as a reference figure, but its coefficient intervals should be read with
   the robust standard errors, and a prediction for a long trip carries a wider margin of error.
6. The web application gives the General Services Office and motorpool staff a computed, per-trip fuel estimate
   before a trip, so fuel requests can be reviewed against a reference figure instead of relying only on experience
   and past records.

## Recommendations

Based on the conclusions, the researchers recommend the following:

1. **For the General Services Office.** Use the predicted fuel figure as a reference when reviewing fuel requests, and
   record the actual fuel consumed after each trip in the system so the records can be compared and used for future
   retraining.
2. **For the motorpool staff and drivers.** Encode trips in the system soon after travel instead of relying only on the
   paper-based Monthly Report of Official Travel, to reduce rounding, missing entries and encoding errors.
3. **For data collection.** Gather the Monthly Report of Official Travel of all fleet vehicles, not only SFA 4714, and
   for a longer period, so the model can be validated on every vehicle of the fleet.
4. **For model improvement.** Retrain the model regularly as more local trips are recorded, so it relies less on the
   supplementary dataset and reflects local routes and driving conditions.
5. **For future researchers.**
   - Add variables the local records do not capture, such as trip duration, average speed, route, road condition,
     passenger count and cargo weight, which the literature shows affect fuel use.
   - Compare Linear Regression with nonlinear models such as Random Forest or Gradient Boosting, since the
     assumption checks show patterns a linear model cannot fully capture.
   - Apply a transformation of fuel consumed (for example, a logarithm) or weighted regression to address the unequal
     variance of the errors.
   - Extend the study to other state universities and government agencies to test whether the model applies to other
     fleets.
