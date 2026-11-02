# Thesis update — System name and logo (October 30, 2026)

Text for Chapter III (Project Description). It gives the system the name used in the web application and its
logo, so the name "GSU FleetFuel" on the logo, the login page and the page titles is defined in the thesis.

## 1. Project Description — first paragraph (replace)

The Fuel Consumption Prediction System, named **GSU FleetFuel**, is a web-based application for the government
fleet of Guimaras State University. It estimates how much fuel a vehicle needs for a planned official trip. The
General Services Office and motorpool staff use the estimate to review fuel requests before approval, instead of
relying only on experience and past records.

## 2. Logo of the System (new paragraph, after the Project Description)

The logo of GSU FleetFuel is a circular emblem with a double gold margin. The upper ring carries the system
name, GSU FleetFuel, and the lower ring carries its full name, Fuel Consumption Prediction System. The logo
identifies the system only and is not the official seal of Guimaras State University.
At the center is a fuel drop, which represents the fuel consumed per trip, the value the Linear Regression model
predicts. A road runs into the drop and represents the distance traveled, the primary predictor of the model,
while the marks along the road represent the official trips recorded in the Monthly Report of Official Travel.

**Vision.** A Guimaras State University fleet where every official trip begins with an accurate fuel estimate,
built on the university's own Monthly Report of Official Travel and a validated Linear Regression model, giving
the General Services Office and motorpool staff a clear and data-driven basis for every fuel request, ensuring
that every liter charged against public funds is accounted for, and delivered through an accessible web
application.

## 3. Logo files in the system

| File | Use |
|---|---|
| `static/images/seal.svg` | The logo — login, sign-up, sidebar and browser tab of every page |
